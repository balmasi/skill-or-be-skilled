---
name: reflect
description: Reviews agent conversations to find repeated friction, missed skill opportunities, and workflow loops worth improving. Use when the user asks to reflect on current or past work, improve agent workflows, identify recurring corrections or waste, or estimate the leverage of process changes.
---

# Reflect

Review how the human-agent system worked, then recommend the few changes most likely to improve speed and quality. Remain read-only.

## Establish scope

Ask for any missing choice:

- current conversation, selected projects, or all projects;
- Claude Code, Codex, or both;
- an explicit period for every historical review.

Never assume a historical period. Use the current conversation directly when it is the only source.

## Collect historical evidence

Resolve this skill's directory and run:

```sh
python3 <skill-directory>/scripts/sessions.py collect \
  --since <YYYY-MM-DD> --until <YYYY-MM-DD> \
  [--provider claude|codex|all] [--project <path>]
```

Repeat `--project` for multiple projects. Let the script use its temporary output directory unless the user requests another location.

Read `summary.json` first. Inspect `normalized.json` only around candidate sessions and event indexes that need stronger evidence. Do not dump raw transcripts into the response.

## Find leverage

Look across these levels:

1. **Task friction**: repeated corrections, retries, tool errors, expensive exploration, or excessive explanation.
2. **Reusable capability**: repeated work that belongs in a skill, script, reference, project instruction, or better prompt.
3. **Workflow architecture**: places where the human only transfers context, invokes the next step, monitors progress, or reconnects predictable stages.

Compare candidates with existing skills and instructions before proposing something new. Detect semantically equivalent workflows, not merely repeated keywords.

Classify the likely system cause:

- model behavior;
- unclear request or decision;
- missing context or tool;
- weak skill or instruction;
- workflow design.

For orchestration recommendations, verify the current platform supports the proposed mechanism. Prefer built-in platform knowledge; consult current official documentation when needed.

## Estimate leverage

Use conservative Fermi ranges:

```text
projected occurrences × avoidable cost per occurrence × realistic reduction
```

Estimate time and tokens separately when evidence permits. Use measured token totals where available; otherwise label estimates and state assumptions. Avoid false precision. One-off findings qualify only when their cost was exceptional.

Rank by recurrence, friction, generalizability, feasibility, estimated savings, and confidence.

## Report

Return the top three recommendations. For each include:

- **Pattern** and one short recognition cue;
- **Evidence**: observed count and exact review period;
- **Cause** and recommended intervention;
- **Estimated leverage**: conservative time/token range and assumptions;
- **Confidence**: high, medium, or low.

End with a one-line watchlist of weaker patterns. Keep exact session references and detailed evidence available only on request.

Offer to design an implementation-ready skill or agent loop for any selected recommendation. Do not create or modify skills, instructions, or workflows without a separate explicit request.
