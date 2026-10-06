#!/bin/sh
# vdd-codex-stop.sh: the Codex Stop hook of Vibe Driven Development.
#
# It waits on the Doorbell file for a Codex Planner or Orchestrator, so the
# Session spends no model turn while it waits. Setup installs it into
# ${XDG_DATA_HOME:-$HOME/.local/share}/vdd/, beside doorbell-wait.sh, and the
# user's ~/.codex/hooks.json runs it with sh at every turn end of a root
# Codex Session. It ships once, in the vdd-setup skill's references, at mode
# 644, and is never made executable. Plain POSIX sh: it needs no jq.
#
# Reads: LOOP.md in the current directory, which Codex sets to the Session's
#   cwd; the hook input on stdin, for its session_id; and the armed file
#   <tracker>/armed-<session_id>, one line "<Role> <armed count>", which the
#   Role writes before its turn ends when it expects a Doorbell.
# Deletes: that armed file, and no other, before it waits.
# Runs: sh doorbell-wait.sh <tracker>/doorbells <Role> <armed count>, from
#   this script's own directory.
# Prints: {"decision":"block","reason":"<line>"}, the newest line the wait
#   printed or TIMEOUT, so Codex continues the Session with that line as its
#   prompt. Prints nothing when the cwd holds no Codex loop, when nothing is
#   armed for this Session, or when the wait exits non-zero.
# Exits 0 on every path.

# The fast path, shell builtins only: most turn ends on a machine are in a
# project that holds no Codex loop, and they start no process here.
[ -f LOOP.md ] || exit 0

codex=
tracker=
while IFS= read -r line || [ -n "$line" ]; do
  case $line in
    'Harness: Codex' | 'Harness: Codex'[!A-Za-z0-9_-]*) codex=yes ;;
    'Tracker: '*) tracker=${line#'Tracker: '} ;;
  esac
done < LOOP.md

[ "$codex" = yes ] || exit 0

# The tracker path, trailing blanks and one trailing slash dropped.
tab=$(printf '\t')
cr=$(printf '\r')
while :; do
  case $tracker in
    *' ' | *"$tab" | *"$cr") tracker=${tracker%?} ;;
    *) break ;;
  esac
done
tracker=${tracker%/}
[ -n "$tracker" ] || exit 0

nl='
'

# The session_id from the hook input. The character set keeps the id a plain
# file name, and an empty or missing id exits here, so no file named armed-
# is ever claimed.
session_id=$(sed -n 's/.*"session_id": *"\([0-9A-Za-z_-]*\)".*/\1/p')
case $session_id in
  '' | *"$nl"*) exit 0 ;;
esac

armed="$tracker/armed-$session_id"
[ -f "$armed" ] || exit 0

role=
count=
read -r role count rest < "$armed"
rm -f "$armed"

case $0 in
  */*) here=${0%/*} ;;
  *) here=. ;;
esac

# Quoted, so an empty Role or count is still an argument the wait rejects,
# never a two-argument call that would run its count form.
out=$(sh "$here/doorbell-wait.sh" "$tracker/doorbells" "$role" "$count") || exit 0

# The Role acts on the newest line only.
line=${out##*"$nl"}
[ -n "$line" ] || exit 0

# Control characters dropped, then \ and " escaped, so the reason is a valid
# JSON string.
reason=$(printf '%s' "$line" | LC_ALL=C tr -d '\000-\037\177' |
  LC_ALL=C sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')

printf '{"decision":"block","reason":"%s"}\n' "$reason"
exit 0
