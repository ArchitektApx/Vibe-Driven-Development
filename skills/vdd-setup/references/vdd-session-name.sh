#!/bin/sh
# vdd-session-name.sh: the Session-name hook of Vibe Driven Development.
#
# vdd-setup copies this script to ~/.claude/hooks/ on Claude Code and
# registers it in ~/.claude/settings.json as a UserPromptSubmit hook, which
# the user's settings run with sh. It ships at mode 644 and is never made
# executable.
#
# On every prompt in a project whose LOOP.md says "Harness: Claude Code", it
# gives this Session the Planner or the Orchestrator Session name that the
# Loop file records, so a Doorbell sent by name reaches it. Elsewhere it
# exits at once and prints nothing.
#
# It reads the hook input on stdin (session_id, transcript_path, prompt,
# cwd); LOOP.md in the project directory, which is CLAUDE_PROJECT_DIR, or
# cwd from the input when that is unset; this Session's transcript; and the
# session registry, the sessions directory three levels above the
# transcript. It writes nothing but its output, and it needs jq.
#
# Four outcomes, first match wins:
#   Orchestrator  the prompt starts with /vdd:vdd-orchestrator or
#                 /vdd-orchestrator, or the user typed either one earlier in
#                 this Session
#   Planner       the user typed /vdd:vdd-start-loop or /vdd-start-loop in
#                 this Session
#   Restore       the last title this Session carried is the Planner or the
#                 Orchestrator name
#   Nothing       none of the above, or the Session already has the name
#
# A skill counts only from a line the user typed: a transcript line of type
# user whose message content is a string. Tool results, injected skill
# bodies, tool calls and thinking that quote a skill name never count.
#
# It renames by printing
#   {"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","sessionTitle":"<name>"}}
# and exits 0 on every path: a UserPromptSubmit hook that exits 2 blocks the
# user's prompt.

# vdd-session-name v1

command -v jq >/dev/null 2>&1 || exit 0


# --- Read the hook input -------------------------------------------------

input=$(cat)

field() {
  printf '%s' "$input" | jq -r --arg key "$1" '.[$key] // empty | strings' 2>/dev/null
}

session_id=$(field session_id)
transcript=$(field transcript_path)
prompt=$(field prompt)
project_dir=${CLAUDE_PROJECT_DIR:-$(field cwd)}


# --- Read the Loop file --------------------------------------------------

loop_file="$project_dir/LOOP.md"
[ -n "$project_dir" ] && [ -f "$loop_file" ] || exit 0

grep -Eq '^Harness: *Claude Code *$' "$loop_file" || exit 0

name_from_loop() {
  sed -n "s/^- $1: *//p" "$loop_file" | head -n 1 |
    sed 's/ *$//'
}

planner_name=$(name_from_loop Planner)
orchestrator_name=$(name_from_loop Orchestrator)


# --- Read this Session's transcript --------------------------------------

# Prints "yes" when the user typed /vdd:vdd-<skill> or /vdd-<skill> in this
# Session. Lines that do not parse, such as a half-written last line, are
# skipped.
typed_skill() {
  [ -f "$transcript" ] || return 0
  jq -R -r \
    --arg plugin "<command-name>/vdd:vdd-$1</command-name>" \
    --arg bare "<command-name>/vdd-$1</command-name>" \
    'fromjson? | objects | select(.type == "user")
     | .message | objects | .content | strings
     | select(contains($plugin) or contains($bare)) | "yes"' \
    "$transcript" 2>/dev/null | head -n 1
}

last_title() {
  [ -f "$transcript" ] || return 0
  jq -R -r \
    'fromjson? | objects | select(.type == "custom-title")
     | .customTitle | strings' \
    "$transcript" 2>/dev/null | tail -n 1
}


# --- Decide which name this Session should carry -------------------------

target=""

case $prompt in
  /vdd:vdd-orchestrator* | /vdd-orchestrator*) target=$orchestrator_name ;;
esac

if [ -z "$target" ] && [ -n "$(typed_skill orchestrator)" ]; then
  target=$orchestrator_name
elif [ -z "$target" ] && [ -n "$(typed_skill start-loop)" ]; then
  target=$planner_name
elif [ -z "$target" ]; then
  previous=$(last_title)
  if [ -n "$previous" ] &&
     { [ "$previous" = "$planner_name" ] ||
       [ "$previous" = "$orchestrator_name" ]; }; then
    target=$previous
  fi
fi

[ -n "$target" ] || exit 0


# --- Rename only when the live name differs ------------------------------

# transcript_path is <config dir>/projects/<project>/<id>.jsonl, so the
# registry sits in <config dir>/sessions whatever the config dir is.
current_name=""
if [ -n "$transcript" ] && [ -n "$session_id" ]; then
  sessions_dir="$(dirname "$(dirname "$(dirname "$transcript")")")/sessions"
  current_name=$(
    for entry in "$sessions_dir"/*.json; do
      [ -f "$entry" ] || continue
      jq -r --arg id "$session_id" \
        'objects | select(.sessionId == $id) | .name | strings' \
        "$entry" 2>/dev/null
    done | head -n 1
  )
fi

[ "$current_name" = "$target" ] && exit 0

jq -n -c --arg title "$target" \
  '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", sessionTitle: $title}}' \
  2>/dev/null
exit 0
