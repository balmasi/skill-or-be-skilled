#!/usr/bin/env python3
"""Codex CLI adapter for its Responses API request."""
import json

from .base import Adapter, Capture, Counter, Section, Tool, split_skill_rows


def _tokens(item):
    """Codex's own coarse model-visible estimator: ceil(UTF-8 bytes / 4)."""
    raw = json.dumps(item, separators=(",", ":"), ensure_ascii=False).encode()
    return (len(raw) + 3) // 4


class CodexCounter(Counter):
    def __init__(self):
        self.calls = 0
        self.cached = 0

    def count(self, tools=None, system=None, messages=None):
        self.calls += 1
        items = []
        if tools:
            items.append({"type": "additional_tools", "role": "developer",
                          "tools": tools})
        if system:
            items.extend(system if isinstance(system, list) else [system])
        if messages is None:
            items.append({"role": "user", "content": "hi"})
        else:
            items.extend(messages)
        return sum(_tokens(item) for item in items)


def _texts(item):
    content = item.get("content", [])
    if isinstance(content, str):
        return [content]
    return [part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") in ("input_text", "text")]


class CodexAdapter(Adapter):
    name = "codex"
    binary = "codex"

    def env(self, base_env, port, tool_search):
        self.base_url = f"http://127.0.0.1:{port}/v1"
        return dict(base_env)

    def command(self, logpath, tool_search, extra):
        provider = [
            "-c", 'model_provider="contextaudit"',
            "-c", 'model_providers.contextaudit.name="contextaudit"',
            "-c", f'model_providers.contextaudit.base_url="{self.base_url}"',
            "-c", 'model_providers.contextaudit.wire_api="responses"',
            "-c", 'model_providers.contextaudit.experimental_bearer_token="context-audit"',
            "-c", "model_providers.contextaudit.supports_websockets=false",
            "-c", "model_providers.contextaudit.request_max_retries=0",
            "-c", "model_providers.contextaudit.stream_max_retries=0",
            "--disable", "enable_request_compression",
        ]
        return ["codex", "exec", "--ephemeral", "--json", *provider,
                *[x for x in extra if x != "--"], "-"]

    def send_prompt(self, proc, text):
        proc.stdin.write(text)
        proc.stdin.close()

    def wait_ready(self, logpath, timeout):
        return True, 0, 0

    def self_check(self, request, log):
        if not any(i.get("type") == "additional_tools" for i in request.get("input", [])):
            return "request has no additional_tools item; Codex loaded no tool schemas"
        return None

    def capture_headers(self, headers):
        return {k: v for k, v in headers.items()
                if k.lower() in ("content-type", "user-agent")}

    def disable_tools_args(self, names):
        raise NotImplementedError("Codex has no general built-in tool deny flag")

    def parse(self, request):
        items = request.get("input", [])
        tool_items = [i for i in items if i.get("type") == "additional_tools"]
        tools = [Tool(t.get("name", t.get("type", "?")), t)
                 for item in tool_items for t in item.get("tools", [])]
        system = [i for i in items if i.get("role") == "developer"
                  and i.get("type") != "additional_tools"]
        messages = [i for i in items if i.get("role") != "developer"
                    and i.get("type") != "additional_tools"]
        texts = [text for item in items for text in _texts(item) if text.strip()]
        return Capture(tools, system, messages, texts)

    def sections(self):
        return [Section("skills", lambda t: t.startswith("<skills_instructions>"),
                        self._split_skills, limit=15)]

    @staticmethod
    def _split_skills(text):
        available = text.partition("### Available skills")[2].partition(
            "</skills_instructions>")[0]
        return split_skill_rows(available)

    def counter(self, headers, jobs=16, use_cache=True):
        return CodexCounter()
