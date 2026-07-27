---
name: context-audit
description: Measures what a coding agent's tools, MCP servers, and skills cost in context on a session's first prompt, from the real API request rather than an estimate. Use when the user wants to shrink context overhead, asks what their tools or MCP servers cost, hits compaction earlier than expected, or is deciding which tools to disable.
disable-model-invocation: true
---

# Context audit

Prices a coding agent's first prompt per tool, per MCP server, and per skill,
from the actual API request. See `reference/how-it-works.md` for the mechanism.

Resolve this skill's directory first; every command below runs from it, and
`--cwd` is the project being measured, not the skill.

## 0. Pick the agent

The agent being measured is chosen with `--agent`, independent of whichever agent
is reading this skill. Default `claude`;
`python3 <skill-directory>/scripts/capture.py --help` lists what is supported.

**Read `reference/agent-<agent>.md` before advising on anything to cut** — which
tools are worth removing, which are load-bearing, and where a denial gets written
are all agent-specific and live there, not here.

## 1. Baseline

```sh
python3 <skill-directory>/scripts/capture.py --outdir /tmp/ca/base --cwd "$PROJECT_DIR"
python3 <skill-directory>/scripts/analyze.py --capture /tmp/ca/base
```

Reports total tokens split into tool schemas / system prompt / messages, then each
tool's schema cost, plus whatever per-group breakdowns the agent supports (for
Claude Code: deferred tool names per MCP server, and the skills list per skill).

## 2. Let the user pick

Show the table and ask. Which tools they need is their call. Take the candidate
list and the load-bearing list from `reference/agent-<agent>.md` — some tools price
high but disable whole subsystems when removed, and recommending those is a bad
trade the user won't see coming.

## 3. Measure the what-if

```sh
python3 <skill-directory>/scripts/sweep.py --cwd "$PROJECT_DIR" --workdir /tmp/ca \
  "baseline=" \
  "candidate=--disallowed-tools Workflow ScheduleWakeup"
```

Everything after `=` is passed to the agent verbatim, so use that agent's own
tool-disabling flag. Scenarios run concurrently. They only measure; they never
modify settings. Name them after what the user is actually considering.

**Don't predict savings by subtracting schema costs — it undercounts.** Some tools
carry context beyond their own schema, so removing them saves more than the schema
number suggests: in Claude Code, dropping `Agent` also drops the agent-types
reminder, and dropping `Skill` also drops the whole skills list. Always measure.

## 4. Ask where to apply, then apply

**Ask before writing — scope is the user's decision.** The available scopes, the
config file for each, and the shape of the patch are in `reference/agent-<agent>.md`.

Say plainly when a scope is machine-wide, including losing whatever the tool
powered in every other project.

Back up the target file first, somewhere durable — not a temp directory. Then
re-run step 1 to confirm the saving landed.

## What this buys

Context, not speed. Those tokens are cache reads after the first call. The win is
headroom before compaction plus a cheaper first call. Say so — don't let the user
expect lower latency.

## Adding another agent

`reference/adding-an-adapter.md`. The three scripts are agent-neutral; everything
specific lives in `scripts/adapters/<agent>.py` plus a `reference/agent-<agent>.md`.
