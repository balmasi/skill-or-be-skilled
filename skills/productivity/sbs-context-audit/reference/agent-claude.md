# Agent profile: Claude Code

`--agent claude` (the default). Drives the `claude` CLI against the Anthropic
Messages API; adapter in `scripts/adapters/claude.py`.

## Requirements

- `claude` on `PATH`, with an authenticated session (`claude auth`)

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

Measure built-ins with space-separated names, for example:

```text
--disallowed-tools Workflow ScheduleWakeup
```

Measure all skills with `--disable-slash-commands`. To isolate an MCP server,
pass `--strict-mcp-config --mcp-config <temporary-config>` containing every
server except that candidate.

## Load-bearing — recommend against removing

- **`Agent`** — removing it kills all subagent delegation, so `/code-review`,
  `/research`, Explore, and any parallel fan-out stop working. Only agree if the
  user says they never delegate.
- **`ToolSearch`** — it defers every other schema, so it saves far more than it costs.
- **`Skill`** — removing it drops the skills list, which looks like a large saving
  but disables every slash command.

These are Claude-specific examples of why schema subtraction undercounts:
removing `Agent` also drops the agent-types reminder; removing `Skill` drops the
skills list. Measure with `sweep.py`.

## Apply built-in denials

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

Remove an MCP server with `claude mcp remove <name> --scope local|project|user`.
Individual skill removal depends on where it was installed; confirm its owner and
path rather than guessing a generic settings patch.
