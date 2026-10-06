#!/bin/sh
# vdd-codex-stop.test.sh: the fixture test for the Codex Stop hook.
#
# Run from anywhere as
#   sh tests/vdd-codex-stop.test.sh [<hook script>]
# It tests skills/vdd-setup/references/vdd-codex-stop.sh, or the script named
# as the argument (a scratch copy for a mutation check). It installs the hook
# beside skills/vdd-setup/references/doorbell-wait.sh, as Setup's shared
# directory holds them, and runs it under dash when dash is on PATH and under
# sh otherwise. Every file it reads or writes is built under $TMPDIR, and it
# touches no real Session.
#
# It prints one PASS or FAIL line per case, and exits 1 when any case fails, 0
# when all pass. Every case also expects the hook to exit 0. Needs no jq.

repo=$(cd "$(dirname "$0")/.." && pwd)
hook_src=${1:-"$repo/skills/vdd-setup/references/vdd-codex-stop.sh"}
wait_src="$repo/skills/vdd-setup/references/doorbell-wait.sh"

if command -v dash >/dev/null 2>&1; then
  shell=dash
else
  shell=sh
fi
echo "hook: $hook_src"
echo "shell: $shell"

[ -f "$hook_src" ] || { echo "FAIL  no hook script at $hook_src"; exit 1; }
[ -f "$wait_src" ] || { echo "FAIL  no wait script at $wait_src"; exit 1; }

root=$(mktemp -d "${TMPDIR:-/tmp}/vdd-codex-stop-test.XXXXXX") || exit 1
trap 'rm -rf "$root"' EXIT

# The shared directory, as Setup fills it, and a second one whose wait is a
# stub that prints TIMEOUT at once, since the real wait times out after 45
# minutes.
shared="$root/share/vdd"
stubbed="$root/stub/vdd"
mkdir -p "$shared" "$stubbed"
cp "$hook_src" "$shared/vdd-codex-stop.sh"
cp "$wait_src" "$shared/doorbell-wait.sh"
cp "$hook_src" "$stubbed/vdd-codex-stop.sh"
printf 'echo TIMEOUT\n' > "$stubbed/doorbell-wait.sh"

proj="$root/proj"
tracker=.scratch/feat
doorbells="$proj/$tracker/doorbells"

id=019a0001-aaaa-7bbb-8ccc-0123456789ab
other=019a0002-dddd-7eee-8fff-0123456789ab

fresh() {
  rm -rf "$proj"
  mkdir -p "$proj/$tracker"
}

write_loop() {
  # $1: the Harness value; $2: "no-tracker" for a Loop file without one.
  {
    printf '# VDD Loop\n\nFeature: feat\nBase branch: main\nFeature branch: feat\n'
    [ "$2" = no-tracker ] || printf 'Tracker: %s/\n' "$tracker"
    printf 'Minors: fix\nPR: no\nFresh Coder: never\nHarness: %s\n' "$1"
  } > "$proj/LOOP.md"
}

ring() {
  # $1 time, $2 receiving Role, $3 Doorbell line.
  printf '%s to: %s %s\n' "$1" "$2" "$3" >> "$doorbells"
}

arm() {
  # $1 session id, $2 the armed file's line.
  printf '%s\n' "$2" > "$proj/$tracker/armed-$1"
}

stop_input() {
  # The Stop hook input, with a session_id field holding $1.
  printf '{"session_id":"%s","turn_id":"t1","cwd":"%s","hook_event_name":"Stop","stop_hook_active":false,"last_assistant_message":"Done."}' "$1" "$proj"
}

snapshot() {
  # Every file under the project, with its checksum.
  (cd "$proj" && find . -type f | sort | while IFS= read -r f; do
    printf '%s %s\n' "$f" "$(cksum < "$f")"
  done)
}

hook() {
  # $1 the directory the hook is installed in, $2 its stdin.
  out=$(cd "$proj" && printf '%s' "$2" | "$shell" "$1/vdd-codex-stop.sh" 2>/dev/null)
  status=$?
}

block() {
  printf '{"decision":"block","reason":"%s"}' "$1"
}

failed=0

verdict() {
  # $1 case label; the rest is the check, run as a command.
  label=$1
  shift
  if [ "$status" -eq 0 ] && "$@"; then
    result=PASS
  else
    result=FAIL
    failed=1
  fi
  printf '%s  %-58s exit %s, printed "%s"\n' "$result" "$label" "$status" "$out"
}

silent_and_untouched() {
  [ -z "$out" ] && [ "$(snapshot)" = "$before" ]
}

printed_and_claimed() {
  # $1 the expected output; the armed file of $id is gone.
  [ "$out" = "$1" ] && [ ! -e "$proj/$tracker/armed-$id" ]
}

planner_line='VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 0 blocker, 1 major, 0 minor. Read it.'
orchestrator_line='VDD Planner: .scratch/feat/ ready, round 1. Read spec.md and issues/.'


# --- Cases ------------------------------------------------------------------

fresh
arm "$id" 'Orchestrator 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
before=$(snapshot)
hook "$shared" "$(stop_input "$id")"
verdict " 1 no LOOP.md: silent, nothing touched" silent_and_untouched

fresh
write_loop Cursor
arm "$id" 'Orchestrator 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
before=$(snapshot)
hook "$shared" "$(stop_input "$id")"
verdict " 2 Harness: Cursor: silent, nothing touched" silent_and_untouched

fresh
write_loop Codex
ring 10:00:00 Orchestrator "$orchestrator_line"
before=$(snapshot)
hook "$shared" "$(stop_input "$id")"
verdict " 3 nothing armed: silent, nothing touched" silent_and_untouched

fresh
write_loop Codex
arm "$other" 'Orchestrator 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
before=$(snapshot)
hook "$shared" "$(stop_input "$id")"
verdict " 4 another Session's armed file: silent, untouched" silent_and_untouched

fresh
write_loop Codex
arm "$id" 'Orchestrator 0'
arm "$other" 'Planner 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
hook "$shared" "$(stop_input "$id")"
claimed_own_only() {
  printed_and_claimed "$(block "10:00:00 to: Orchestrator $orchestrator_line")" &&
    [ "$(cat "$proj/$tracker/armed-$other")" = 'Planner 0' ]
}
verdict " 5 armed, line already there: block, own file deleted" claimed_own_only

fresh
write_loop Codex
arm "$id" 'Planner 1'
ring 10:00:00 Planner "$planner_line"
ring 10:01:00 Orchestrator "$orchestrator_line"
ring 10:02:00 Planner 'VDD Plan-Reviewer: PLAN-REVIEW.md written, round 2: 0 blocker, 0 major, 1 minor. Read it.'
ring 10:03:00 Planner 'VDD Plan-Reviewer: PLAN-REVIEW.md SIGNED OFF, round 3.'
hook "$shared" "$(stop_input "$id")"
newest() {
  printed_and_claimed "$(block '10:03:00 to: Planner VDD Plan-Reviewer: PLAN-REVIEW.md SIGNED OFF, round 3.')"
}
verdict " 6 several lines beyond the count: newest passed" newest

fresh
write_loop Codex
arm "$id" 'Orchestrator 0'
ring 10:00:00 Orchestrator 'VDD Planner: .scratch/a"b\c/ ready, round 1. Read spec.md and issues/.'
hook "$shared" "$(stop_input "$id")"
escaped() {
  printed_and_claimed '{"decision":"block","reason":"10:00:00 to: Orchestrator VDD Planner: .scratch/a\"b\\c/ ready, round 1. Read spec.md and issues/."}'
}
verdict " 7 a line with \" and \\: escaped into valid JSON" escaped

fresh
write_loop Codex
arm "$id" 'Orchestrator 0'
ring 10:00:00 Orchestrator "$(printf 'VDD Planner: .scratch/feat/ ready,\tround 1.\033[0m Read spec.md and issues/.')"
hook "$shared" "$(stop_input "$id")"
no_controls() {
  printed_and_claimed "$(block '10:00:00 to: Orchestrator VDD Planner: .scratch/feat/ ready,round 1.[0m Read spec.md and issues/.')"
}
verdict " 8 a line with a tab and an escape: control characters dropped" no_controls

fresh
write_loop Codex
arm "$id" 'Planner 0'
hook "$stubbed" "$(stop_input "$id")"
timeout_passed() {
  printed_and_claimed "$(block TIMEOUT)"
}
verdict " 9 the wait prints TIMEOUT: TIMEOUT passed on" timeout_passed

fresh
write_loop Codex
arm "$id" 'Coder 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
hook "$shared" "$(stop_input "$id")"
no_block() {
  [ -z "$out" ] && [ ! -e "$proj/$tracker/armed-$id" ]
}
verdict "10 a bad Role in the armed file: no block" no_block

fresh
write_loop Codex
arm "$id" 'Orchestrator x'
ring 10:00:00 Orchestrator "$orchestrator_line"
hook "$shared" "$(stop_input "$id")"
verdict "11 a bad count in the armed file: no block" no_block

fresh
write_loop Codex
arm "$id" 'Orchestrator'
ring 10:00:00 Orchestrator "$orchestrator_line"
hook "$shared" "$(stop_input "$id")"
verdict "12 no count in the armed file: no block" no_block

fresh
write_loop Codex
arm '' 'Orchestrator 0'
arm "$id" 'Orchestrator 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
before=$(snapshot)
hook "$shared" '{"turn_id":"t1","hook_event_name":"Stop","stop_hook_active":false}'
verdict "13 stdin with no session_id: silent, nothing touched" silent_and_untouched

fresh
write_loop Codex
arm '' 'Orchestrator 0'
arm "$id" 'Orchestrator 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
before=$(snapshot)
hook "$shared" "$(stop_input '')"
verdict "14 stdin with an empty session_id: silent, nothing touched" silent_and_untouched

fresh
write_loop Codex no-tracker
arm '' 'Orchestrator 0'
arm "$id" 'Orchestrator 0'
ring 10:00:00 Orchestrator "$orchestrator_line"
before=$(snapshot)
hook "$shared" "$(stop_input "$id")"
verdict "15 Harness: Codex, no Tracker: line: silent, nothing touched" silent_and_untouched

exit "$failed"
