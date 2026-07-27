import { execFile } from "node:child_process";
import { lstat, mkdir, mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";
import { promisify } from "node:util";

const run = promisify(execFile);
const root = process.cwd();
const skillsRoot = path.join(root, "skills");
const skipDirs = new Set(["node_modules", ".git"]);

// Installing into a throwaway HOME is the point: a first-time installer has an
// empty home, which is the one configuration our own machine can never be in.
const source = process.argv[2] ?? "balmasi/skill-or-be-skilled";
const failures = [];
const notes = [];

const localDirs = [];
async function walk(directory) {
  for (const entry of await readdir(directory)) {
    if (skipDirs.has(entry)) continue;
    const fullPath = path.join(directory, entry);
    const info = await lstat(fullPath);
    if (info.isDirectory()) await walk(fullPath);
    else if (entry === "SKILL.md") localDirs.push(directory);
  }
}
await walk(skillsRoot);
const local = new Set(localDirs.map((dir) => path.basename(dir)));

const manifestPath = path.join(root, ".claude-plugin", "plugin.json");
const manifest = JSON.parse(await readFile(manifestPath, "utf-8"));
const manifestNames = new Set(
  (manifest.skills ?? []).map((entry) => path.basename(entry)),
);

// A skill missing from plugin.json still installs — it just lands ungrouped
// under "General" for everyone who installs it.
for (const name of local) {
  if (!manifestNames.has(name)) {
    failures.push(`${name}: in skills/ but not listed in .claude-plugin/plugin.json`);
  }
}
for (const name of manifestNames) {
  if (!local.has(name)) {
    failures.push(`${name}: listed in plugin.json but no such folder in skills/`);
  }
}

const home = await mkdtemp(path.join(tmpdir(), "sbs-verify-"));
try {
  await mkdir(path.join(home, ".agents", "skills"), { recursive: true });
  await mkdir(path.join(home, ".claude", "skills"), { recursive: true });

  await run(
    "npx",
    ["-y", "skills@latest", "add", source, "-g", "-s", "*", "-a", "claude-code", "-a", "codex", "-y"],
    { env: { ...process.env, HOME: home }, cwd: tmpdir() },
  );

  const lock = JSON.parse(
    await readFile(path.join(home, ".agents", ".skill-lock.json"), "utf-8"),
  ).skills;
  const installed = new Set(Object.keys(lock));

  for (const name of local) {
    if (!installed.has(name)) {
      failures.push(`${name}: in working tree but not in the published install (unpushed?)`);
    }
  }
  for (const name of installed) {
    if (!local.has(name)) {
      notes.push(`${name}: published but no longer in the working tree`);
    }
    if (lock[name].pluginName !== manifest.name) {
      failures.push(
        `${name}: grouped as ${lock[name].pluginName ?? "General"}, expected ${manifest.name}`,
      );
    }
  }

  // The Claude Code entries are symlinks into ~/.agents/skills; a dangling one
  // means the skill installs but never loads.
  for (const entry of await readdir(path.join(home, ".claude", "skills"))) {
    const target = path.join(home, ".claude", "skills", entry, "SKILL.md");
    const ok = await lstat(target).then(() => true, () => false);
    if (!ok) failures.push(`${entry}: Claude Code link does not resolve to a SKILL.md`);
  }

  console.log(`source:    ${source}`);
  console.log(`installed: ${[...installed].sort().join(", ")}`);
  console.log(`grouped:   ${manifest.name}`);
} finally {
  await rm(home, { recursive: true, force: true });
}

for (const note of notes) console.log(`note  ${note}`);
if (failures.length > 0) {
  console.error(`\n${failures.length} problem(s):`);
  for (const failure of failures) console.error(`  ✗ ${failure}`);
  process.exit(1);
}
console.log("\nok");
