# How context-audit works

Measure exactly what a coding agent's own tools, MCP servers, and skills cost in
context on the first prompt of a session — then cut the expensive ones.

Every number comes from the actual API request the agent sends. Nothing is
estimated, and it costs no model tokens: the capture never reaches a model, and
pricing goes through a token-counting endpoint or a local tokenizer.

## Supported agents

| Agent | `--agent` | Notes |
|---|---|---|
| Claude Code | `claude` (default) | [`agent-claude.md`](./agent-claude.md) |

That's the only one implemented today, but the pipeline is agent-neutral: driving
the CLI, parsing the provider's wire format, and counting tokens all sit behind an
adapter in `scripts/adapters/<agent>.py`, with the accompanying judgment (what's
safe to cut, where settings live) in [`agent-<agent>.md`](.). To add one —
Codex, say — see [`adding-an-adapter.md`](./adding-an-adapter.md); the three scripts shouldn't
need to change.

## Requirements

- Python 3.9+ (standard library only)
- The target agent's CLI on `PATH`, with an authenticated session — see that
  agent's reference page for the binary and any auth specifics.

## Usage

```bash
# baseline  (add --agent <name> for anything other than Claude Code)
python3 <skill-directory>/scripts/capture.py --outdir /tmp/ca/base --cwd "$PROJECT_DIR"
python3 <skill-directory>/scripts/analyze.py --capture /tmp/ca/base

# compare removal scenarios, run concurrently
python3 <skill-directory>/scripts/sweep.py --cwd "$PROJECT_DIR" --workdir /tmp/ca \
  "baseline=" \
  "candidate=--disallowed-tools Workflow ScheduleWakeup"
```

Everything after `=` in a sweep scenario is passed to the agent verbatim, so use
that agent's own tool-disabling flag.

Output breaks the first prompt into tool schemas / system prompt / messages, prices
each loaded tool, and adds whatever per-group breakdowns the adapter declares — for
Claude Code, deferred tool names per MCP server and the skills list per skill.

Apply findings by denying tools in the agent's config; the file, scope, and patch
shape are on its reference page. A denial must strip the schema from the request,
not merely block the call at runtime — otherwise it saves nothing.

Used as a skill, [`SKILL.md`](../SKILL.md) drives the whole flow, including which tools are safe
to cut and which are load-bearing.

## What it buys

Context, not speed. Those tokens are cache reads after the first call. The win is
headroom before compaction, plus a cheaper first call per session. Don't expect a
latency improvement.

## How it works

A local HTTP proxy stands in for the provider's API via the agent's base-URL
environment variable, records the first request body, and returns an error so
nothing is billed. The captured tools, system prompt, and messages are then priced
individually.

## Gotchas it handles

Each of these silently corrupts results if you roll your own. These are structural
and apply to any agent; per-agent traps are on the reference pages.

- **The request may fire before the agent has finished loading.** Anything still
  connecting — MCP servers especially — is then absent from the measured tool set.
  Adapters gate the prompt on a readiness signal rather than sleeping blindly, and
  a self-check fails the capture loudly if it still looks early.
- **A capture proxy is not a first-party host**, which can make an agent quietly
  change what it sends — disabling tool search and unrolling every schema, for
  instance. The adapter forces the real behaviour back on.
- **Return 400 from the proxy, never 529.** 529 is retryable, so the CLI backs off
  exponentially and a capture takes minutes instead of seconds.
- **Pricing one tool alone includes a fixed per-request tool-block overhead.** Real
  schema cost is the delta minus that. It's solved across all tools as
  `OH = (Σdeltas − (all − base)) / (N − 1)`, verified against leave-one-out.
  Pseudo-tools the provider rejects when sent alone fall back to leave-one-out
  automatically.
- **Don't predict a saving by subtracting schema costs — it undercounts.** Some
  tools carry context beyond their own schema: in Claude Code, dropping `Agent`
  also drops the agent-types reminder, and dropping `Skill` also drops the entire
  skills list. Always measure the scenario.

## Performance

The floor is agent startup, which for MCP-heavy configs is real work — stdio
servers spawn processes. `--settle` defaults to 0 because the self-check detects an
early capture better than blind padding does.

- `analyze.py` issues all counts in one parallel wave. Per-tool prices cache under
  `~/.cache/context-audit/<agent>/` keyed by schema hash, so re-analysing a what-if re-prices only what changed.
  `--no-cache` forces fresh pricing.
- `sweep.py --jobs` defaults to 4; beyond that, concurrent captures contend for CPU.
- Don't reach for flags that skip project config, skills, or plugins to go faster —
  those are the things being measured. Each reference page lists the safe ones.

## Verifying

A reported total should match the token usage of a real run of the same agent in
the same directory. The exact command is on the agent's reference page.
