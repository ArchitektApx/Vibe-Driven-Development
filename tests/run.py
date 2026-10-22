"""Run the test suite in parallel, one test class per worker process.

    python3 -B tests/run.py [--update-goldens] [-s <start directory>]

It discovers as `unittest discover -s tests` does, runs each test class in
its own `python -B -m unittest` process, os.cpu_count() at a time, the
longest classes first by the timings of the last run (by test count when
there are none), prints a failing class's whole output and a summary, and
exits non-zero on any failure or error. It fills the bytecode prefix once and
passes it to every worker through VDD_TEST_PYCACHE, and removes it at the
end. --update-goldens sets VDD_UPDATE_GOLDENS=1, so the golden tests write
their files. Plain `python3 -B -m unittest discover -s tests` keeps working.
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
# Classes that flake under parallel load run alone, after the rest.
SERIAL = ()


def timings_path(start):
    """The timing record of a start directory, kept outside the repository."""
    key = re.sub(r"[^A-Za-z0-9]+", "-", os.path.realpath(start)).strip("-")[-80:]
    return os.path.join(tempfile.gettempdir(), "vdd-test-timings-%s.json" % key)


def classes(start):
    """Every test class discovery finds under start, as (target, count): the
    target is module.Class, or the module name for a module that failed to
    load, which its own run reports."""
    suite = unittest.defaultTestLoader.discover(start, top_level_dir=start)
    counts = {}

    def walk(item):
        if isinstance(item, unittest.TestSuite):
            for sub in item:
                walk(sub)
            return
        if type(item).__name__ == "_FailedTest":
            target = item._testMethodName
        else:
            target = item.id().rsplit(".", 1)[0]
        counts[target] = counts.get(target, 0) + 1

    walk(suite)
    return sorted(counts.items())


def run_class(start, target, env):
    began = time.monotonic()
    proc = subprocess.run([sys.executable, "-B", "-m", "unittest", target], cwd=start, env=env,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return target, proc.returncode, proc.stdout.decode("utf-8", "replace"), time.monotonic() - began


def counted(output):
    """(tests, failures, errors, skipped) from a unittest run's last lines."""
    ran = re.search(r"^Ran (\d+) tests?", output, re.M)
    numbers = dict((key, int(value)) for key, value in re.findall(r"(failures|errors|skipped)=(\d+)", output))
    return (int(ran.group(1)) if ran else 0, numbers.get("failures", 0), numbers.get("errors", 0),
            numbers.get("skipped", 0))


def main(argv):
    parser = argparse.ArgumentParser(description="Run the test suite in parallel.")
    parser.add_argument("--update-goldens", action="store_true", help="write the golden files instead of comparing")
    parser.add_argument("-s", "--start", default=HERE, help="the test directory, tests/ by default")
    options = parser.parse_args(argv)
    start = os.path.abspath(options.start)
    sys.path.insert(0, start)
    began = time.monotonic()
    found = classes(start)

    env = dict(os.environ)
    sys.path.insert(0, HERE)
    import vddtest  # noqa: E402  fills the bytecode prefix, removed at this process's exit
    env["VDD_TEST_PYCACHE"] = vddtest.PYCACHE
    if options.update_goldens:
        env["VDD_UPDATE_GOLDENS"] = "1"

    record = timings_path(start)
    try:
        with open(record) as handle:
            timed = json.load(handle)
    except (OSError, ValueError):
        timed = {}
    order = sorted(found, key=lambda item: (-timed.get(item[0], 0.0), -item[1], item[0]))
    parallel = [target for target, _ in order if target not in SERIAL]
    serial = [target for target, _ in order if target in SERIAL]

    results = []
    workers = os.cpu_count() or 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(lambda target: run_class(start, target, env), parallel):
            results.append(result)
    for target in serial:
        results.append(run_class(start, target, env))

    totals = [0, 0, 0, 0]
    failed = []
    for target, code, output, seconds in results:
        timed[target] = round(seconds, 2)
        numbers = counted(output)
        totals = [a + b for a, b in zip(totals, numbers)]
        if code != 0:
            failed.append(target)
            sys.stdout.write("=" * 70 + "\nFAILED CLASS: %s\n%s\n" % (target, output.rstrip("\n")))
    try:
        with open(record, "w") as handle:
            json.dump(timed, handle, indent=0, sort_keys=True)
    except OSError:
        pass
    sys.stdout.write("Ran %d tests in %d classes in %.1fs on %d workers: %d failures, %d errors, %d skipped.\n"
                     % (totals[0], len(results), time.monotonic() - began, workers, totals[1], totals[2], totals[3]))
    if failed:
        sys.stdout.write("FAILED: %s\n" % ", ".join(failed))
        return 1
    sys.stdout.write("OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
