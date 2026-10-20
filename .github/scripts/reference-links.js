const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const tracked = execFileSync("git", ["ls-files", "-z", "--", "skills"], { encoding: "utf8" })
  .split("\0").filter(Boolean).map((p) => path.normalize(p));
// A target carrying <angle brackets> is a template placeholder the
// reader fills in, not a file that ships.
const external = (t) => /^[a-z][a-z0-9+.-]*:/i.test(t) || t.startsWith("/") || t.startsWith("#") || /<[^>]*>/.test(t);
let rc = 0;
const roots = [...new Set(tracked.map((f) => f.split(path.sep)).filter((s) => s.length > 2).map((s) => path.join(s[0], s[1])))];
for (const root of roots) {
  const skill = path.join(root, "SKILL.md");
  if (!tracked.includes(skill)) {
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
  const refs = path.join(root, "references") + path.sep;
  for (const f of tracked.filter((p) => p.startsWith(refs))) {
    if (!linked.has(path.normalize(f))) {
      console.error(`${f}: no direct link from ${skill}`);
      rc = 1;
    }
  }
}
process.exit(rc);
