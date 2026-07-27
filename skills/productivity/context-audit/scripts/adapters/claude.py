#!/usr/bin/env python3
"""Claude Code adapter: the `claude` CLI against the Anthropic Messages API."""
import hashlib, json, os, re, time, urllib.error, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from .base import Adapter, Capture, Counter, Section, Tool

API = "https://api.anthropic.com/v1/messages/count_tokens"
CACHE = os.path.expanduser("~/.cache/context-audit/claude/prices.json")
COUNT_MODEL = "claude-sonnet-4-5-20250929"


class AnthropicCounter(Counter):
    """count_tokens client. Memoises in-process by request shape and, for tool
    schemas, across runs on disk."""

    def __init__(self, headers, jobs=16, use_cache=True):
        self.auth = headers["Authorization"]
        self.jobs = jobs
        self.calls = 0
        self.cached = 0
        self.mem = {}
        try:
            self.disk = json.load(open(CACHE)) if use_cache else {}
        except Exception:
            self.disk = {}
        self.use_cache = use_cache

    def _post(self, body):
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
            "Authorization": self.auth, "anthropic-version": "2023-06-01",
            "anthropic-beta": "oauth-2025-04-20", "content-type": "application/json",
            "user-agent": "claude-cli/2.1.220 (external, sdk-cli)", "x-app": "cli"})
        last = None
        for _ in range(4):
            try:
                with urllib.request.urlopen(req, timeout=90) as f:
                    self.calls += 1
                    return json.loads(f.read())["input_tokens"]
            except urllib.error.HTTPError as e:
                if e.code == 400: raise          # genuinely invalid, do not retry
                last = e
            except Exception as e:
                last = e
        raise last

    def count(self, tools=None, system=None, messages=None):
        body = {"model": COUNT_MODEL,
                "messages": messages or [{"role": "user", "content": "hi"}]}
        if tools: body["tools"] = tools
        if system is not None: body["system"] = system
        key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        if key in self.mem: return self.mem[key]
        v = self._post(body)
        self.mem[key] = v
        return v

    def tool_price(self, tool, base):
        key = hashlib.sha256(json.dumps(tool.schema, sort_keys=True).encode()).hexdigest()
        if key in self.disk:
            self.cached += 1
            return self.disk[key]
        try:
            v = self.count(tools=[tool.schema]) - base
        except Exception:
            return None
        self.disk[key] = v
        return v

    def save(self):
        if not self.use_cache: return
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(self.disk, open(CACHE, "w"))

    def wave(self, fns):
        with ThreadPoolExecutor(self.jobs) as ex:
            return list(ex.map(lambda f: f(), fns))


def _blocks(x):
    if isinstance(x, str): return [x]
    if isinstance(x, list):
        return [b.get("text", "") for b in x if isinstance(b, dict)]
    return []


class ClaudeAdapter(Adapter):
    name = "claude"
    binary = "claude"

    # --- drive -----------------------------------------------------------
    def env(self, base_env, port, tool_search):
        env = dict(base_env)
        env["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{port}"
        # A capture proxy is not a first-party host, so the CLI silently disables
        # tool search. Force it so we observe what real sessions actually send.
        if tool_search == "on": env["ENABLE_TOOL_SEARCH"] = "true"
        else: env.pop("ENABLE_TOOL_SEARCH", None)
        return env

    def command(self, logpath, tool_search, extra):
        cmd = ["claude", "-p", "--input-format", "stream-json",
               "--output-format", "stream-json", "--verbose",
               "--model", "haiku", "--no-session-persistence",
               "--debug", "api", "--debug-file", logpath]
        cmd += [x for x in extra if x != "--"]
        if tool_search == "off": cmd += self.disable_tools_args(["ToolSearch"])
        return cmd

    def send_prompt(self, proc, text):
        msg = {"type": "user", "message": {"role": "user",
               "content": [{"type": "text", "text": text}]}}
        try:
            proc.stdin.write(json.dumps(msg) + "\n"); proc.stdin.flush()
        except BrokenPipeError:
            pass

    def wait_ready(self, logpath, timeout, quiet_for=0.15, poll=0.02, no_mcp_grace=0.8):
        """Return once every MCP server that started connecting has reported in
        and the log has gone quiet. `quiet_for` guards against a server that has
        not yet logged its 'Starting connection' line when we first look; it does
        not need to be long, because self_check catches an early capture."""
        deadline = time.time() + timeout
        last_change, prev = time.time(), (0, 0)
        last_growth, size = time.time(), 0
        # Read incrementally: re-reading a growing debug log each poll is O(n^2).
        buf, pos = [], 0
        while time.time() < deadline:
            try:
                with open(logpath, errors="replace") as f:
                    f.seek(pos); chunk = f.read(); pos = f.tell()
                buf.append(chunk)
            except FileNotFoundError:
                time.sleep(poll); continue
            txt = "".join(buf)
            if len(txt) != size:
                size = len(txt); last_growth = time.time()
            started = len(re.findall(r'Starting connection with timeout', txt))
            done = len(re.findall(r'Connection established|Connection failed|connection error', txt))
            if (started, done) != prev:
                prev = (started, done); last_change = time.time()
            if started > 0 and done >= started and time.time() - last_change >= quiet_for:
                return True, started, done
            # No MCP servers configured at all (e.g. --strict-mcp-config): nothing
            # will ever start, so fall back to "the log stopped growing".
            if started == 0 and size > 0 and time.time() - last_growth >= no_mcp_grace:
                return True, 0, 0
            time.sleep(poll)
        return False, prev[0], prev[1]

    def self_check(self, request, log):
        """The deferred-tools reminder must agree with the registry the CLI
        reports at request time. If it lags, the capture undercounts MCP servers
        and every per-server number downstream is wrong."""
        m = re.search(r'Dynamic tool loading: \d+/(\d+) deferred tools', log)
        if not m: return None
        listed = 0
        for msg in request.get("messages", []):
            for t in _blocks(msg.get("content")):
                if "deferred tools" in t[:200]:
                    listed = len(re.findall(r'^([A-Za-z_][\w.:-]*)$', t, re.M))
        registry = int(m.group(1))
        if listed and listed < registry:
            return (f"reminder lists {listed} deferred tools but registry has "
                    f"{registry} — capture is early. Re-run with a larger --settle.")
        print(f"self-check ok: {listed} deferred names == registry {registry}")
        return None

    def disable_tools_args(self, names):
        return ["--disallowed-tools", *names]

    # --- parse -----------------------------------------------------------
    def parse(self, request):
        tools = [Tool(t["name"], t) for t in request.get("tools", [])]
        msgs = request["messages"]
        texts = [t for m in msgs for t in _blocks(m["content"]) if t.strip()]
        return Capture(tools=tools, system=request.get("system"),
                       messages=msgs, texts=texts)

    def sections(self):
        return [
            Section("deferred tool names by server",
                    lambda t: "deferred tools" in t[:200], self._split_servers),
            Section("skills",
                    lambda t: "skills are available" in t[:200], self._split_skills,
                    limit=15),
        ]

    @staticmethod
    def _split_servers(text):
        names = re.findall(r'^([A-Za-z_][\w.:-]*)$', text, re.M)
        chars, cnt = defaultdict(int), defaultdict(int)
        for nm in names:
            g = nm.split("__")[1] if nm.startswith("mcp__") else "(built-in)"
            chars[g] += len(nm) + 1; cnt[g] += 1
        return [(g, chars[g], f"({cnt[g]} tools)")
                for g in sorted(chars, key=lambda k: -chars[k])]

    @staticmethod
    def _split_skills(text):
        rows = [(m.group(1), len(p)) for p in re.split(r'\n(?=- [\w:-]+: )', text)
                if (m := re.match(r'- ([\w:-]+):', p.strip()))]
        return [(n, c, "") for n, c in sorted(rows, key=lambda x: -x[1])]

    # --- price -----------------------------------------------------------
    def counter(self, headers, jobs=16, use_cache=True):
        return AnthropicCounter(headers, jobs=jobs, use_cache=use_cache)

    # --- apply -----------------------------------------------------------
    def deny_scopes(self, project_dir):
        return [
            ("Global", "~/.claude/settings.json",
             "Tools aren't project-specific — usual case for built-ins"),
            ("Project", os.path.join(project_dir, ".claude/settings.json"),
             "The whole team should get it; committed to git"),
            ("Local", os.path.join(project_dir, ".claude/settings.local.json"),
             "Just this user, just this repo — not committed"),
        ]

    def deny_patch(self, names):
        return {"permissions": {"deny": list(names)}}
