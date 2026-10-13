"""Seam 1 for codex-stop, and seam 3: the hook strings as they ship.

The cases of the 0.15 fixture suites (vdd-codex-stop.test.sh and .ps1) live
on here, numbered as they were where they still apply.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import unittest

from vddtest import REPO, WINDOWS, ToolTest

ID = "019a0001-aaaa-7bbb-8ccc-0123456789ab"
OTHER = "019a0002-dddd-7eee-8fff-0123456789ab"
P1 = "VDD Planner: .scratch/feat/ ready, round 1. Read spec.md and issues/."
R1 = "VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 0 blocker, 1 major, 0 minor. Read it."
TRACKER = os.path.join(".scratch", "feat")


def loop_file(harness, tracker=True):
    text = "# VDD Loop\n\nFeature: feat\nBase branch: main\nFeature branch: feat\n"
    if tracker:
        text += "Tracker: .scratch/feat/\n"
    return text + "Minors: fix\nPR: no\nFresh Coder: never\nHarness: %s\n" % harness


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

    def loop(self, harness="Codex", tracker=True):
        self.box.write("LOOP.md", loop_file(harness, tracker))

    def arm(self, session, text):
        self.box.write(os.path.join(TRACKER, "codex-armed-" + session), text)

    def armed(self, session, role="Orchestrator", count=0):
        self.arm(session, "vdd codex-armed 1\n%s %d\n" % (role, count))

    def ring(self, to, line):
        path = self.box.path(TRACKER, "doorbells")
        with open(path, "ab") as handle:
            handle.write(("10:00:00 to: %s %s\n" % (to, line)).encode("utf-8"))

    def hook(self, stdin, env=None):
        return self.box.run("codex-stop", stdin=stdin, env=env or self.box.env(
            VDD_WAIT_POLL_SECONDS="0.05", VDD_WAIT_TIMEOUT_SECONDS="0.5"))

    def snapshot(self):
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
            self.assertEqual(self.snapshot(), before)

    def assertBlock(self, result):
        self.assertEqual(result.code, 0, result)
        self.assertEqual(len(result.lines), 1, result)
        decision = json.loads(result.lines[0])
        self.assertEqual(sorted(decision), ["decision", "reason"])
        self.assertEqual(decision["decision"], "block")
        result.data.decode("ascii")
        return decision["reason"]

    def gone(self, session):
        return not os.path.exists(self.box.path(TRACKER, "codex-armed-" + session))

    def test_help_explains_the_hook_and_claims_nothing(self):
        """The top-level help lists codex-stop as a group, so its --help
        answers before the hook reads standard input."""
        self.loop()
        self.armed("s1")
        before = self.snapshot()
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                result = self.box.run("codex-stop", flag, stdin=stop_input("s1"))
                self.assertEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("Codex runs it at a turn end", result.text)
                self.assertNext(result, "a Role never runs codex-stop")
                self.assertEqual(self.snapshot(), before)

    # --- the 0.15 cases ---

    def test_01_no_loop_file_silent_nothing_touched(self):
        self.armed(ID)
        self.ring("Orchestrator", P1)
        before = self.snapshot()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_02_another_harness_silent_nothing_touched(self):
        self.loop("Cursor")
        self.armed(ID)
        self.ring("Orchestrator", P1)
        before = self.snapshot()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_03_nothing_armed_silent(self):
        self.loop()
        self.ring("Orchestrator", P1)
        before = self.snapshot()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_04_another_sessions_armed_file_untouched(self):
        self.loop()
        self.armed(OTHER)
        self.ring("Orchestrator", P1)
        before = self.snapshot()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_05_armed_with_a_doorbell_waiting_blocks_and_claims_its_own_file(self):
        self.loop()
        self.armed(ID)
        self.armed(OTHER, "Planner", 0)
        self.ring("Orchestrator", P1)
        reason = self.assertBlock(self.hook(stop_input(ID)))
        self.assertIn("doorbell take --role Orchestrator --harness codex", reason)
        self.assertTrue(self.gone(ID))
        self.assertFalse(self.gone(OTHER))

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
        before = self.snapshot()
        self.assertSilent(self.hook(b'{"turn_id":"t1","hook_event_name":"Stop"}'), before)
        self.assertSilent(self.hook(stop_input("")), before)

    def test_15_codex_with_no_tracker_line_silent(self):
        self.loop(tracker=False)
        self.armed(ID)
        self.ring("Orchestrator", P1)
        before = self.snapshot()
        self.assertSilent(self.hook(stop_input(ID)), before)

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
        before = self.snapshot()
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
        arm, and the new one ignores the old file (spec, user story 16)."""
        self.loop()
        self.box.write(os.path.join(TRACKER, "armed-" + ID), "Orchestrator 0\n")
        self.ring("Orchestrator", P1)
        before = self.snapshot()
        self.assertSilent(self.hook(stop_input(ID)), before)

    def test_an_error_inside_exits_zero(self):
        """Exit 0 on every path, exceptions included: Codex reads exit 2 as a
        block and repeats it without limit (ADR 0008)."""
        self.loop()
        self.armed(ID)
        self.box.write(os.path.join(TRACKER, "doorbells"), "# vdd doorbells 99\n")
        self.assertSilent(self.hook(stop_input(ID)))

    def test_two_turn_ends_racing_claim_the_arm_once(self):
        """Two turn ends can race for the same armed file; the claim renames it
        away first, so only one of them waits. The 0.15 hook deleted the armed
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
        os.makedirs(self.box.path(TRACKER))
        self.bin = os.path.join(self.box.root, "bin")
        os.makedirs(self.bin)

    def command(self, root, windows=False):
        return self.handler["commandWindows" if windows else "command"].replace("${PLUGIN_ROOT}", root)

    def ready(self):
        self.box.write("LOOP.md", loop_file("Codex"))
        self.box.write(os.path.join(TRACKER, "codex-armed-" + ID), "vdd codex-armed 1\nOrchestrator 0\n")
        with open(self.box.path(TRACKER, "doorbells"), "wb") as handle:
            handle.write(("10:00:00 to: Orchestrator %s\n" % P1).encode())

    def posix(self, root, python):
        """Run command through sh -c with python3 on PATH being python."""
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
        proc = subprocess.run(["sh", "-c", self.command(root)], cwd=self.box.proj, env=env,
                              input=json.dumps({"session_id": ID}).encode(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=60)
        return proc

    @unittest.skipIf(WINDOWS, "Codex runs command, not commandWindows, on macOS and Linux")
    def test_command_no_loop_file_starts_no_python(self):
        proc = self.posix(REPO, "marker")
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.box.root, "started")))
        self.ready()
        self.posix(REPO, "marker")
        self.assertTrue(os.path.exists(os.path.join(self.box.root, "started")))

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
    def test_command_windows_no_loop_file_exits_zero_silently(self):
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
