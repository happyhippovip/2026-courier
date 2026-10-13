"""Regression gate for the Courier v1 integration trunk.

Compares recorded test outcomes (outcomes_plugin.py) with the known-failure
baseline in known_failures.json for one platform.

Exit status:
  0  no new failures. Known failures that actually failed are tolerated.
     A flaky-list entry is tolerated only when that same node has at least
     one passed sample and one failed sample. One failed sample is a failure.
  1  at least one test failed that is not a known failure, a proven flake
     (pass and fail of the same node), or out of scope for this platform;
     or a known failure was skipped (skip is not a pass);
     or the pytest session itself was broken (collection error, crash, no tests);
     or the Golden zero-skip rule fired (see below)

Golden zero-skip rule (SKIPPED != PASS):
  tests/golden/** must never be skipped once the runtime modules they drive
  exist. The gate imports nothing: it probes importlib find_spec for the three
  modules whose absence the harness itself treats as the skip reason
  (courier_core.serve, courier_worker.host, adapters.synthetic).
  - any of the three unimportable: skips are legitimate ("waiting for v1
    components"); reported informationally, gate unaffected;
  - all three importable: any skipped Golden test fails the gate, because a
    skip would hide untested acceptance behavior;
  - zero Golden outcomes recorded at all: gate fails (suite deleted or never
    collected — absence of evidence is not PASS).

Known failures that start passing are reported, so the baseline can be
tightened in the same integration step. If the platform has no baseline
entry yet, the gate runs in BASELINE mode: it reports and exits 0 so the
first baseline can be recorded from real CI evidence.

A platform entry may declare "out_of_scope": node-id patterns (fnmatch) of
tests whose component cannot run on that platform by design (for example the
POSIX-only legacy Mac worker on Windows). Those tests still run; their
failures are reported separately and do not fail the gate on that platform.
They stay fully gated on the platforms where the component runs.

A platform entry may declare "skipped_platform": {"modules": [...], "reason"}.
These are test modules that skip themselves as a whole on that platform
(e.g. pytest.importorskip("fcntl") on Windows). The outcomes plugin records
such a module skip as "<module>::<collection>" = "skipped"; the gate reports
it as SKIPPED_PLATFORM (module skip), not as MISSING and not as a failure.
This category tolerates only that module-level skip: if any node of such a
module actually runs and fails, the gate fails (out_of_scope patterns do not
apply inside skipped_platform modules). A module that runs instead of
skipping is reported so the entry can be removed.

Every node may belong to exactly one category. A failing/flaky entry that
lies inside a skipped_platform module or matches an out_of_scope pattern is a
baseline inconsistency and fails the gate.
"""

import argparse
import fnmatch
import importlib.util
import json
import os
import sys

# pytest exit codes: 0 ok, 1 tests failed, 2 interrupted, 3 internal error,
# 4 usage error, 5 no tests collected
BROKEN_SESSION = {2, 3, 4, 5}


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def outcome_samples(result):
    """One outcome string, or several samples of the same node.

    The outcomes plugin records a single string per node. A list is accepted
    so a flake can be shown only when both a pass and a fail were recorded.
    """
    if isinstance(result, str):
        return (result,)
    if isinstance(result, (list, tuple)):
        return tuple(item for item in result if isinstance(item, str))
    return ()


# Modules whose absence is the harness's own documented reason for skipping
# the Golden suite (tests/golden/golden_harness.py REQUIRED_MODULES, minus
# courier_core.journal/projection which are already integrated).
GOLDEN_GATE_MODULES = (
    "courier_core.serve",
    "courier_worker.host",
    "adapters.synthetic",
)


def _repo_root():
    # .github/ci/check_regressions.py -> repository root.
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def golden_zero_skip_gate(outcomes):
    """Enforce SKIPPED != PASS for tests/golden/**.

    Returns (rc, lines). Probes importability with find_spec (imports
    nothing, runs nothing) against the repository under test.
    """
    lines = [""]
    golden = sorted(
        node for node in outcomes
        if node.split("::")[0].replace("\\", "/").startswith("tests/golden/")
    )
    if not golden:
        lines.append("GATE FAIL: no Golden outcomes recorded (suite deleted or never collected).")
        return 1, lines

    root = _repo_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    missing = []
    for name in GOLDEN_GATE_MODULES:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ValueError):
            missing.append(name)

    skipped = sorted(node for node in golden if outcomes.get(node) == "skipped")
    if missing:
        lines.append(
            "Golden suite waiting for v1 components: "
            + ", ".join(missing)
            + f" ({len(skipped)} skipped, tolerated)."
        )
        return 0, lines

    unjustified = [node for node in golden if outcomes.get(node) not in ("passed",)]
    if unjustified:
        lines.append("GATE FAIL: Golden zero-skip violated (all runtime modules present):")
        lines.extend(f"  GOLDEN NOT-PASSED {node} ({outcomes.get(node)})" for node in unjustified)
        return 1, lines
    lines.append(f"Golden zero-skip holds: {len(golden)} Golden tests passed, 0 skipped.")
    return 0, lines


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

    failed = sorted(node for node, result in outcomes.items() if "failed" in outcome_samples(result))
    passed = sorted(
        node for node, result in outcomes.items()
        if "passed" in outcome_samples(result) and "failed" not in outcome_samples(result)
    )
    skipped = sorted(
        node for node, result in outcomes.items()
        if outcome_samples(result) and set(outcome_samples(result)) == {"skipped"}
    )

    golden_rc, golden_lines = golden_zero_skip_gate(outcomes)

    lines = [f"## Courier v1 regression gate ({args.platform})", ""]
    lines.append(f"passed={len(passed)} failed={len(failed)} skipped={len(skipped)} pytest_exit={exitstatus}")

    known_all = load_json(args.known)
    baseline = known_all.get(args.platform)

    rc = 0
    new_failures, now_passing, scoped_out = [], [], []
    skipped_known, platform_skipped, overlap = [], [], []
    if exitstatus in BROKEN_SESSION:
        lines.append(f"GATE FAIL: pytest session broken (exit {exitstatus}).")
        rc = 1

    lines.extend(golden_lines)
    if golden_rc:
        rc = golden_rc

    if baseline is None:
        lines.append("")
        lines.append(f"BASELINE MODE: no known_failures entry for {args.platform}; reporting only.")
        for node in failed:
            lines.append(f"  FAILED {node}")
    else:
        known_failing = set(baseline.get("failing", []))
        known_flaky = set(baseline.get("flaky", []))
        scope_patterns = baseline.get("out_of_scope", {}).get("patterns", [])
        platform_modules = sorted(set(baseline.get("skipped_platform", {}).get("modules", [])))

        def module_of(node):
            return node.split("::")[0].replace("\\", "/")

        def in_platform_module(node):
            return module_of(node) in platform_modules

        def out_of_scope(node):
            if in_platform_module(node):
                return False  # skipped_platform tolerates only the module skip, never a failure
            return any(fnmatch.fnmatchcase(node, pattern) for pattern in scope_patterns)

        overlap = sorted(
            node for node in known_failing | known_flaky
            if in_platform_module(node) or any(fnmatch.fnmatchcase(node, p) for p in scope_patterns)
        )

        def samples(node):
            return outcome_samples(outcomes.get(node))

        proven_flaky = [
            node for node in failed
            if node in known_flaky and "passed" in samples(node) and "failed" in samples(node)
        ]
        proven = set(proven_flaky)
        unexpected = [node for node in failed if node not in known_failing and node not in proven]
        scoped_out = [node for node in unexpected if out_of_scope(node)]
        new_failures = [node for node in unexpected if not out_of_scope(node)]
        now_passing = sorted(
            node for node in known_failing
            if "passed" in samples(node) and "failed" not in samples(node)
        )
        missing = sorted(node for node in known_failing | known_flaky if node not in outcomes)
        skipped_known = sorted(
            node for node in known_failing
            if samples(node) and set(samples(node)) == {"skipped"}
        )

        platform_failed = [node for node in new_failures if in_platform_module(node)]
        platform_skipped, platform_ran, platform_absent = [], [], []
        for module in platform_modules:
            nodes = [node for node in outcomes if module_of(node) == module]
            collection = outcome_samples(outcomes.get(f"{module}::<collection>"))
            ran = [node for node in nodes if not node.endswith("::<collection>")
                   and set(samples(node)) - {"skipped"}]
            if ran:
                platform_ran.append(module)
            elif collection and set(collection) == {"skipped"}:
                platform_skipped.append(module)
            elif not nodes:
                platform_absent.append(module)
            else:
                platform_skipped.append(module)  # all collected nodes skipped

        lines.append("")
        if overlap:
            rc = 1
            lines.append("GATE FAIL: baseline inconsistent (node in more than one category):")
            lines.extend(f"  OVERLAP {node}" for node in overlap)
        if platform_failed:
            lines.append(f"GATE FAIL: SKIPPED_PLATFORM module ran and failed on {args.platform}:")
            lines.extend(f"  PLATFORM MODULE FAILED {node}" for node in platform_failed)
        plain_new = [node for node in new_failures if node not in known_flaky]
        lone_flaky_fail = [node for node in new_failures if node in known_flaky]
        if plain_new:
            rc = 1
            lines.append("GATE FAIL: new failures not in the known baseline:")
            lines.extend(f"  NEW FAILURE {node}" for node in plain_new)
        if lone_flaky_fail:
            rc = 1
            lines.append("GATE FAIL: single failure is not a flake (no passing sample of the same node):")
            lines.extend(f"  FAIL {node}" for node in lone_flaky_fail)
        if skipped_known:
            rc = 1
            lines.append("GATE FAIL: known failure skipped (skip is not a pass):")
            lines.extend(f"  KNOWN FAILURE SKIPPED {node}" for node in skipped_known)
        if not new_failures and not skipped_known and not overlap:
            lines.append("GATE PASS: no new failures.")
        if platform_skipped:
            reason = baseline.get("skipped_platform", {}).get("reason", "module skips itself on this platform")
            lines.append(f"Modules skipped by platform on {args.platform} ({reason}):")
            lines.extend(f"  SKIPPED_PLATFORM {module} (module skip)" for module in platform_skipped)
        if platform_ran:
            lines.append("SKIPPED_PLATFORM modules that actually ran (remove from skipped_platform if they pass):")
            lines.extend(f"  PLATFORM MODULE RAN {module}" for module in platform_ran)
        if platform_absent:
            lines.append("SKIPPED_PLATFORM modules not present in this run (renamed or removed?):")
            lines.extend(f"  MISSING MODULE {module}" for module in platform_absent)
        if now_passing:
            lines.append("Known failures now PASSING (remove them from known_failures.json):")
            lines.extend(f"  NOW PASSING {node}" for node in now_passing)
        if proven_flaky:
            lines.append("Known flaky tests with both a pass and a fail of the same node:")
            lines.extend(f"  FLAKY {node}" for node in proven_flaky)
        if scoped_out:
            reason = baseline.get("out_of_scope", {}).get("reason", "component does not run on this platform")
            lines.append(f"Failures out of scope on {args.platform} ({reason}):")
            lines.extend(f"  OUT OF SCOPE {node}" for node in scoped_out)
        if missing:
            lines.append("Known entries not present in this run (renamed or removed?):")
            lines.extend(f"  MISSING {node}" for node in missing)

    report = "\n".join(lines)
    print(report)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        # One-line summary as a check-run annotation, readable through the API.
        counts = (f"passed={len(passed)} failed={len(failed)} skipped={len(skipped)} "
                  f"pytest_exit={exitstatus} result={'FAIL' if rc else 'PASS'}")
        if baseline is not None:
            counts += (f" new={len(new_failures)} now_passing={len(now_passing)} "
                       f"out_of_scope={len(scoped_out)} known_skipped={len(skipped_known)} "
                       f"skipped_platform={len(platform_skipped)} overlap={len(overlap)}")
        print(f"::notice title=v1 gate {args.platform}::{counts}")
        # Name each new failure too (capped), so agents can triage from the API
        # without downloading the outcomes artifact.
        announced = list(skipped_known) + list(new_failures)
        if not announced and rc:
            announced = list(failed)
        for node in announced[:10]:
            print(f"::error title=new failure {args.platform}::{node}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
