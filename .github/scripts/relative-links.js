const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const tracked = execFileSync("git", ["ls-files", "-z", "--", "skills"], { encoding: "utf8" })
  .split("\0").filter(Boolean).map((p) => path.normalize(p));
// A target carrying <angle brackets> is a template placeholder the
// reader fills in, not a file that ships.
const external = (t) => /^[a-z][a-z0-9+.-]*:/i.test(t) || t.startsWith("/") || t.startsWith("#") || /<[^>]*>/.test(t);
let rc = 0;
for (const f of tracked.filter((p) => p.endsWith(".md"))) {
  const raw = fs.readFileSync(f, "utf8");
  for (const m of raw.matchAll(/\[[^\]]*\]\(([^)\s]+)/g)) {
    const target = decodeURIComponent(m[1].trim().split(/[#?]/)[0]);
    if (!target || external(target)) continue;
    if (!fs.existsSync(path.join(path.dirname(f), target))) {
      console.error(`${f}: link resolves to nothing: ${target}`);
      rc = 1;
    }
  }
}
process.exit(rc);
