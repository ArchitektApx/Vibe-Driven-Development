set -eo pipefail
rc=0
r=.github/workflows/release.yml
[ -f "$r" ] || { echo "missing $r"; exit 1; }
trig=$(awk '/^[[:space:]]*#/ {next} /^on:[[:space:]]*$/ {f=1; next} /^[^[:space:]]/ {f=0} f && /^  [^[:space:]]/ {sub(/:.*/, ""); sub(/^ +/, ""); print}' "$r" | sort | paste -sd' ' -)
[ "$trig" = "push workflow_dispatch" ] || { echo "$r: triggers are '$trig', expected push and workflow_dispatch"; rc=1; }
push=$(awk '/^[[:space:]]*#/ {next} /^on:[[:space:]]*$/ {o=1; next} /^[^[:space:]]/ {o=0} o && /^  push:/ {p=1; next} o && /^  [^[:space:]]/ {p=0} o && p && /^    [^[:space:]]/ {sub(/:.*/, ""); sub(/^ +/, ""); print}' "$r" | sort | paste -sd' ' -)
[ "$push" = "tags" ] || { echo "$r: push filters are '$push', expected tags only"; rc=1; }
if awk '/^[[:space:]]*#/ {next} /pull_request/ {f=1} END {exit !f}' "$r"; then
  echo "$r: names a pull_request trigger"; rc=1
fi
perms=$(awk '/^[[:space:]]*#/ {next} /^permissions:/ {f=1; print; next} /^[^[:space:]]/ {f=0} f && NF' "$r" | paste -sd'|' -)
[ "$perms" = "permissions:|  contents: read" ] || { echo "$r: workflow-level permissions are '$perms', expected contents read"; rc=1; }
if ! awk '/^[[:space:]]*#/ {next} /^jobs:/ {j=1} !j && /contents:[[:space:]]*writ[e]/ {f=1} END {exit f}' "$r"; then
  echo "$r: grants contents write access outside a job"; rc=1
fi
writes=$(awk '/^[[:space:]]*#/ {next} /contents:[[:space:]]*writ[e]/ {n++} END {print n+0}' "$r")
[ "$writes" = 1 ] || { echo "$r: grants contents write access in $writes places, expected the release job alone"; rc=1; }
for f in .github/workflows/*.yml .github/workflows/*.yaml; do
  [ -f "$f" ] || continue
  if awk '/^[[:space:]]*#/ {next} /write[-]all/ {f=1} END {exit !f}' "$f"; then
    echo "$f: grants every permission at once"; rc=1
  fi
  [ "$f" = "$r" ] && continue
  if awk '/^[[:space:]]*#/ {next} /contents:[[:space:]]*writ[e]/ {f=1} END {exit !f}' "$f"; then
    echo "$f: grants contents write access, which only release.yml's release job may"; rc=1
  fi
done
exit $rc
