# Orchestrator on Codex

- **Spawn and resume.** `collaboration.spawn_agent` spawns a fresh child.
  Pass `fork_turns: "none"` on every hosted-Role spawn, a Role's first spawn,
  a respawn and a spawn after a restart alike, so the Role starts without
  your conversation. `collaboration.followup_task` addressed to that child
  resumes the same child with its context intact, and takes no `fork_turns`.
- **The Spawn prompt's skill name.** `$vdd:vdd-<role>`:
  `$vdd:vdd-plan-reviewer`, `$vdd:vdd-coder` or `$vdd:vdd-code-reviewer`. A
  child spawned with that name in its task loads the plugin's skill.
- **The return.** After every spawn and every follow-up, wait for that child
  inside your turn with `collaboration.wait_agent`, a timeout of several
  minutes, and wait again until its completion arrives. A child that finishes
  after your turn has ended does not wake this Session. The completion
  arrives as a message of type `FINAL_ANSWER` with a `Task name`, a `Sender`
  and a `Payload`. The `Payload` is the return to parse.
- **The context size.** Codex reports none for a subagent, in any field of the
  spawn, wait, follow-up or completion results.
- **The wait.** A background shell cannot wake an idle Codex Session, so
  VDD's `Stop` hook waits for you. `doorbell wait` arms it and returns at
  once; then end your turn. End every turn in which you expect a Planner
  Doorbell that way. Run no `wait` in a turn that ends asking the user a
  question, Model approval included, whose answer the hook would hold back
  until it exits, nor after you relayed the plan Sign-off. Running it again
  in a later turn is harmless: the hook claims it at most once per turn end.
- **How the wait wakes you.** When your turn ends, the hook waits on the
  Doorbell file with no model turn, then continues this Session with the
  `take` command, or `TIMEOUT`, as your next prompt: run it, or on `TIMEOUT`
  do what it says. The hook runs at the end of your own turns only, never a
  hosted Role's. A hook that is missing or untrusted never wakes you, and the
  line the Planner printed is the fallback.
- **Esc and typed prompts.** Esc ends the hook's wait together with the turn.
  A prompt the user types while the hook waits arrives when it exits, and Esc
  sends it at once. Either way the rule above covers it: the next turn ends
  with `doorbell wait` run again.
- **A resume.** `codex resume --no-daemon` resumes a Session the user quit.
  The quit ended its turn, the Roles it hosted and its hook wait. Place the
  Workflow from the files as `restart.md` says, and "The wait" above re-arms
  you at the first turn you end.
- **A refused command.** When a sandbox refuses a command, rerun it once with
  `sandbox_permissions: "require_escalated"` on the same call. When that is
  denied too, stop with one line naming the command and what it was for; a
  wait falls back to hand relay instead.

Trust your live tools over this file when they disagree.
