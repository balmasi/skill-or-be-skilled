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

- [`sbs-coplan`](./skills/productivity/sbs-coplan/SKILL.md) — pressure-test a plan one decision at a time before acting.
- [`sbs-context-audit`](./skills/productivity/sbs-context-audit/SKILL.md) — price what your tools, MCP servers, and skills cost in context, then cut the expensive ones.
- [`sbs-reflect`](./skills/productivity/sbs-reflect/SKILL.md) — review agent conversations for repeated friction and workflow improvements.

## Develop

```sh
npm run link              # once, and after adding a skill
npm run validate:skill    # while writing — checks the source, offline
npm run validate          # before release — source + a real install from GitHub
```

`link` symlinks every folder holding a `SKILL.md` into `~/.agents/skills` (Codex) and
`~/.claude/skills`, so edits are live in both agents with no reinstall. If `skills add`
ever replaces the links with copies, run it again.

`validate:skill` checks frontmatter, naming, and that every skill is listed in
`.claude-plugin/plugin.json` — an unlisted skill installs ungrouped under "General".

`validate:publish` installs from GitHub into a throwaway `HOME` and checks the result,
so push first. `validate` runs both.
