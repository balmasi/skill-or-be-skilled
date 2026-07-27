# Agent profile: Codex CLI

`--agent codex`. Drives `codex exec` against the Responses API; adapter in
`scripts/adapters/codex.py`.

## Requirements and counting

- `codex` on `PATH`
- Codex 0.134.0 or newer (custom Responses providers and one-off `-c` overrides)

The capture uses a temporary custom provider with dummy auth; real credentials
are neither sent nor stored. HTTP retries, WebSockets, and request compression
are disabled. It sends one intercepted request, never reaches a model, and
changes no config. Counting applies the same coarse four-UTF-8-bytes-per-token
heuristic Codex uses for local estimates to each captured input item. The totals
are estimates, not server-billed token counts.

Codex currently puts schemas in an `additional_tools` developer input item.
Code mode exposes a few top-level tools (often `exec`, `wait`,
`request_user_input`, and `collaboration`); tools orchestrated through `exec` are
part of that schema rather than separately priceable functions.

## What to cut

- **Unused skills** — every available skill's name and description is included.
- **Unused MCP servers/plugins/apps** — disable the source, especially when its
  declarations enlarge `exec`.
- **Multi-agent tools** — only if delegation is never used. Measure
  `-c agents.enabled=false`; it removes collaboration tools on current Codex.

Disabling web search can restrict execution but did not change the first-prompt
payload in current E2E tests, so it is not a context optimization here.

Keep the shell/exec tool: removing it defeats Codex's core coding workflow.
Codex has no general CLI flag that denies arbitrary built-in tools, so use the
specific feature, MCP, plugin, or app setting that owns the tool.

## Where settings live

| Scope | File |
|---|---|
| Global | `~/.codex/config.toml` |
| Project | `<project>/.codex/config.toml` (trusted projects only) |

Use `enabled = false` for a whole MCP server, or its `enabled_tools` /
`disabled_tools` lists for individual MCP tools. Project config is appropriate
for repo-specific sources; global config affects every project. Back up the file
before changing it.

Disable an individual discovered skill with its exact path:

```toml
[[skills.config]]
path = "/absolute/path/to/SKILL.md"
enabled = false
```

## Verifying a total

Run a real one-turn command and inspect its final JSONL usage record:

```bash
codex exec --ephemeral --json "say ok"
```

The server's `input_tokens` is authoritative billing usage and can differ from
the local four-bytes-per-token estimate used for fast attribution.
