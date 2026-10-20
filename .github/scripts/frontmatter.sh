set -eo pipefail
rc=0
while IFS= read -r f; do
  head -n 1 "$f" | grep -qx -- '---' || { echo "missing frontmatter: $f"; rc=1; }
  grep -qE '^name:' "$f" || { echo "missing name: $f"; rc=1; }
  grep -qE '^description:' "$f" || { echo "missing description: $f"; rc=1; }
done < <(git ls-files -- skills | grep -E '(^|/)SKILL\.md$')
exit $rc
