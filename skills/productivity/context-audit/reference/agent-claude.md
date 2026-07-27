# Agent profile: Claude Code

`--agent claude` (the default). Drives the `claude` CLI against the Anthropic
Messages API; adapter in `scripts/adapters/claude.py`.

## Requirements

- `claude` on `PATH`, with an authenticated session (`claude auth`)
- Pricing uses the free `count_tokens` endpoint with the OAuth credentials the
  captured request carried, so no API key of your own is needed. Per-tool prices
  cache in `~/.cache/context-audit/claude/prices.json`.

## What to cut, in rough order of payoff

- **Orchestration and workflow tools they don't use** — often the single largest
  schema in the whole set.
- **Single-purpose tools** — `ScheduleWakeup` (`/loop`), `ReportFindings`
  (`/code-review`), `NotebookEdit`.
- **MCP servers** — judge by name-list cost, not schema cost; with tool search on,
  a connected server usually costs only its tool names. Flag duplicates: a
  staging/prod pair of the same server pays for identical names twice.
- **Skills** — every `.claude/skills/*` description loads each session, so a large
  skills directory is often worth more than any single tool.

## Load-bearing — recommend against removing

- **`Agent`** — removing it kills all subagent delegation, so `/code-review`,
  `/research`, Explore, and any parallel fan-out stop working. Only agree if the
  user says they never delegate.
- **`ToolSearch`** — it defers every other schema, so it saves far more than it costs.
- **`Skill`** — removing it drops the skills list, which looks like a large saving
  but disables every slash command.

## Where a denial can be written

| Scope | File | Use when |
|---|---|---|
| Global | `~/.claude/settings.json` | Tools aren't project-specific — usual case for built-ins |
| Project | `<project>/.claude/settings.json` | The whole team should get it; committed to git |
| Local | `<project>/.claude/settings.local.json` | Just this user, just this repo — not committed |

Recommend global for built-in tools, project scope for anything tied to that repo's
MCP servers or skills. Recommend **local** when the repo is shared and the user
doesn't want to impose their choices on teammates — confirm
`.claude/settings.local.json` is gitignored before writing it, and add it if not.

Say plainly that global affects every project on the machine, including losing
whatever the tool powered.

The patch:

```json
{ "permissions": { "deny": ["Workflow", "ScheduleWakeup"] } }
```

`permissions.deny` and `--disallowed-tools` both strip the schema from the request,
not merely block the call.

## Speed

Most of the runtime is MCP servers connecting. If only built-ins, skills and the
system prompt matter, add `--extra --strict-mcp-config` to skip MCP (loses
per-server attribution). Never use `--bare` or `--safe-mode` to go faster — they
skip CLAUDE.md, skills and plugins, the things being measured.

## Gotchas the adapter handles

- A capture proxy isn't a first-party host, so the CLI disables tool search and
  unrolls every schema. The adapter sets `ENABLE_TOOL_SEARCH=true` so you measure
  what real sessions send. Pass `--tool-search off` when you *want* every schema
  unrolled and priced.
- In `-p` mode the request fires before MCP servers connect, so the prompt is fed
  over stream-json stdin only once the debug log shows every server settled.
- MCP server names contain hyphens, so a `\w`-based regex over the deferred
  tool-name list silently drops servers with a `-` in the name. The self-check
  cross-checks the parsed count against the registry count the CLI logs.

## Verifying a total

```bash
claude -p "say ok" --output-format json | \
  python3 -c "import json,sys; u=json.load(sys.stdin)['usage']; \
  print(u['input_tokens']+u['cache_creation_input_tokens']+u['cache_read_input_tokens'])"
```
