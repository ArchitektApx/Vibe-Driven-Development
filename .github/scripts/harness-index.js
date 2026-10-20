const fs = require("fs");
const path = require("path");
const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
  const p = path.join(dir, e.name);
  return e.isDirectory() ? walk(p) : [p];
});
const NONE = "none: the inline text is complete";
const slugOf = (name) => name.trim().toLowerCase().replace(/\s+/g, "-");
const skills = fs.readdirSync("skills", { withFileTypes: true })
  .filter((e) => e.isDirectory() && fs.existsSync(path.join("skills", e.name, "SKILL.md")))
  .map((e) => path.join("skills", e.name));
const shipped = new Map();
for (const root of skills) {
  const slugs = walk(root)
    .map((f) => path.basename(f).match(/^harness-(.+)\.md$/))
    .filter(Boolean)
    .map((m) => m[1]);
  if (slugs.length) shipped.set(root, slugs);
}
const all = [...new Set([...shipped.values()].flat())].sort();
let rc = 0;
for (const root of shipped.keys()) {
  const skill = path.join(root, "SKILL.md");
  const lines = fs.readFileSync(skill, "utf8").split("\n");
  const start = lines.findIndex((l) => l.trim() === "## Harnesses");
  if (start < 0) {
    console.error(`${skill}: ships a Harness file and has no ## Harnesses section`);
    rc = 1;
    continue;
  }
  let end = lines.findIndex((l, i) => i > start && /^#{1,2} /.test(l));
  if (end < 0) end = lines.length;
  const section = lines.slice(start + 1, end);
  const linked = new Set();
  const none = new Set();
  for (const line of section) {
    for (const m of line.matchAll(/\]\(([^)\s]+)\)/g)) {
      linked.add(path.normalize(m[1].split(/[#?]/)[0]));
    }
    const b = line.match(/^\s*-\s+([^:`]+):\s*(.*?)\s*$/);
    if (b && b[2] === NONE) none.add(slugOf(b[1]));
  }
  for (const slug of all) {
    const own = path.normalize(`references/harness-${slug}.md`);
    if (!linked.has(own) && !none.has(slug)) {
      console.error(`${skill}: ## Harnesses has no entry for ${slug} (a link to ${own}, or "${NONE}")`);
      rc = 1;
    }
  }
}
process.exit(rc);
