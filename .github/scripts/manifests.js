const fs = require("fs");
const read = (f) => {
  try { return JSON.parse(fs.readFileSync(f, "utf8")); }
  catch (e) { console.error(`missing or invalid JSON: ${f}: ${e.message}`); process.exit(1); }
};
const m = read(".claude-plugin/marketplace.json");
const p = read(".claude-plugin/plugin.json");
const c = read(".codex-plugin/plugin.json");
let rc = 0;
const entry = (m.plugins || []).find(e => e.name === p.name);
if (!entry) { console.error(`marketplace.json has no plugin named ${p.name}`); process.exit(1); }
if (entry.version !== p.version) {
  console.error(`version drift: marketplace ${entry.version} vs plugin.json ${p.version}`); rc = 1;
}
if (entry.source !== "./") {
  console.error(`plugin ${p.name} sources from ${JSON.stringify(entry.source)}, expected "./" (this repo)`); rc = 1;
}
// Every field the two plugin manifests both carry agrees, hooks
// excepted: only the Codex manifest carries the one hook. The
// fields Codex repeats must be there in both.
const repeated = ["name", "version", "description", "author", "homepage", "repository", "license", "keywords"];
for (const k of repeated) {
  if (!(k in p) || !(k in c)) {
    console.error(`${k} is missing from ${k in p ? ".codex-plugin" : ".claude-plugin"}/plugin.json`); rc = 1;
  }
}
for (const k of Object.keys(p).filter((k) => k in c && k !== "hooks")) {
  if (JSON.stringify(p[k]) !== JSON.stringify(c[k])) {
    console.error(`.codex-plugin/plugin.json ${k} differs from .claude-plugin/plugin.json`); rc = 1;
  }
}
process.exit(rc);
