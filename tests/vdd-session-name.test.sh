#!/bin/sh
# vdd-session-name.test.sh: the fixture test for the Session-name hook.
#
# Run from anywhere as
#   sh tests/vdd-session-name.test.sh [<hook script>]
# It runs skills/vdd-setup/references/vdd-session-name.sh in place, or the
# script named as the argument (a scratch copy for a mutation check), under
# dash when dash is on PATH and under sh otherwise. Every file it reads or
# writes is built under $TMPDIR, and it touches no real Session.
#
# It prints one PASS or FAIL line per case with what the hook printed, and
# exits 1 when any case fails, 0 when all pass. Every case also expects the
# hook to exit 0. Needs jq.

repo=$(cd "$(dirname "$0")/.." && pwd)
hook=${1:-"$repo/skills/vdd-setup/references/vdd-session-name.sh"}

if command -v dash >/dev/null 2>&1; then
  shell=dash
else
  shell=sh
fi
echo "hook: $hook"
echo "shell: $shell"

command -v jq >/dev/null 2>&1 || { echo "FAIL  jq is not on PATH"; exit 1; }
[ -f "$hook" ] || { echo "FAIL  no hook script at $hook"; exit 1; }

root=$(mktemp -d "${TMPDIR:-/tmp}/vdd-session-name-test.XXXXXX") || exit 1
trap 'rm -rf "$root"' EXIT

proj="$root/proj"
cfg="$root/cfg"
transcripts="$cfg/projects/-proj"
registry="$cfg/sessions"
mkdir -p "$proj" "$transcripts" "$registry"

session=vdd-session-name-test-session
planner=X-feat-Planner
orchestrator=X-feat-Orchestrator

write_loop() {
  # $1: the Harness line, or nothing for a Loop file without one.
  {
    printf '# VDD Loop\n\nRepository: X\nFeature: feat\n'
    [ -n "$1" ] && printf '%s\n' "$1"
    printf '\nSessions:\n- Planner: %s\n- Orchestrator: %s\n' \
      "$planner" "$orchestrator"
  } > "$proj/LOOP.md"
}


# --- Transcript lines ----------------------------------------------------

typed() {
  # A skill the user typed: a user line with string content.
  printf '{"type":"user","message":{"role":"user","content":"<command-message>%s</command-message>\\n<command-name>/%s</command-name>\\n<command-args></command-args>"}}\n' "$1" "$1"
}

plain_user='{"type":"user","message":{"role":"user","content":"hello"}}'
plain_assistant='{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hi."}]}}'

quoted_in_tool_result='{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1","content":"The hook matches <command-name>/vdd:vdd-orchestrator</command-name> and <command-name>/vdd-orchestrator</command-name>."}]}}'

quoted_in_assistant='{"type":"assistant","message":{"role":"assistant","content":[{"type":"thinking","thinking":"The user may have typed <command-name>/vdd:vdd-start-loop</command-name> before."},{"type":"tool_use","id":"t2","name":"Skill","input":{"skill":"vdd:vdd-start-loop","args":"<command-name>/vdd-start-loop</command-name>"}}]}}'

write_tool() {
  printf '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"t3","name":"Write","input":{"file_path":"%s/LOOP.md","content":"# VDD Loop"}}]}}\n' "$proj"
}

title() {
  printf '{"type":"custom-title","customTitle":"%s","sessionId":"%s"}\n' "$1" "$session"
}

half_line='{"type":"user","message":{"role":"user","content":"hal'

t() { echo "$transcripts/$1.jsonl"; }

echo "$plain_user" > "$(t none)"
{ echo "$plain_user"; echo "$plain_assistant"; } >> "$(t none)"
typed vdd:vdd-orchestrator > "$(t orch-plugin)"
typed vdd-orchestrator > "$(t orch-bare)"
typed vdd:vdd-start-loop > "$(t start-plugin)"
typed vdd-start-loop > "$(t start-bare)"
{ typed vdd:vdd-start-loop; echo "$plain_assistant"; typed vdd:vdd-orchestrator; } > "$(t both)"
{ echo "$plain_user"; echo "$quoted_in_tool_result"; } > "$(t tool-result)"
{ echo "$plain_user"; echo "$quoted_in_assistant"; } > "$(t assistant)"
{ echo "$plain_user"; write_tool; } > "$(t writer)"
{ title Something-else; title "$planner"; echo "$plain_user"; } > "$(t restore)"
{ title "$planner"; title Something-else; echo "$plain_user"; } > "$(t unrelated)"
{ typed vdd:vdd-start-loop; printf '%s' "$half_line"; } > "$(t half)"


# --- Running the hook ----------------------------------------------------

failed=0

run() {
  # $1 case label, $2 transcript name, $3 prompt, $4 expected title or "".
  input=$(jq -n -c \
    --arg id "$session" --arg tp "$(t "$2")" --arg cwd "$proj" --arg p "$3" \
    '{session_id: $id, transcript_path: $tp, cwd: $cwd, prompt: $p,
      hook_event_name: "UserPromptSubmit"}')
  out=$(printf '%s' "$input" | CLAUDE_PROJECT_DIR="$proj" "$shell" "$hook")
  status=$?
  got=$(printf '%s' "$out" |
    jq -r '.hookSpecificOutput.sessionTitle // empty' 2>/dev/null)
  if [ "$status" -eq 0 ] && [ "$got" = "$4" ] &&
     { [ -n "$4" ] || [ -z "$out" ]; }; then
    result=PASS
  else
    result=FAIL
    failed=1
  fi
  printf '%s  %-62s exit %s, printed "%s"\n' "$result" "$1" "$status" "$out"
}

write_loop "Harness: Claude Code"

run " 1 no marker in transcript or prompt: silent"        none         "hello"                  ""
run " 2 prompt /vdd:vdd-orchestrator: Orchestrator"       none         "/vdd:vdd-orchestrator"  "$orchestrator"
run " 3 prompt /vdd-orchestrator: Orchestrator"           none         "/vdd-orchestrator"      "$orchestrator"
run " 4 typed /vdd:vdd-orchestrator: Orchestrator"        orch-plugin  "hello"                  "$orchestrator"
run " 5 typed /vdd-orchestrator: Orchestrator"            orch-bare    "hello"                  "$orchestrator"
run " 6 typed /vdd:vdd-start-loop: Planner"               start-plugin "hello"                  "$planner"
run " 7 typed /vdd-start-loop: Planner"                   start-bare   "hello"                  "$planner"
run " 8 typed Start-Loop and Orchestrator: Orchestrator"  both         "hello"                  "$orchestrator"
run " 9 marker only in a tool_result: silent"             tool-result  "hello"                  ""
run "10 marker only in thinking and tool_use: silent"     assistant    "hello"                  ""
run "11 LOOP.md written, no Start-Loop line: silent"      writer       "hello"                  ""
run "12 last custom-title is the Planner: restore"        restore      "hello"                  "$planner"
run "13 last custom-title is unrelated: silent"           unrelated    "hello"                  ""

echo "{\"pid\":1,\"sessionId\":\"$session\",\"name\":\"$planner\"}" > "$registry/1.json"
run "14 Start-Loop typed, registry has Planner: silent"   start-plugin "hello"                  ""
echo "{\"pid\":1,\"sessionId\":\"$session\",\"name\":\"Other-name\"}" > "$registry/1.json"
run "15 Start-Loop typed, registry differs: Planner"      start-plugin "hello"                  "$planner"
rm -f "$registry/1.json"

write_loop "Harness: Cursor"
run "16 Harness: Cursor, prompt /vdd-orchestrator: silent" none        "/vdd-orchestrator"      ""
write_loop ""
run "17 no Harness: line, prompt /vdd-orchestrator: silent" none       "/vdd-orchestrator"      ""
rm -f "$proj/LOOP.md"
run "18 no LOOP.md, prompt /vdd-orchestrator: silent"     none         "/vdd-orchestrator"      ""

write_loop "Harness: Claude Code"
run "19 typed Start-Loop, half-written last line: Planner" half        "hello"                  "$planner"

exit "$failed"
