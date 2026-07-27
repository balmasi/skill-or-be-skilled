# Agent profile: Codex CLI

Codex totals use a local four-UTF-8-bytes-per-token estimate over the captured
request. They are not server-billed token counts.

## Controls

| Knob | Effect |
|---|---|
| `developer_instructions`, `AGENTS.md` | Add instructions. Trim user-owned text first. |
| `model_instructions_file` | Replaces Codex's base instructions. High risk; do not recommend as a routine optimization. |
| `skills.config[].enabled` | Controls skill discovery. Measure: one-skill E2E removal saved zero total context. |
| `mcp_servers.<id>.enabled`, `enabled_tools`, `disabled_tools` | Control MCP availability. One-server E2E removal saved zero total context. |
| `web_search` | Selects `cached`, `indexed`, `live`, or `disabled`; current E2E disabling saved zero context. |
| `agents.enabled` | Controls collaboration. Keep enabled: agents are load-bearing. |

Codex has no documented general deny-list for built-in `exec`, `wait`, or
`request_user_input`. Toggling `default_mode_request_user_input` did not remove
the tool in the current E2E run.

Schema cost alone also undercounts on Codex: disabling collaboration removed its
schema and related system instructions. Treat that as measurement evidence, not
a recommendation to disable agents.

## Apply

| Scope | File |
|---|---|
| Global | `~/.codex/config.toml` |
| Project | `<project>/.codex/config.toml` (trusted projects only) |

Global config affects every project. Project config is ignored for untrusted
projects. Sweeps should use one-off `-c` overrides and must not edit either file.
