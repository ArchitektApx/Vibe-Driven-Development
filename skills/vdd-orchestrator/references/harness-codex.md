# Orchestrator on Codex

- **Spawn and resume.** `collaboration.spawn_agent` spawns a fresh child.
  `collaboration.followup_task` addressed to that child resumes the same child
  with its context intact.
- **The Spawn prompt's skill name.** `$vdd:vdd-<role>`:
  `$vdd:vdd-plan-reviewer`, `$vdd:vdd-coder` or `$vdd:vdd-code-reviewer`. A
  child spawned with that name in its task loads the plugin's skill.
- **The return.** A child's completion arrives as a message of type
  `FINAL_ANSWER` with a `Task name`, a `Sender` and a `Payload`. The `Payload`
  is the return to parse.
- **The context size.** Codex reports none for a subagent, in any field of the
  spawn, wait, follow-up or completion results. The no-size path of "The
  Coder's context" applies from the first Coder return.
- **Starting with no review file on disk.** Arm at 0, as
  [`doorbell-file-posix.md`](doorbell-file-posix.md) says, by writing your
  armed file holding `Orchestrator 0` before your first turn ends, so the
  Planner's round-1 Doorbell already in the Doorbell file fires at once.
- **Relaying to the Planner.** Through the Doorbell file: ring as
  [`doorbell-file-posix.md`](doorbell-file-posix.md) says, and wait as "The
  wait" below says. Nothing confirms that the Planner's Session is reachable,
  so every relay also prints, worded: "If the Planner's Session does not
  wake, paste this into it:" followed by the exact Doorbell.
- **The wait.** A background shell cannot wake an idle Codex Session, so the
  `Stop` hook Setup installs waits for you. This rule replaces the arming
  rules of "Your wait" in [`doorbell-file-posix.md`](doorbell-file-posix.md):
  end every turn in which you expect a Planner Doorbell by writing your armed
  file, `.scratch/<feature-slug>/armed-<id>`, holding the one line
  `Orchestrator <count>`, where `<count>` is the count you last acted on as
  that file defines it. `<id>` is this Session's thread id: read it once with
  `printf '%s\n' "$CODEX_THREAD_ID"` and write it out in full after that.
  Write it with one shell command:

  ```sh
  printf 'Orchestrator %s\n' <count> > .scratch/<feature-slug>/armed-<id>
  ```

  Write none in a turn in which you expect no Planner Doorbell: after you
  relayed the plan Sign-off, and in a turn that ends asking the user a
  question, Model approval included, whose answer the hook would hold back
  until it exits. Writing the file again in a later turn is harmless: the
  hook claims it at most once per turn end. With `CODEX_THREAD_ID` empty you
  cannot arm: say so in one line and fall back to hand relay, as "When the
  script cannot run" says.
- **How the wait wakes you.** When your turn ends, the hook claims your armed
  file, waits on the Doorbell file with no model turn, and continues this
  Session with the newest Doorbell line, or `TIMEOUT`, as your next prompt.
  Handle it as a line your wait printed, under "On wake" in
  [`doorbell-file-posix.md`](doorbell-file-posix.md), and `TIMEOUT` as that
  file says. The hook runs at the end of your own turns only, never a hosted
  Role's. A hook that is missing or untrusted never wakes you, and the line
  the Planner printed is the fallback.
- **Esc and typed prompts.** Esc ends the hook's wait together with the turn.
  A prompt the user types while the hook waits arrives when it exits, and Esc
  sends it at once. Either way the rule above covers it: the next turn ends
  with your armed file written again.
- **A resume.** `codex resume --no-daemon` resumes a Session the user quit.
  The quit ended its turn, the Roles it hosted and its hook wait. Place the
  Workflow from the files as `restart.md` says, and "The wait" above re-arms
  you at the first turn you end.

Trust your live tools over this file when they disagree.
