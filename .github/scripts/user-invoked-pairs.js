const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const tracked = execFileSync("git", ["ls-files", "-z", "--", "skills"], { encoding: "utf8" })
  .split("\0").filter(Boolean).map((p) => path.normalize(p));
const frontmatter = (f) => {
  const lines = fs.readFileSync(f, "utf8").split("\n");
  if (lines[0] !== "---") return [];
  const end = lines.indexOf("---", 1);
  return end < 0 ? [] : lines.slice(1, end);
};
const implicitOff = (f) => {
  let top = null;
  for (const line of fs.readFileSync(f, "utf8").split("\n")) {
    const key = line.match(/^([A-Za-z_][\w-]*)\s*:/);
    if (key) { top = key[1]; continue; }
    const m = line.match(/^\s+allow_implicit_invocation\s*:\s*(\S+)\s*$/);
    if (m && top === "policy" && m[1] === "false") return true;
  }
  return false;
};
const policies = new Set(tracked.filter((f) => f.endsWith(path.join(path.sep, "agents", "openai.yaml"))));
let rc = 0;
for (const p of policies) {
  const skill = path.join(path.dirname(path.dirname(p)), "SKILL.md");
  if (!fs.existsSync(skill)) {
    console.error(`${p}: no SKILL.md beside its agents directory`);
    rc = 1;
  }
}
for (const skill of tracked.filter((f) => f.split(path.sep).length === 3 && path.basename(f) === "SKILL.md")) {
  const dir = path.dirname(skill);
  const blocked = frontmatter(skill).some((l) => /^disable-model-invocation:\s*true\s*$/.test(l));
  const p = path.join(dir, "agents", "openai.yaml");
  const off = policies.has(p) && implicitOff(p);
  if (blocked && !policies.has(p)) {
    console.error(`${dir}: disable-model-invocation: true and no agents/openai.yaml`);
    rc = 1;
  } else if (blocked && !off) {
    console.error(`${dir}: disable-model-invocation: true but ${p} does not set policy.allow_implicit_invocation: false`);
    rc = 1;
  } else if (!blocked && off) {
    console.error(`${dir}: ${p} sets policy.allow_implicit_invocation: false but the frontmatter lacks disable-model-invocation: true`);
    rc = 1;
  }
}
process.exit(rc);
