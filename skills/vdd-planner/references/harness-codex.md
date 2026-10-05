# Planner on Codex

- **Typed skill names.** Where you ask the user to invoke a skill, give the
  form they type: `$<name>` for a Borrowed skill, such as `$grill-with-docs`
  or `$to-tickets .scratch/<slug>/spec.md`, and `$vdd:vdd-<role>` for a VDD
  skill, such as `$vdd:vdd-setup`.
- **The Orchestrator launch.** `codex --no-daemon` in a terminal in this
  repository, then `$vdd:vdd-orchestrator` in that Session. Without
  `--no-daemon`, Codex runs the Session in its shared background server, and
  quitting the terminal leaves a running turn and its hosted Roles working.
- **Delivering a Doorbell.** You ring and wait through the Doorbell file:
  ring as the Doorbell file for your platform that `SKILL.md` links says, and
  wait as "The wait" below says. Nothing confirms that the Orchestrator's
  Session is reachable, so every ring also prints, worded: "If the
  Orchestrator's Session does not wake, paste this into it:" followed by the
  exact Doorbell.
- **Round 1.** The Orchestrator reads your round-1 Doorbell from the Doorbell
  file when it starts. In place of "Paste the Doorbell below into it once it
  is up", say: "It picks up the Doorbell below from the Doorbell file; paste
  it in only if it does not start the review."
- **The wait.** A background shell cannot wake an idle Codex Session, so the
  `Stop` hook Setup installs waits for you. This rule replaces the arming
  rules of "Your wait" in the Doorbell file for your platform:
  end every turn in which you expect a Doorbell by writing your armed file,
  `.scratch/<feature-slug>/armed-<id>`, holding the one line
  `Planner <count>`, where `<count>` is the count you last acted on as that
  file defines it. `<id>` is this Session's thread id: read it once with
  `printf '%s\n' "$CODEX_THREAD_ID"`, on native Windows with
  `$env:CODEX_THREAD_ID`, and write it out in full after that. Write it with
  one shell command:

  ```sh
  printf 'Planner %s\n' <count> > .scratch/<feature-slug>/armed-<id>
  ```

  On native Windows, where Codex gives you PowerShell:

  ```powershell
  [IO.File]::WriteAllText((Join-Path (Get-Location).Path '.scratch/<feature-slug>/armed-<id>'), 'Planner <count>' + "`n")
  ```

  That writes the one line ending in LF, as UTF-8 with no byte order mark,
  which the hook reads as plain text. Never write it with `>`, which writes
  UTF-16 in Windows PowerShell 5.1.

  Write none in a turn in which you expect no Doorbell: after the plan
  Sign-off, and in a turn that ends asking the user a question, whose answer
  the hook would hold back until it exits. Writing the file again in a later
  turn is harmless: the hook claims it at most once per turn end. With
  `CODEX_THREAD_ID` empty you cannot arm: say so in one line and fall back to
  hand relay, as "When the script cannot run" says.
- **How the wait wakes you.** When your turn ends, the hook claims your armed
  file, waits on the Doorbell file with no model turn, and continues this
  Session with the newest Doorbell line, or `TIMEOUT`, as your next prompt.
  Handle it as a line your wait printed, under "On wake" in
  the Doorbell file for your platform, and `TIMEOUT` as that file says. A
  hook that is missing or untrusted never wakes you, and the line the
  Orchestrator printed is the fallback.
- **Esc and typed prompts.** Esc ends the hook's wait together with the turn.
  A prompt the user types while the hook waits arrives when it exits, and Esc
  sends it at once. Either way the rule above covers it: the next turn ends
  with your armed file written again.
- **A resume.** `codex resume --no-daemon` resumes a Session the user quit.
  The quit ended its turn and its hook wait, and "The wait" above re-arms it
  with no word from the user: the first turn you end after it writes your
  armed file.

Trust your live tools over this file when they disagree.
