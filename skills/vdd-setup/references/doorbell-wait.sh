#!/bin/sh
# doorbell-wait.sh: the Doorbell wait of the VDD Planner and Orchestrator.
#
# The Planner and the Orchestrator of Vibe Driven Development run this script
# on a Harness that rings through the Doorbell file. It reads the Doorbell
# file and writes nothing. Run it with sh, as `sh doorbell-wait.sh ...`. It
# ships at mode 644 and is never made executable.
#
# It ships once, in the vdd-setup skill's references. Setup installs a copy
# into ${XDG_DATA_HOME:-$HOME/.local/share}/vdd/, and the Roles run that copy.
#
# Two forms, chosen by the number of arguments:
#
#   sh doorbell-wait.sh <Doorbell file> <Role>
#     The count. Prints the number of lines in the Doorbell file addressed to
#     <Role> and exits 0. A missing Doorbell file counts as 0.
#
#   sh doorbell-wait.sh <Doorbell file> <Role> <armed count>
#     The wait. Reads the Doorbell file every 10 seconds. When the number of
#     lines addressed to <Role> rises above <armed count>, prints the lines
#     beyond <armed count>, oldest first, and exits 0. After 2700 seconds
#     without one, prints TIMEOUT and exits 0. Prints nothing until it exits.
#
# A line is addressed to <Role> when it starts with "HH:MM:SS to: <Role> ".
# <Role> is Planner or Orchestrator, and <armed count> is a non-negative
# integer. A wrong number of arguments or a bad value prints one usage line
# to stderr and exits 2. A Doorbell file that exists but cannot be read exits
# 1, after grep's own message on stderr.

# How often the wait reads the Doorbell file, and how long it waits in all.
poll_seconds=10
timeout_seconds=2700

usage() {
  echo "usage: sh doorbell-wait.sh <Doorbell file> Planner|Orchestrator [<armed count>]" >&2
  exit 2
}

case $# in
  2 | 3) ;;
  *) usage ;;
esac

doorbell_file=$1
role=$2

case $role in
  Planner | Orchestrator) ;;
  *) usage ;;
esac

if [ $# -eq 3 ]; then
  armed_count=$3
  # Digits only, and no leading zero, which shell arithmetic reads as octal.
  case $armed_count in
    '' | *[!0-9]* | 0?*) usage ;;
  esac
fi

# The address, written once for both forms: the time, then "to: <Role> ".
address="^[0-9][0-9]:[0-9][0-9]:[0-9][0-9] to: $role "

# Prints the number of lines addressed to the Role. A missing file counts as
# 0. Returns 1 when grep cannot read the file.
count_addressed() {
  if [ ! -e "$doorbell_file" ]; then
    echo 0
    return 0
  fi
  # grep -c exits 1 when nothing matches, which is a count of 0, not an error.
  grep -c -- "$address" "$doorbell_file"
  [ $? -le 1 ]
}

if [ $# -eq 2 ]; then
  count_addressed || exit 1
  exit 0
fi

waited=0
while :; do
  count=$(count_addressed) || exit 1
  if [ "$count" -gt "$armed_count" ]; then
    grep -- "$address" "$doorbell_file" | tail -n "+$((armed_count + 1))"
    exit 0
  fi
  if [ "$waited" -ge "$timeout_seconds" ]; then
    echo TIMEOUT
    exit 0
  fi
  sleep "$poll_seconds"
  waited=$((waited + poll_seconds))
done
