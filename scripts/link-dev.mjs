import { lstat, readdir, readlink, rm, symlink } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const skillsRoot = path.join(root, "skills");
const dryRun = process.argv.includes("--dry-run");

// Every agent that reads ~/.agents/skills directly (Codex among them) picks the
// skills up from there; Claude Code needs its own entry under ~/.claude/skills.
const targets = [
  path.join(homedir(), ".agents", "skills"),
  path.join(homedir(), ".claude", "skills"),
];

const skipDirs = new Set(["node_modules", ".git"]);
const skillDirs = [];

// Any directory holding a SKILL.md is a skill, at any depth under skills/ —
// the category folders (productivity/, …) carry no meaning here.
async function walk(directory) {
  for (const entry of await readdir(directory)) {
    if (skipDirs.has(entry)) continue;
    const fullPath = path.join(directory, entry);
    const info = await lstat(fullPath);

    if (info.isDirectory()) {
      await walk(fullPath);
    } else if (entry === "SKILL.md") {
      skillDirs.push(directory);
    }
  }
}

async function linkKind(linkPath) {
  let info;
  try {
    info = await lstat(linkPath);
  } catch {
    return { kind: "missing" };
  }

  if (!info.isSymbolicLink()) return { kind: "real-dir" };

  const dest = path.resolve(path.dirname(linkPath), await readlink(linkPath));
  if (dest === path.join(root, "skills") || dest.startsWith(skillsRoot + path.sep)) {
    return { kind: "ours", dest };
  }
  return { kind: "foreign", dest };
}

await walk(skillsRoot);

const wanted = new Map(skillDirs.map((dir) => [path.basename(dir), dir]));
const actions = [];

for (const target of targets) {
  // Never create an agent's skills directory — an absent one means that agent
  // isn't set up on this machine, and linking into it would be noise.
  const exists = await lstat(target).then((info) => info.isDirectory(), () => false);
  if (!exists) {
    actions.push(`absent  ${target} (skipped)`);
    continue;
  }

  for (const [name, source] of wanted) {
    const linkPath = path.join(target, name);
    const { kind, dest } = await linkKind(linkPath);

    if (kind === "ours" && dest === source) {
      actions.push(`ok      ${linkPath}`);
      continue;
    }
    if (kind === "real-dir") {
      actions.push(`SKIP    ${linkPath} (real directory — remove it first)`);
      continue;
    }
    if (kind === "foreign") {
      actions.push(`SKIP    ${linkPath} (symlink to ${dest})`);
      continue;
    }

    if (!dryRun) {
      await rm(linkPath, { force: true });
      await symlink(source, linkPath);
    }
    actions.push(`link    ${linkPath} -> ${source}`);
  }

  // Drop links for skills that were renamed or deleted in the working tree.
  for (const entry of await readdir(target).catch(() => [])) {
    if (wanted.has(entry)) continue;
    const linkPath = path.join(target, entry);
    const { kind } = await linkKind(linkPath);
    if (kind !== "ours") continue;

    if (!dryRun) await rm(linkPath, { force: true });
    actions.push(`prune   ${linkPath}`);
  }
}

console.log(actions.join("\n"));
console.log(
  `\n${wanted.size} skill(s)${dryRun ? " (dry run — nothing written)" : ""}`,
);
