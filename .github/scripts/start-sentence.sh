set -eo pipefail
rc=0
sentence='An Orchestrator hosts this Workflow.'
if ! grep -qF "You are the <Role> in a Vibe Driven Development loop. $sentence" skills/vdd-orchestrator/SKILL.md; then
  echo "skills/vdd-orchestrator/SKILL.md: the Spawn prompt lacks: $sentence"; rc=1
fi
for f in skills/vdd-plan-reviewer/SKILL.md skills/vdd-coder/SKILL.md skills/vdd-code-reviewer/SKILL.md; do
  if ! grep -qF "If the prompt that started you does not say \"$sentence\"" "$f"; then
    echo "$f: the start check lacks: $sentence"; rc=1
  fi
done
exit $rc
