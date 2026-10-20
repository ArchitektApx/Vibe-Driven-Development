set -eo pipefail
dupes=$(git ls-files -- skills | grep -E '^skills/[^/]+/SKILL\.md$' | while IFS= read -r f; do grep -h '^name:' "$f" || true; done | sort | uniq -d)
if [ -n "$dupes" ]; then
  echo "duplicate skill names:"; echo "$dupes"; exit 1
fi
