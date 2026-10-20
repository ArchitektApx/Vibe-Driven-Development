set -eo pipefail
if [ "$(cat CLAUDE.md)" != "@AGENTS.md" ]; then
  echo "CLAUDE.md must contain exactly the line: @AGENTS.md"
  exit 1
fi
