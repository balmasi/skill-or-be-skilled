# Skill or Be Skilled

Portable skills for working deliberately with AI agents.

The skills use the open [Agent Skills](https://agentskills.io) format and are designed for Codex and Claude Code. Skills are grouped by purpose:

- `skills/productivity/` — general collaboration and thinking workflows
- `skills/engineering/` — software-engineering workflows

## Install

Install the collection with the cross-agent skills installer:

```sh
npx skills@latest add balmasi/skill-or-be-skilled
```

Select the skills and agents you want when prompted.

## Available skills

### Productivity

- [`co-plan`](./skills/productivity/co-plan/SKILL.md) — pressure-test a plan one decision at a time before acting.
- [`reflect`](./skills/productivity/reflect/SKILL.md) — review agent conversations for repeated friction and workflow improvements.

## Develop

```sh
npm test
npm run validate
```

Each skill is a self-contained folder whose entry point is `SKILL.md`. Keep skill behavior portable and add platform-specific metadata only when it provides necessary behavior.
