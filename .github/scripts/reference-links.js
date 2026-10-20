const fs = require("fs");
const path = require("path");
const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
  const p = path.join(dir, e.name);
  return e.isDirectory() ? walk(p) : [p];
});
// A target carrying <angle brackets> is a template placeholder the
// reader fills in, not a file that ships.
const external = (t) => /^[a-z][a-z0-9+.-]*:/i.test(t) || t.startsWith("/") || t.startsWith("#") || /<[^>]*>/.test(t);
let rc = 0;
for (const entry of fs.readdirSync("skills", { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const root = path.join("skills", entry.name);
  const skill = path.join(root, "SKILL.md");
  if (!fs.existsSync(skill)) {
    console.error(`${root}: no SKILL.md`);
    rc = 1;
    continue;
  }
  const linked = new Set();
  for (const m of fs.readFileSync(skill, "utf8").matchAll(/\[[^\]]*\]\(([^)\s]+)/g)) {
    const target = decodeURIComponent(m[1].trim().split(/[#?]/)[0]);
    if (!target || external(target)) continue;
    linked.add(path.normalize(path.join(root, target)));
  }
  const refs = path.join(root, "references");
  if (!fs.existsSync(refs)) continue;
  for (const f of walk(refs)) {
    if (!linked.has(path.normalize(f))) {
      console.error(`${f}: no direct link from ${skill}`);
      rc = 1;
    }
  }
}
process.exit(rc);
