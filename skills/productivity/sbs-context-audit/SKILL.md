---
name: sbs-context-audit
description: Measures a coding agent's first-prompt context cost by tool and agent-specific group from its captured API request. Use when the user wants to shrink context overhead, asks what tools or MCP servers cost, hits compaction early, or is deciding what to disable.
disable-model-invocation: true
---

# Context audit

Resolve this skill's directory first; every command below runs from it, and
`--cwd` is the project being measured, not the skill.

## Measure

Choose the measured agent with `--agent` (default: `claude`). Read
`reference/agent-<agent>.md` before interpreting results or suggesting cuts.

```bash
python3 <skill-directory>/scripts/capture.py --agent <agent> \
  --outdir /tmp/ca/base --cwd <project-directory>
python3 <skill-directory>/scripts/analyze.py --agent <agent> \
  --capture /tmp/ca/base
```

Show the report and let the user choose candidates. Use the agent reference to
identify load-bearing tools and valid disabling arguments.

Measure every proposed removal:

```bash
python3 <skill-directory>/scripts/sweep.py --agent <agent> \
  --cwd <project-directory> --workdir /tmp/ca \
  "baseline=" \
  "candidate=<agent-specific arguments>"
```

Everything after `=` is passed to the agent verbatim. Sweeps modify no settings.

Never infer total savings from schema cost alone: removing a tool can also remove
related prompt blocks. Use the measured scenario delta.

## Apply

Ask before writing. The user chooses scope; paths and setting syntax are in the
agent reference. State plainly when a choice affects every project.

Back up the target file outside a temporary directory and apply the change. Run
a fresh capture/analyze without candidate arguments into `/tmp/ca/after`; compare
it with `/tmp/ca/base`.

Describe the result as context headroom and first-call savings, not a latency win.
