import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const skillsRoot = path.join(root, "skills");
const errors = [];
const skillPaths = [];

async function walk(directory) {
  for (const entry of await readdir(directory)) {
    const fullPath = path.join(directory, entry);
    const info = await stat(fullPath);

    if (info.isDirectory()) {
      await walk(fullPath);
    } else if (entry === "SKILL.md") {
      skillPaths.push(fullPath);
    }
  }
}

function parseFrontmatter(source, file) {
  const match = source.match(/^---\n([\s\S]*?)\n---\n/);
  if (!match) {
    errors.push(`${file}: missing YAML frontmatter`);
    return {};
  }

  return Object.fromEntries(
    match[1]
      .split("\n")
      .map((line) => line.match(/^([a-z][a-z0-9-]*):\s*(.+)$/))
      .filter(Boolean)
      .map(([, key, value]) => [key, value.trim()]),
  );
}

await walk(skillsRoot);

if (skillPaths.length === 0) {
  errors.push("No skills found.");
}

const names = new Set();

for (const skillPath of skillPaths) {
  const relativePath = path.relative(root, skillPath);
  const source = await readFile(skillPath, "utf8");
  const frontmatter = parseFrontmatter(source, relativePath);
  const directoryName = path.basename(path.dirname(skillPath));

  if (!frontmatter.name) {
    errors.push(`${relativePath}: missing name`);
  } else {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(frontmatter.name)) {
      errors.push(`${relativePath}: invalid skill name "${frontmatter.name}"`);
    }
    if (frontmatter.name !== directoryName) {
      errors.push(`${relativePath}: name must match directory "${directoryName}"`);
    }
    if (names.has(frontmatter.name)) {
      errors.push(`${relativePath}: duplicate skill name "${frontmatter.name}"`);
    }
    names.add(frontmatter.name);
  }

  if (!frontmatter.description) {
    errors.push(`${relativePath}: missing description`);
  } else if (frontmatter.description.length > 1024) {
    errors.push(`${relativePath}: description exceeds 1024 characters`);
  } else if (!frontmatter.description.includes(". Use when ")) {
    errors.push(`${relativePath}: description must state capability, then "Use when ..." triggers`);
  }

  if (source.includes("[TODO")) {
    errors.push(`${relativePath}: unresolved TODO placeholder`);
  }

  const lineCount = source.split("\n").length;
  if (lineCount > 100) {
    errors.push(`${relativePath}: exceeds the 100-line SKILL.md guideline`);
  }
}

const pluginPath = path.join(root, ".claude-plugin", "plugin.json");
try {
  const plugin = JSON.parse(await readFile(pluginPath, "utf8"));
  const declared = new Set(plugin.skills ?? []);

  for (const skillPath of skillPaths) {
    const expected = `./${path.relative(root, path.dirname(skillPath))}`;
    if (!declared.has(expected)) {
      errors.push(`.claude-plugin/plugin.json: missing ${expected}`);
    }
  }
} catch (error) {
  errors.push(`.claude-plugin/plugin.json: ${error.message}`);
}

if (errors.length > 0) {
  console.error(errors.map((error) => `- ${error}`).join("\n"));
  process.exit(1);
}

console.log(`Validated ${skillPaths.length} skill${skillPaths.length === 1 ? "" : "s"}.`);
