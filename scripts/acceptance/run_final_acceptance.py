#!/usr/bin/env python3
"""Existing acceptance entry point: fail-closed, repository-only.

Reuses a58ff1f3's refusal protocol and existing contract/recovery tests.
No live server, worker impersonation, provider, credential lookup or ledger.
Exit 0: required repo proofs pass (NOT physical acceptance); 1: proof failure;
2: refused/incomplete. See cannon_v1_matrix.json for scope and pinned candidate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("cannon_v1_matrix.json")


def evaluate(rows, outcomes, pytest_exit):
    """All selected parameterizations must pass; absent/skip/xfail never pass."""
    matrix = []
    for source in rows:
        row = dict(source)
        evidence, missing = {}, []
        for selector in row["TEST"]:
            matches = {node: status for node, status in outcomes.items()
                       if node == selector or node.startswith(selector + "[")
                       or node.startswith(selector + "::")}
            evidence.update(matches)
            if not matches:
                missing.append(selector)
        if row.get("PROOF_LEVEL", "").endswith("_PROOF_REQUIRED"):
            status = "REQUIRED"
        elif any(v in ("FAIL", "ERROR", "XPASS") for v in evidence.values()):
            status = "FAIL"
        elif not evidence or missing or any(v != "PASS" for v in evidence.values()):
            status = "NOT_PROVEN"
        else:
            status = "PREVIEW_PASS" if row.get("SCOPE") == "PATCH_PREVIEW" else "PASS"
        row.update(STATUS=status, EVIDENCE={"CASES": evidence, "MISSING": missing})
        matrix.append(row)
    required = [row for row in matrix if row.get("REQUIRED")]
    if any(row["STATUS"] == "FAIL" for row in required) or pytest_exit == 1:
        status = "FAIL"
    elif not required or pytest_exit != 0 or any(row["STATUS"] != "PASS" for row in required):
        status = "NOT_PROVEN"
    else:
        status = "PASS"
    invariants = {}
    for group in "ABCDEFGH":
        members = [row["STATUS"] for row in required if group in row.get("INVARIANT", "").split(",")]
        invariants[group] = ("FAIL" if "FAIL" in members else "PASS"
                             if members and all(v == "PASS" for v in members) else "NOT_PROVEN")
    return {"CANNON_V1_REPO_STATUS": status, "PHYSICAL_ACCEPTANCE": "NO",
            "SYNTHETIC_TEST_ONLY": "YES", "PYTEST_EXIT_CODE": pytest_exit,
            "INVARIANTS": invariants, "MATRIX": matrix}


class Results:
    def __init__(self):
        self.outcomes, self.collection_errors = {}, []

    def pytest_collection_finish(self, session):
        self.outcomes.update({item.nodeid: "NOT_RUN" for item in session.items})

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(report.nodeid)

    def pytest_runtest_logreport(self, report):
        if report.failed:
            value = "FAIL" if report.when == "call" else "ERROR"
        elif getattr(report, "wasxfail", None):
            value = "XPASS" if report.passed else "XFAIL"
        elif report.skipped:
            value = "SKIP"
        elif report.when == "call":
            value = "PASS"
        else:
            return
        if self.outcomes.get(report.nodeid) not in ("FAIL", "ERROR", "XPASS"):
            self.outcomes[report.nodeid] = value


def install_test_guards(scratch):
    """Defense in depth, not a sandbox for hostile tests. Tests are reviewed."""
    violations = []

    def denied(*args, **kwargs):
        violations.append("credential_or_provider_access")
        raise RuntimeError("acceptance forbids credential access")

    keyring = types.ModuleType("keyring")
    keyring.get_password = keyring.get_credential = keyring.set_password = denied
    keyring.delete_password = denied
    sys.modules["keyring"] = keyring
    # Selected server tests supply explicit plans. The unrelated provider planner
    # creates repository event directories even at import time; do not import it.
    planner = types.ModuleType("scripts.run_chief_commander")
    planner.ChiefCommander = denied
    sys.modules["scripts.run_chief_commander"] = planner
    # urllib3 performs an IPv6 bind probe at import. Disable that capability in
    # this throwaway test process; keep the socket audit guard fully enforced.
    socket.has_ipv6 = False

    def audit(event, args):
        blocked = event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "os.system"}
        if event == "subprocess.Popen":
            _, argv, cwd, _ = args
            argv = list(argv) if not isinstance(argv, str) else [argv]
            preview = (len(argv) == 3 and argv[:2] == ["git", "apply"]
                       and Path(argv[2]).resolve() == ROOT / "docs/p3/artifact-upload-cutover.patch"
                       and cwd and Path(cwd).resolve().is_relative_to(scratch.resolve()))
            # Reused refusal test launches this script WITHOUT opt-in.
            refusal = argv == [sys.executable, str(Path(__file__).resolve())]
            blocked = not (preview or refusal)
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0]))
            blocked = blocked or path.name == ".env" or "Keychains" in path.parts
        if blocked:
            violations.append(event)
            raise RuntimeError("acceptance blocked external/credential operation")

    sys.addaudithook(audit)
    return violations


def execute_tests(scratch, selectors):
    import pytest
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    violations = install_test_guards(scratch)
    plugin = Results()
    code = int(pytest.main(["-q", "-p", "no:cacheprovider", "--tb=short",
                           "--basetemp", str(scratch / "pytest"), *selectors], plugins=[plugin]))
    payload = {"outcomes": plugin.outcomes, "pytest_exit": code,
               "collection_errors": plugin.collection_errors, "guard_violations": violations}
    (scratch / "results.json").write_text(json.dumps(payload), encoding="utf-8")
    return code


def fingerprint(paths):
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in sorted(set(paths)) if (ROOT / name).is_file()}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="store_true", help="isolated repo proofs; never physical acceptance")
    parser.add_argument("--output", type=Path, help="JSON evidence file (new file only)")
    parser.add_argument("--only", action="append", default=[], metavar="ID",
                        help="target matrix row(s); unexecuted proofs remain NOT_PROVEN")
    parser.add_argument("--_execute", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.repo:
        print("REFUSED: explicit --repo required; this is not a physical acceptance proof.")
        print("SYNTHETIC_TEST_ONLY=YES\nPHYSICAL_ACCEPTANCE=NO")
        return 2
    spec = json.loads(MANIFEST.read_text(encoding="utf-8"))
    unknown = set(args.only) - {row["ID"] for row in spec["MATRIX"]}
    if unknown:
        parser.error("unknown matrix ID")
    selectors = sorted({test for row in spec["MATRIX"] if not args.only or row["ID"] in args.only
                        for test in row["TEST"]})
    if not selectors:
        parser.error("selection has no executable repository proof")
    if args._execute:
        return execute_tests(args._execute, selectors)
    if args.output and args.output.exists():
        parser.error("output already exists; use a new evidence filename")
    tracked = git("ls-files", "*.py", "docs/p3/artifact-upload-cutover.patch").splitlines()
    tracked += [str(MANIFEST.relative_to(ROOT)), "tests/test_cannon_v1_acceptance_gaps.py",
                "tests/test_final_acceptance_harness_fail_closed.py"]
    before = fingerprint(tracked)
    head = git("rev-parse", "HEAD")
    product_changes = [path for path in git("diff", "--name-only", spec["BASE"]["COMMIT"], "--").splitlines()
                       if not path.startswith(("tests/", "scripts/acceptance/"))]
    with tempfile.TemporaryDirectory(prefix="courier-cv1-") as name:
        scratch = Path(name)
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONUTF8": "1",
               "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
               "COURIER_API_KEY": "test-secret", "COURIER_VERIFIER_API_KEY": "verifier-secret",
               "COURIER_SERVER": "http://courier.invalid", "COURIER_SERVER_URL": "http://courier.invalid",
               "COURIER_STATE_FILE": str(scratch / "unused-central.json"),
               "COURIER_ARTIFACT_DIR": str(scratch / "unused-artifacts")}
        try:
            selection = [item for row_id in args.only for item in ("--only", row_id)]
            child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--repo", "--_execute", name, *selection],
                                   cwd=ROOT, env=env, text=True, capture_output=True, timeout=120)
            path = scratch / "results.json"
            raw = json.loads(path.read_text()) if path.exists() else {"outcomes": {}, "pytest_exit": child.returncode}
            print(child.stdout[-18000:])
            if child.returncode != raw["pytest_exit"]:
                raw["pytest_exit"] = 3
        except subprocess.TimeoutExpired:
            raw = {"outcomes": {}, "pytest_exit": 3, "error": "isolated test process timed out"}
        report = evaluate(spec["MATRIX"], raw["outcomes"], raw["pytest_exit"])
        after = fingerprint(tracked)
        changed = sorted(set(before) ^ set(after) | {p for p in before if before[p] != after.get(p)})
        if changed or raw.get("guard_violations") or raw.get("collection_errors"):
            report["CANNON_V1_REPO_STATUS"] = "NOT_PROVEN"
        report.update(BASE=spec["BASE"], TESTED_HEAD=head, BRANCH=git("branch", "--show-current"),
                      UTC=datetime.now(timezone.utc).isoformat(), FILE_SHA256=before,
                      PRODUCT_CHANGES_VS_BASE=product_changes,
                      CHANGED_DURING_RUN=changed, TEST_COUNTS=dict(Counter(raw["outcomes"].values())),
                      EXECUTION_ERROR=raw.get("error"),
                      GUARD_VIOLATIONS=raw.get("guard_violations", []),
                      COLLECTION_ERRORS=raw.get("collection_errors", []))
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    for row in report["MATRIX"]:
        print(f"{row['ID']}={row['STATUS']}")
    print(f"CANNON_V1_REPO_STATUS={report['CANNON_V1_REPO_STATUS']}")
    print("SYNTHETIC_TEST_ONLY=YES\nPHYSICAL_ACCEPTANCE=NO")
    return {"PASS": 0, "FAIL": 1, "NOT_PROVEN": 2}[report["CANNON_V1_REPO_STATUS"]]


if __name__ == "__main__":
    sys.exit(main())
