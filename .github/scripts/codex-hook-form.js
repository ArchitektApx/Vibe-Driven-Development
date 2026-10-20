const c = JSON.parse(require("fs").readFileSync(".codex-plugin/plugin.json", "utf8"));
const hook = {
  type: "command",
  command: "[ ! -d .scratch ] || [ -z \"$(find .scratch -mindepth 2 -maxdepth 2 -name 'codex-armed-*' 2>/dev/null)\" ] || python3 \"${PLUGIN_ROOT}/skills/vdd-setup/scripts/vdd.py\" codex-stop || true",
  commandWindows: "if (Test-Path .scratch\\*\\codex-armed-*) { py -3 \"${PLUGIN_ROOT}\\skills\\vdd-setup\\scripts\\vdd.py\" codex-stop }; exit 0",
  timeout: 2760,
};
const expected = { hooks: { Stop: [{ hooks: [hook] }] } };
let rc = 0;
if (JSON.stringify(c.hooks) !== JSON.stringify(expected)) {
  console.error(".codex-plugin/plugin.json: hooks is not exactly the one Codex Stop hook in its fixed form");
  rc = 1;
}
if ("mcpServers" in c) { console.error(".codex-plugin/plugin.json declares MCP servers"); rc = 1; }
process.exit(rc);
