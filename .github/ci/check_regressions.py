"""Regression gate for the Courier v1 integration trunk.

Compares recorded test outcomes (outcomes_plugin.py) with the known-failure
baseline in known_failures.json for one platform.

Exit status:
  0  no new failures (known failures and known flaky tests are tolerated)
  1  at least one test failed that is not recorded as known failing or flaky,
     or the pytest session itself was broken (collection error, crash, no tests)

Known failures that start passing are reported, so the baseline can be
tightened in the same integration step. If the platform has no baseline
entry yet, the gate runs in BASELINE mode: it reports and exits 0 so the
first baseline can be recorded from real CI evidence.
"""

import argparse
import json
import os
import sys

# pytest exit codes: 0 ok, 1 tests failed, 2 interrupted, 3 internal error,
# 4 usage error, 5 no tests collected
BROKEN_SESSION = {2, 3, 4, 5}


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--outcomes", required=True)
    parser.add_argument("--known", required=True)
    parser.add_argument("--platform", required=True, help="runner.os value: Linux, Windows or macOS")
    args = parser.parse_args(argv)

    if not os.path.exists(args.outcomes):
        print(f"GATE FAIL: outcomes file missing: {args.outcomes}")
        return 1
    data = load_json(args.outcomes)
    outcomes = data.get("outcomes", {})
    exitstatus = data.get("exitstatus")

    failed = sorted(node for node, result in outcomes.items() if result == "failed")
    passed = sorted(node for node, result in outcomes.items() if result == "passed")
    skipped = sorted(node for node, result in outcomes.items() if result == "skipped")

    lines = [f"## Courier v1 regression gate ({args.platform})", ""]
    lines.append(f"passed={len(passed)} failed={len(failed)} skipped={len(skipped)} pytest_exit={exitstatus}")

    known_all = load_json(args.known)
    baseline = known_all.get(args.platform)

    rc = 0
    if exitstatus in BROKEN_SESSION:
        lines.append(f"GATE FAIL: pytest session broken (exit {exitstatus}).")
        rc = 1

    if baseline is None:
        lines.append("")
        lines.append(f"BASELINE MODE: no known_failures entry for {args.platform}; reporting only.")
        for node in failed:
            lines.append(f"  FAILED {node}")
    else:
        known_failing = set(baseline.get("failing", []))
        known_flaky = set(baseline.get("flaky", []))
        new_failures = [node for node in failed if node not in known_failing and node not in known_flaky]
        now_passing = sorted(node for node in known_failing if outcomes.get(node) == "passed")
        missing = sorted(node for node in known_failing | known_flaky if node not in outcomes)
        flaky_failed = [node for node in failed if node in known_flaky]

        lines.append("")
        if new_failures:
            rc = 1
            lines.append("GATE FAIL: new failures not in the known baseline:")
            lines.extend(f"  NEW FAILURE {node}" for node in new_failures)
        else:
            lines.append("GATE PASS: no new failures.")
        if now_passing:
            lines.append("Known failures now PASSING (remove them from known_failures.json):")
            lines.extend(f"  NOW PASSING {node}" for node in now_passing)
        if flaky_failed:
            lines.append("Known flaky tests that failed this run (tolerated, still tracked):")
            lines.extend(f"  FLAKY {node}" for node in flaky_failed)
        if missing:
            lines.append("Known entries not present in this run (renamed or removed?):")
            lines.extend(f"  MISSING {node}" for node in missing)

    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
