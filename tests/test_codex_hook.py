"""Seam 1 for codex-stop, and seam 3: the hook strings as they ship.

The cases of the 0.15 fixture suites (vdd-codex-stop.test.sh and .ps1) live
on here, numbered as they were where they still apply. The hook finds its
loop through the Session's armed file and reads no Loop file.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import unittest

from vddtest import REPO, SCRIPTS, WINDOWS, ToolTest

ID = "019a0001-aaaa-7bbb-8ccc-0123456789ab"
OTHER = "019a0002-dddd-7eee-8fff-0123456789ab"
P1 = "VDD Planner: .scratch/feat/ ready, round 1. Read spec.md and issues/."
R1 = "VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 0 blocker, 1 major, 0 minor. Read it."
TRACKER = os.path.join(".scratch", "feat")




def stop_input(session, message="Done."):
    return json.dumps(
        {"session_id": session, "turn_id": "t1", "hook_event_name": "Stop",
         "stop_hook_active": False, "last_assistant_message": message},
        ensure_ascii=False,
    ).encode("utf-8")


class CodexHookTest(ToolTest):
    def setUp(self):
        ToolTest.setUp(self)
        os.makedirs(self.box.path(TRACKER))
        # The reason names the Shared copy; with one there, the Next: sweep
        # runs the step the Role would run.
        shutil.copytree(SCRIPTS, self.box.shared, ignore=shutil.ignore_patterns("__pycache__"))

    def loop(self, harness="Codex"):
        self.box.write_loop("feat", harness=harness)

    def arm(self, session, text, tracker=TRACKER):
        self.box.write(os.path.join(tracker, "codex-armed-" + session), text)

    def armed(self, session, role="Orchestrator", count=0, tracker=TRACKER):
        self.arm(session, "vdd codex-armed 1\n%s %d\n" % (role, count), tracker)

    def ring(self, to, line, tracker=TRACKER):
        path = self.box.path(tracker, "doorbells")
        with open(path, "ab") as handle:
            handle.write(("10:00:00 to: %s %s\n" % (to, line)).encode("utf-8"))

    def hook(self, stdin, env=None):
        return self.box.run("codex-stop", stdin=stdin, env=env or self.box.env(
            VDD_WAIT_POLL_SECONDS="0.05", VDD_WAIT_TIMEOUT_SECONDS="0.5"))

    def project_files(self):
        out = {}
        for directory, _, files in os.walk(self.box.proj):
            for name in files:
                path = os.path.join(directory, name)
                with open(path, "rb") as handle:
                    out[os.path.relpath(path, self.box.proj)] = handle.read()
        return out

    def assertSilent(self, result, before=None):
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.data, b"", result)
        if before is not None:
            self.assertEqual(self.project_files(), before)

    def assertBlock(self, result):
        self.assertEqual(result.code, 0, result)
        self.assertEqual(len(result.lines), 1, result)
        decision = json.loads(result.lines[0])
        self.assertEqual(sorted(decision), ["decision", "reason"])
        self.assertEqual(decision["decision"], "block")
        result.data.decode("ascii")
        return decision["reason"]

    def gone(self, session, tracker=TRACKER):
        return not os.path.exists(self.box.path(tracker, "codex-armed-" + session))

    def test_help_explains_the_hook_and_claims_nothing(self):
        """The top-level help lists codex-stop as a group, so its --help
        answers before the hook reads standard input."""
        self.loop()
        self.armed("s1")
        before = self.project_files()
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                result = self.box.run("codex-stop", flag, stdin=stop_input("s1"))
                self.assertEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("Codex runs it at a turn end", result.text)
                self.assertNext(result, "a Role never runs codex-stop")
                self.assertEqual(self.project_files(), before)

    # --- the 0.15 cases ---

    def test_01_no_scratch_silent(self):
        os.rmdir(self.box.path(TRACKER))
        os.rmdir(self.box.path(".scratch"))
        self.assertSilent(self.hook(stop_input(ID)), {})

    def test_02_the_loop_file_is_not_read(self):
        """Only a Codex wait writes an armed file, so the hook checks no
        Harness and reads no Loop file: the armed file alone finds the loop."""
        self.loop("Cursor")
        self.armed(ID)
        self.ring("Orchestrator", P1)
        self.assertBlock(self.hook(stop_input(ID)))
        os.remove(self.box.path(TRACKER, "loop.md"))
        self.armed(ID)
        self.assertBlock(self.hook(stop_input(ID)))

    def test_03_nothing_armed_silent(self):
        self.loop()
        self.ring("Orchestrator", P1)
        before = self.project_files()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_04_another_sessions_armed_file_untouched(self):
        self.loop()
        self.armed(OTHER)
        self.ring("Orchestrator", P1)
        before = self.project_files()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_05_armed_with_a_doorbell_waiting_blocks_and_claims_its_own_file(self):
        self.loop()
        self.armed(ID)
        self.armed(OTHER, "Planner", 0)
        self.ring("Orchestrator", P1)
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertIn("doorbell take --role Orchestrator --harness codex --slug feat", reason)
        self.assertTrue(self.gone(ID))
        self.assertFalse(self.gone(OTHER))

    def test_the_loop_is_the_armed_file_s_directory(self):
        """Two loops, each with a Session armed: each Session's hook finds
        only its own file and names its own loop."""
        other = os.path.join(".scratch", "two")
        self.armed(ID)
        self.armed(OTHER, tracker=other)
        self.ring("Orchestrator", P1)
        self.ring("Orchestrator", "VDD Planner: .scratch/two/ ready, round 1. Read spec.md and issues/.", tracker=other)
        reason = self.assertBlock(self.hook(stop_input(OTHER)))
        self.assertIn("--slug two", reason)
        self.assertTrue(self.gone(OTHER, other))
        self.assertFalse(self.gone(ID))

    def test_two_armed_files_for_one_session_act_on_the_newer_and_delete_both(self):
        other = os.path.join(".scratch", "two")
        self.armed(ID, tracker=other)
        self.armed(ID)
        old = self.box.path(other, "codex-armed-" + ID)
        os.utime(old, (1000000000, 1000000000))
        self.ring("Orchestrator", P1)
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertIn("--slug feat", reason)
        self.assertTrue(self.gone(ID))
        self.assertTrue(self.gone(ID, other))

    def test_06_several_lines_beyond_the_count_block_once(self):
        self.loop()
        self.armed(ID, "Planner", 1)
        self.ring("Planner", R1)
        self.ring("Orchestrator", P1)
        self.ring("Planner", "VDD Plan-Reviewer: PLAN-REVIEW.md SIGNED OFF, round 3.")
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertIn("A Doorbell for the Planner is waiting", reason)

    @unittest.skipIf(WINDOWS, "a quote and a tab in a directory name are POSIX-only")
    def test_07_08_the_reason_is_ascii_json_with_no_control_characters(self):
        """Escaped into valid JSON, ASCII only, control characters dropped, so
        it reads back unchanged through json.loads: the reason names the Shared
        copy's path, and a quote, a backslash, a tab or a non-ASCII letter in
        it must not break the block decision Codex parses. The 0.15 hook
        dropped control characters and escaped the reason too (e89c906)."""
        data = os.path.join(self.box.root, 'da"t\\a\té')
        os.makedirs(data)
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        env = self.box.env(XDG_DATA_HOME=data, VDD_WAIT_TIMEOUT_SECONDS="0.5")
        reason = self.assertBlock(self.hook(stop_input(ID), env=env))
        self.assertIn('da"t\\aé', reason)
        self.assertFalse(any(ord(c) < 32 for c in reason))

    def test_09_timeout_blocks_with_timeout(self):
        self.loop()
        self.armed(ID, "Planner", 0)
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertTrue(reason.startswith("TIMEOUT"), reason)
        self.assertIn("Ask the user whether to keep waiting", reason)
        self.assertTrue(self.gone(ID))

    def test_10_12_a_malformed_armed_file_is_claimed_and_no_block(self):
        """The claim takes a malformed armed file too, so it cannot fire on a
        later turn end: the 0.15 hook deleted the armed file before it waited,
        whatever it held (e89c906)."""
        self.loop()
        self.ring("Orchestrator", P1)
        for text in ("vdd codex-armed 1\nCoder 0\n", "vdd codex-armed 1\nOrchestrator x\n",
                     "vdd codex-armed 1\nOrchestrator\n", "vdd codex-armed 9\nOrchestrator 0\n",
                     "Orchestrator 0\n", ""):
            with self.subTest(text=text):
                self.arm(ID, text)
                self.assertSilent(self.hook(stop_input(ID)))
                self.assertTrue(self.gone(ID))

    def test_13_14_no_or_empty_session_id_silent(self):
        self.loop()
        self.armed(ID)
        self.arm("", "vdd codex-armed 1\nOrchestrator 0\n")
        self.ring("Orchestrator", P1)
        before = self.project_files()
        self.assertSilent(self.hook(b'{"turn_id":"t1","hook_event_name":"Stop"}'), before)
        self.assertSilent(self.hook(stop_input("")), before)

    # --- new cases ---

    def test_garbage_on_stdin_exits_zero_silently(self):
        self.loop()
        self.armed(ID)
        self.assertSilent(self.hook(b"garbage"))
        self.assertFalse(self.gone(ID))

    def test_the_session_id_filter(self):
        """session_id becomes part of a file name, so only [0-9A-Za-z_-]+ is
        accepted and ../ never reaches the disk, as in the 0.15 hook
        (e89c906)."""
        self.loop()
        self.box.write(os.path.join(".scratch", "codex-armed-x"), "vdd codex-armed 1\nOrchestrator 0\n")
        self.ring("Orchestrator", P1)
        before = self.project_files()
        for session in ("../codex-armed-x", "a b", "a/b", "é"):
            with self.subTest(session=session):
                self.assertSilent(self.hook(stop_input(session)), before)

    def test_a_right_double_quote_in_the_last_message(self):
        """Stdin decoded in the Windows code page broke on a U+201D in
        last_assistant_message; it is read as bytes and decoded UTF-8, as the
        0.15 hook on native Windows read it (0a606c2)."""
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        self.assertBlock(self.hook(stop_input(ID, "Done ”here”.")))

    def test_a_015_armed_file_is_ignored(self):
        """A 0.15 hook that survives reads armed-<id>; the new hook reads
        codex-armed-<id>, so the old one finds nothing and cannot take the new
        arm, and the new one ignores the old file."""
        self.loop()
        self.box.write(os.path.join(TRACKER, "armed-" + ID), "Orchestrator 0\n")
        self.ring("Orchestrator", P1)
        before = self.project_files()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_an_error_inside_exits_zero(self):
        """Exit 0 on every path, exceptions included: Codex reads exit 2 as a
        block and repeats it without limit (ADR 0008). A wait that fails after
        the claim took the armed file blocks once with the failure and the
        hand-relay step, naming the Shared copy: a silent exit left the
        Session idle with no wait armed."""
        self.loop()
        self.armed(ID)
        self.box.write(os.path.join(TRACKER, "doorbells"), "# vdd doorbells 99\n")
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertTrue(reason.startswith(".scratch/feat/doorbells has format version 99, which this copy of the "
                                          "VDD tool does not know. Next: Tell the user in one line that this wait "
                                          "cannot run, so they paste the Planner's next Doorbell here."), reason)
        self.assertIn('%s" doorbell take --role Orchestrator --pasted' % os.path.join(self.box.shared, "vdd.py"),
                      reason)
        self.assertTrue(self.gone(ID))
        self.assertSilent(self.hook(stop_input(ID)))

    def test_an_unreadable_state_file_after_the_claim_blocks_once(self):
        """A state file the wait cannot read, after the claim took the armed
        file, blocks with the read failure and the hand-relay step, once."""
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        os.makedirs(self.box.path(TRACKER, "doorbell-state-orchestrator"))
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertTrue(reason.startswith("The wait could not read its files: "
                                          ".scratch/feat/doorbell-state-orchestrator: "), reason)
        self.assertRegex(reason, r"\S\. Next: Tell the user in one line that this wait cannot run")
        self.assertIn("--pasted", reason)
        self.assertTrue(self.gone(ID))
        self.assertSilent(self.hook(stop_input(ID)))

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_a_failure_before_the_claim_stays_silent(self):
        """A claim that cannot create its marker ends the turn as usual: before
        the claim nothing is taken, so blocking would stop an unrelated turn
        end."""
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        tracker = self.box.path(TRACKER)
        os.chmod(tracker, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, tracker, stat.S_IRWXU)
        self.assertSilent(self.hook(stop_input(ID)))
        self.assertFalse(self.gone(ID))

    def test_two_turn_ends_racing_claim_the_arm_once(self):
        """Two turn ends can race for the same armed file; only one of them
        creates the claim marker, so only one of them waits. The 0.15 hook deleted the armed
        file before it waited (e89c906), which left a window between its read
        and its delete."""
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        results = []
        env = self.box.env(VDD_WAIT_POLL_SECONDS="0.05", VDD_WAIT_TIMEOUT_SECONDS="0.5")
        threads = [threading.Thread(target=lambda: results.append(self.hook(stop_input(ID), env=env))) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        blocks = [r for r in results if r.data]
        self.assertEqual(len(blocks), 1, results)
        self.assertTrue(all(r.code == 0 for r in results))

    def test_a_marker_a_killed_hook_left_blocks_no_later_wait(self):
        """A hook killed between its claim and its cleanup leaves its claim
        marker behind; with the marker kept, every later wait of the Session
        was taken as already claimed and the Doorbell was never waited for.
        Arming a wait clears the marker, so the next turn end blocks once."""
        self.loop()
        self.armed(ID)
        marker = self.box.path(TRACKER, "codex-claim-" + ID)
        self.box.write(os.path.join(TRACKER, "codex-claim-" + ID), "")
        self.ring("Orchestrator", P1)
        armed = self.box.run("doorbell", "wait", "--role", "Orchestrator", "--harness", "codex", "--slug", "feat",
                             env=self.box.env(CODEX_THREAD_ID=ID))
        self.assertEqual(armed.code, 0, armed)
        self.assertFalse(os.path.exists(marker))
        self.assertBlock(self.hook(stop_input(ID)))
        self.assertTrue(self.gone(ID))
        self.assertFalse(os.path.exists(marker))
        self.assertSilent(self.hook(stop_input(ID)))

    def test_a_turn_end_finding_the_wait_claimed_takes_nothing(self):
        """The claim marker says another turn end has this wait: this one
        exits 0 without blocking and without touching the armed file, so the
        wait is never taken by two turn ends."""
        self.loop()
        self.armed(ID)
        self.box.write(os.path.join(TRACKER, "codex-claim-" + ID), "")
        self.ring("Orchestrator", P1)
        before = self.project_files()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def pin(self, path):
        """Make deleting path fail, as a program holding it open does on
        Windows, and return the call that undoes it."""
        if WINDOWS:
            return open(path, "rb").close
        os.chflags(path, stat.UF_IMMUTABLE)
        return lambda: os.chflags(path, 0)

    @unittest.skipUnless(WINDOWS or hasattr(os, "chflags"), "a file that refuses its delete needs Windows or chflags")
    def test_an_armed_file_that_cannot_be_deleted_is_claimed_once(self):
        """The claim removed its marker even when the armed file outlived it,
        so the next turn end claimed the same wait again and blocked for the
        whole timeout on a Doorbell already taken. The marker now stays until
        the next arm."""
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        marker = self.box.path(TRACKER, "codex-claim-" + ID)
        release = self.pin(self.box.path(TRACKER, "codex-armed-" + ID))
        try:
            self.assertBlock(self.hook(stop_input(ID)))
            self.assertFalse(self.gone(ID))
            self.assertTrue(os.path.exists(marker))
            self.assertSilent(self.hook(stop_input(ID)))
        finally:
            release()

    @unittest.skipUnless(WINDOWS, "only Windows retries a refused delete")
    def test_an_armed_file_held_for_a_moment_is_still_deleted(self):
        """A delete refused for a moment, as a scanner briefly holding the file
        on Windows refuses it, is retried, so the claim ends as usual. POSIX
        reports a refused delete at once."""
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        timer = threading.Timer(1.0, self.pin(self.box.path(TRACKER, "codex-armed-" + ID)))
        timer.start()
        try:
            self.assertBlock(self.hook(stop_input(ID)))
        finally:
            timer.join()
        self.assertTrue(self.gone(ID))
        self.assertFalse(os.path.exists(self.box.path(TRACKER, "codex-claim-" + ID)))

    def test_the_hook_names_the_shared_copy(self):
        self.loop()
        self.armed(ID)
        self.ring("Orchestrator", P1)
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertIn(os.path.join(self.box.shared, "vdd.py"), reason)


class HookStringTest(ToolTest):
    """Seam 3: the hook strings read from .codex-plugin/plugin.json, run where
    Codex runs them, ${PLUGIN_ROOT} replaced as Codex replaces it."""

    def setUp(self):
        ToolTest.setUp(self)
        with open(os.path.join(REPO, ".codex-plugin", "plugin.json"), "rb") as handle:
            manifest = json.loads(handle.read().decode("utf-8"))
        self.handler = manifest["hooks"]["hooks"]["Stop"][0]["hooks"][0]
        self.bin = os.path.join(self.box.root, "bin")
        os.makedirs(self.bin)

    def command(self, root, windows=False):
        return self.handler["commandWindows" if windows else "command"].replace("${PLUGIN_ROOT}", root)

    def ready(self):
        self.box.write_loop("feat", harness="Codex")
        self.box.write(os.path.join(TRACKER, "codex-armed-" + ID), "vdd codex-armed 1\nOrchestrator 0\n")
        with open(self.box.path(TRACKER, "doorbells"), "wb") as handle:
            handle.write(("10:00:00 to: Orchestrator %s\n" % P1).encode())

    def stage_case(self, case):
        """One of the guard's three cases: no .scratch/, .scratch/ with a loop
        and nothing armed, one armed file."""
        shutil.rmtree(self.box.path(".scratch"), ignore_errors=True)
        if case == "unarmed":
            self.box.write_loop("feat", harness="Codex")
        elif case == "armed":
            self.ready()

    def posix(self, root, python, shell="sh", command=None):
        """Run command through <shell> -c with python3 on PATH being python."""
        target = os.path.join(self.bin, "python3")
        if os.path.lexists(target):
            os.remove(target)
        if python == "marker":
            with open(target, "w") as handle:
                handle.write("#!/bin/sh\ntouch '%s'\nexit 0\n" % os.path.join(self.box.root, "started"))
            os.chmod(target, 0o755)
        else:
            os.symlink(sys.executable, target)
        env = self.box.env(PATH=self.bin + os.pathsep + os.environ.get("PATH", ""))
        proc = subprocess.run([shell, "-c", command or self.command(root)], cwd=self.box.proj, env=env,
                              input=json.dumps({"session_id": ID}).encode(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=60)
        return proc

    @unittest.skipIf(WINDOWS, "Codex runs command, not commandWindows, on macOS and Linux")
    def test_command_starts_python_only_when_armed_in_every_shell(self):
        """Codex runs a hook under the Session's shell: sh, bash, or zsh, the
        macOS default."""
        started = os.path.join(self.box.root, "started")
        shells = [shell for shell in ("sh", "bash", "zsh") if shutil.which(shell)]
        self.assertIn("sh", shells)
        for shell in shells:
            for case in ("none", "unarmed", "armed"):
                with self.subTest(shell=shell, case=case):
                    self.stage_case(case)
                    if os.path.exists(started):
                        os.remove(started)
                    proc = self.posix(REPO, "marker", shell)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(os.path.exists(started), case == "armed")

    @unittest.skipIf(WINDOWS or not shutil.which("zsh"), "needs zsh")
    def test_a_bare_glob_guard_fails_under_zsh_with_nothing_armed(self):
        """Why the guard runs find: zsh aborts on an unmatched glob with exit
        1, which Codex shows as "Hook failed" at every turn end."""
        bare = 'set -- .scratch/*/codex-armed-*; [ ! -e "$1" ] || python3 x.py || true'
        for case in ("none", "unarmed"):
            with self.subTest(case=case):
                self.stage_case(case)
                proc = self.posix(REPO, "marker", "zsh", bare)
                self.assertNotEqual(proc.returncode, 0)

    @unittest.skipIf(WINDOWS, "Codex runs command, not commandWindows, on macOS and Linux")
    def test_command_missing_script_exits_zero(self):
        """python3 exits 2 on a missing script, which Codex reads as a block
        and repeats; the guard's || true keeps it at 0 (ADR 0008)."""
        self.ready()
        proc = self.posix(os.path.join(self.box.root, "gone"), "real")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")

    @unittest.skipIf(WINDOWS, "Codex runs command, not commandWindows, on macOS and Linux")
    def test_command_pending_doorbell_blocks(self):
        self.ready()
        proc = self.posix(REPO, "real")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["decision"], "block")

    def powershell(self, root):
        exe = shutil.which("powershell.exe") or shutil.which("powershell")
        if not exe or not shutil.which("py"):
            self.skipTest("needs powershell.exe and the py launcher")
        proc = subprocess.run([exe, "-NoProfile", "-Command", self.command(root, windows=True)],
                              cwd=self.box.proj, env=self.box.env(),
                              input=json.dumps({"session_id": ID}).encode(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=120)
        return proc.returncode, proc.stdout.replace(b"\r", b"")

    @unittest.skipUnless(WINDOWS, "Codex runs commandWindows on native Windows")
    def test_command_windows_nothing_armed_exits_zero_silently(self):
        for case in ("none", "unarmed"):
            with self.subTest(case=case):
                self.stage_case(case)
                code, out = self.powershell(REPO)
                self.assertEqual((code, out), (0, b""))

    @unittest.skipUnless(WINDOWS, "Codex runs commandWindows on native Windows")
    def test_command_windows_missing_script_exits_zero(self):
        self.ready()
        code, out = self.powershell(os.path.join(self.box.root, "gone"))
        self.assertEqual(code, 0)

    @unittest.skipUnless(WINDOWS, "Codex runs commandWindows on native Windows")
    def test_command_windows_pending_doorbell_blocks(self):
        """py -3 picks its own 3.x there, not the matrix Python, and PowerShell
        re-emits the output with CRLF, so the block decision is checked as
        Codex receives it through the shipped string."""
        self.ready()
        code, out = self.powershell(REPO)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
