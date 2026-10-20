set -eo pipefail
rc=0
while IFS= read -r entry; do
  mode=${entry%% *}
  case "$mode" in
    120000) echo "symlink in distributed content: ${entry#* }"; rc=1 ;;
    100755) echo "executable in distributed content: ${entry#* }"; rc=1 ;;
  esac
done < <(git ls-files -s | awk '{print $1" "$4}')
for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json; do
  if grep -qE '"(hooks|mcpServers)"' "$f"; then
    echo "$f declares hooks or MCP servers; only .codex-plugin/plugin.json carries the one hook"; rc=1
  fi
done
node .github/scripts/codex-hook-form.js || rc=1
while IFS= read -r f; do
  echo "unexpected hook or MCP config: $f"; rc=1
done < <(git ls-files | grep -E '(^|/)(hooks\.json|\.mcp\.json|mcp\.json)$' || true)
# A `dependencies` key in agents/openai.yaml can declare tools and
# MCP servers: `interface` and `policy` are the only keys allowed.
while IFS= read -r f; do
  first=$(grep -vE '^([[:space:]]*#|[[:space:]]*$|---$)' "$f" | head -1)
  case "$first" in
    [[:space:]]*) echo "$f: top-level keys must start at column 0"; rc=1 ;;
  esac
  bad=$(grep -vE '^([[:space:]]|#|$|---$|\.\.\.$)' "$f" | grep -vE '^(interface|policy)[[:space:]]*:' || true)
  if [ -n "$bad" ]; then
    echo "$f: top-level keys other than interface and policy:"; echo "$bad"; rc=1
  fi
done < <(git ls-files -- skills | grep -E '/agents/openai\.yaml$')
exit $rc
