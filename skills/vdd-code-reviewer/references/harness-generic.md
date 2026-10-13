# Code-Reviewer on a Harness VDD does not know

- **Which `code-review` to use.** The `code-review` whose description names
  "Standards" and "Spec". Another skill can carry the same bare name, so read
  the description of each hit.
- **The `code-review` sub-agents.** Spawn both with your Harness's subagent
  tool, side by side where it can, in a form whose calls return with the
  reports inside your turn.
- **Typed skill names.** Where you ask the user to invoke a skill, give its
  bare name: `setup-matt-pocock-skills`, `vdd-start-loop`.
- **A refused command.** When a sandbox refuses a command, rerun it once
  outside the sandbox if your tools offer a way; otherwise treat the refusal
  as a denial. On a denial, stop with one line naming the command and what it
  was for, and return `BLOCKED`.

Trust your live tools over this file when they disagree.
