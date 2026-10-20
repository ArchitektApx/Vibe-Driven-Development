set -eo pipefail
rc=0
while IFS= read -r f; do
  size=$(wc -c < "$f")
  if [ "$size" -gt 8192 ]; then
    echo "$f: $size bytes, over 8 KB"; rc=1
  fi
done < <(git ls-files -- skills | grep '/references/')
exit $rc
