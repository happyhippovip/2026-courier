#!/usr/bin/env python3
"""Executable handoff and durability tests for the coordination-only ledger."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "agent_handoff_ledger.py"
SPEC = importlib.util.spec_from_file_location("agent_handoff_ledger", CLI)
assert SPEC and SPEC.loader
ledger_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger_module)


def record() -> dict:
    return {
        "PROJECT": "happyhippovip/2026-courier",
        "GOAL": "Continue exact-SHA acceptance without chat context.",
        "CURRENT_SHA": "b" * 40,
        "BRANCH": "release-candidate-integration",
        "RUNTIME_IDENTITY": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "RUNTIME_OWNER": "test-owner",
        "STATUS": "PROVISIONAL",
        "PROVEN_EDGES": ["issue state"],
        "UNPROVEN_EDGES": ["runtime artifact"],
        "FIRST_CAUSAL_BLOCKER": "runtime artifact is not current-SHA bound",
        "BLOCKER_OWNER": "session-b",
        "NEXT_EXECUTABLE_ACTION": "Validate the current-SHA runtime artifact.",
        "ACTIVE_WRITERS": ["session-a"],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 1,
        "TASKS_COMPLETED": 2,
        "WORKERS_USED": 1,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "NO",
        "QUEUE_INDEPENDENT": "UNKNOWN",
        "LAST_EVIDENCE": ["https://github.com/example/project/issues/1"],
        "LAST_UPDATED_BY": "session-a",
        "CONTINUATION_CHECKPOINT": "Session B starts from the acceptance guard.",
    }


def guard(
    *,
    sha: str = "b" * 40,
    runtime_identity: str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    transition_state: str = "PROVISIONAL",
) -> dict:
    issue_url = "https://github.com/example/project/issues/1"
    artifact_url = "https://github.com/example/project/actions/runs/1"
    value = {
        "flow": [
            "EXECUTION",
            "EVIDENCE",
            "ACCEPTANCE_GUARD",
            "LEDGER_TRANSITION",
            "NEXT_EXECUTABLE_ACTION",
        ],
        "transition_state": transition_state,
        "binding": {
            "branch": "release-candidate-integration",
            "current_sha": sha,
            "runtime_identity": runtime_identity,
        },
        "worker_state": "READY_FOR_FOREIGN_VALIDATION",
        "evidence": [
            {
                "source_url": issue_url,
                "source_type": "GITHUB_ISSUE_STATE",
                "observed_at": "2026-09-17T09:00:00Z",
                "evidence_sha": sha,
                "runtime_binding": runtime_identity,
                "validity": "VALID",
                "reason": "Issue state was observed through GitHub.",
            },
            {
                "source_url": artifact_url,
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-09-17T09:00:00Z",
                "evidence_sha": "a" * 40,
                "runtime_binding": "older-runtime",
                "validity": "STALE",
                "reason": "Artifact is not bound to the current SHA/runtime.",
                "producer_id": "test_producer",
                "verifier_id": "test_verifier",
            },
        ],
        "acceptance_predicate": {
            "name": "courier-physical-acceptance",
            "version": "1",
            "required_results": ["ISSUE_STATE", "RUNTIME_ARTIFACT"],
            "results": {
                "ISSUE_STATE": {
                    "status": "PASS",
                    "observed_value": "CLOSED",
                    "evidence_urls": [issue_url],
                },
                "RUNTIME_ARTIFACT": {
                    "status": "UNKNOWN",
                    "observed_value": "NOT_BOUND_TO_CURRENT_SHA",
                    "evidence_urls": [artifact_url],
                },
            },
        },
    }
    if transition_state == "CANONICAL_ACCEPTED":
        value["evidence"][1].update(
            {
                "evidence_sha": sha,
                "runtime_binding": runtime_identity,
                "validity": "VALID",
                "reason": "Artifact is bound to the current SHA/runtime.",
            }
        )
        value["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"].update(
            {"status": "PASS", "observed_value": "PASS"}
        )
    return value


def initialize(path: Path) -> dict:
    return ledger_module.initialize(path, record(), guard(), 1.0)


def write_legacy_ledger(path: Path) -> dict:
    bundle = initialize(path)
    bundle.pop("acceptance_guard")
    bundle["schema_version"] = 1
    previous_hash = None
    for entry in bundle["history"]:
        entry.pop("acceptance_guard")
        entry.pop("state_sha256")
        entry["previous_entry_sha256"] = previous_hash
        entry["entry_sha256"] = ledger_module._entry_hash(entry)
        previous_hash = entry["entry_sha256"]
    ledger_module.atomic_write(path, bundle)
    return ledger_module.load_bundle(path)


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI, timeout=60), *args],
        check=check,
        capture_output=True,
        text=True,
    )


class AgentHandoffLedgerTests(unittest.TestCase):
    def test_separate_process_handoff_preserves_state_and_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            ledger = base / "ledger.json"
            record_path = base / "record.json"
            guard_path = base / "guard.json"
            record_path.write_text(json.dumps(record()), encoding="utf-8")
            guard_path.write_text(json.dumps(guard()), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import subprocess,sys;"
                        "subprocess.run([sys.executable,sys.argv[1],'init',sys.argv[2],"
                        "'--record',sys.argv[3],'--guard',sys.argv[4]],check=True,"
                        "capture_output=True,text=True, timeout=60)"
                    ),
                    str(CLI),
                    str(ledger),
                    str(record_path),
                    str(guard_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            session_b_code = """
import json, subprocess, sys
cli, ledger = sys.argv[1], sys.argv[2]
action = json.loads(subprocess.run(
    [sys.executable, cli, "next-action", ledger],
    check=True, capture_output=True, text=True
, timeout=60).stdout)
assert action["CURRENT_SHA"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
assert action["TRANSITION_STATE"] == "PROVISIONAL"
assert action["WORKER_STATE"] == "READY_FOR_FOREIGN_VALIDATION"
subprocess.run([
    sys.executable, cli, "update", ledger,
    "--expected-revision", str(action["REVISION"], timeout=60),
    "--updated-by", "session-b",
    "--set", "STATUS=VALIDATING",
    "--set", 'PROVEN_EDGES=["issue state","worker state round-trip"]',
], check=True, capture_output=True, text=True)
"""
            subprocess.run(
                [sys.executable, "-c", session_b_code, str(CLI, timeout=60), str(ledger)],
                check=True,
                capture_output=True,
                text=True,
                env={},
            )

            bundle = json.loads(run_cli("read", str(ledger)).stdout)
            self.assertEqual(bundle["revision"], 1)
            self.assertEqual(bundle["record"]["STATUS"], "VALIDATING")
            self.assertEqual(bundle["record"]["TASKS_COMPLETED"], 2)
            self.assertEqual(bundle["record"]["UNPROVEN_EDGES"], ["runtime artifact"])
            self.assertEqual(bundle["acceptance_guard"]["worker_state"], "READY_FOR_FOREIGN_VALIDATION")
            self.assertEqual([item["operation"] for item in bundle["history"]], ["INIT", "UPDATE"])

            stale = run_cli(
                "update",
                str(ledger),
                "--expected-revision",
                "0",
                "--updated-by",
                "stale-session",
                "--set",
                "STATUS=DONE",
                check=False,
            )
            self.assertEqual(stale.returncode, 2)
            self.assertIn("revision conflict", stale.stderr)

    def test_stale_legacy_checkpoint_is_detected_and_next_action_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            write_legacy_ledger(ledger)
            stale = run_cli(
                "freshness",
                str(ledger),
                "--observed-branch",
                "release-candidate-integration",
                "--observed-sha",
                "c" * 40,
                "--observed-issue-state",
                "CLOSED",
                "--observed-evidence-url",
                "https://github.com/example/project/issues/1",
                check=False,
            )
            self.assertEqual(stale.returncode, 3)
            result = json.loads(stale.stdout)
            self.assertEqual(result["FRESHNESS"], "STALE")
            self.assertFalse(result["NEXT_ACTION_ALLOWED"])
            self.assertIn("CURRENT_SHA_MISMATCH", result["REASONS"])
            self.assertIn("ACCEPTANCE_GUARD_MISSING", result["REASONS"])
            self.assertIn("BLOCKER_BINDING_STALE", result["REASONS"])
            self.assertIn("ACCEPTANCE_STATE_UNGUARDED", result["REASONS"])
            self.assertIn("NEXT_ACTION_BINDING_STALE", result["REASONS"])
            action = run_cli("next-action", str(ledger), check=False)
            self.assertEqual(action.returncode, 2)
            self.assertIn("next-action refused", action.stderr)

    def test_guard_upgrade_preserves_unrelated_record_and_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            before = write_legacy_ledger(ledger)
            new_guard = guard(sha="c" * 40, runtime_identity="new-runtime")
            updated = ledger_module.update(
                ledger,
                0,
                {
                    "CURRENT_SHA": "c" * 40,
                    "RUNTIME_IDENTITY": "new-runtime",
                    "STATUS": "PROVISIONAL",
                },
                "upgrade-writer",
                1.0,
                new_guard,
            )
            self.assertEqual(updated["revision"], 1)
            self.assertEqual(updated["schema_version"], 2)
            self.assertEqual(updated["record"]["TASKS_COMPLETED"], before["record"]["TASKS_COMPLETED"])
            self.assertEqual(updated["history"][0], before["history"][0])
            self.assertIn("@ACCEPTANCE_GUARD", updated["history"][1]["changed_fields"])

    def test_provenance_predicates_bindings_and_transition_gate(self):
        mismatch = guard()
        mismatch["evidence"][0]["runtime_binding"] = "wrong-runtime"
        with self.assertRaisesRegex(ledger_module.LedgerError, "mismatched SHA/runtime"):
            ledger_module.validate_guard(mismatch)

        provisional = guard()
        provisional["transition_state"] = "CANONICAL_ACCEPTED"
        with self.assertRaisesRegex(ledger_module.LedgerError, "requires every predicate"):
            ledger_module.validate_guard(provisional)

        accepted = guard(transition_state="CANONICAL_ACCEPTED")
        ledger_module.validate_guard(accepted)
        self.assertEqual(accepted["acceptance_predicate"]["version"], "1")
        self.assertEqual(accepted["evidence"][0]["validity"], "VALID")

    def test_worker_state_and_current_freshness_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            self.assertEqual(
                bundle["acceptance_guard"]["worker_state"],
                "READY_FOR_FOREIGN_VALIDATION",
            )
            current = ledger_module.freshness(
                bundle,
                "release-candidate-integration",
                "b" * 40,
                "CLOSED",
                ["https://github.com/example/project/issues/1"],
            )
            self.assertEqual(current["FRESHNESS"], "CURRENT")
            self.assertTrue(current["NEXT_ACTION_ALLOWED"])

    def test_freshness_with_separated_runtime_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            bundle["record"]["RUNTIME_IDENTITY"] = "test-machine"
            bundle["acceptance_guard"]["binding"]["runtime_identity"] = "test-machine"
            matched = ledger_module.freshness(
                bundle,
                "release-candidate-integration",
                "b" * 40,
                "CLOSED",
                ["https://github.com/example/project/issues/1"],
                "test-machine",
            )
            self.assertEqual(matched["FRESHNESS"], "CURRENT")
            self.assertTrue(matched["NEXT_ACTION_ALLOWED"])
            legacy = ledger_module.freshness(
                bundle,
                "release-candidate-integration",
                "b" * 40,
                "CLOSED",
                ["https://github.com/example/project/issues/1"],
            )
            self.assertEqual(legacy["FRESHNESS"], "STALE")
            self.assertIn("RUNTIME_IDENTITY_MISMATCH", legacy["REASONS"])
            foreign = ledger_module.freshness(
                bundle,
                "release-candidate-integration",
                "b" * 40,
                "CLOSED",
                ["https://github.com/example/project/issues/1"],
                "other-machine",
            )
            self.assertEqual(foreign["FRESHNESS"], "STALE")
            self.assertIn("RUNTIME_IDENTITY_MISMATCH", foreign["REASONS"])

    def test_acceptance_cannot_consume_same_update_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            landed = ledger_module.copy.deepcopy(
                bundle["acceptance_guard"]
            )
            proof = {
                "source_url": "https://github.com/example/project/actions/runs/2",
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-09-17T18:00:00Z",
                "evidence_sha": "b" * 40,
                "runtime_binding": "b" * 40,
                "validity": "VALID",
                "reason": "foreign attestation",
                "producer_id": "foreign-producer",
                "verifier_id": "foreign-verifier",
            }
            landed["evidence"].append(proof)
            landed["transition_state"] = "CANONICAL_ACCEPTED"
            landed["acceptance_predicate"]["results"]["ISSUE_STATE"][
                "status"
            ] = "PASS"
            landed["acceptance_predicate"]["results"]["ISSUE_STATE"][
                "evidence_urls"
            ] = [proof["source_url"]]
            landed["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"][
                "status"
            ] = "PASS"
            landed["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"][
                "observed_value"
            ] = "PASS"
            landed["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"][
                "evidence_urls"
            ] = [proof["source_url"]]
            after_landing = ledger_module.update(
                ledger,
                bundle["revision"],
                {"UNPROVEN_EDGES": []},
                "foreign-worker",
                1.0,
                landed,
            )
            self.assertEqual(
                after_landing["acceptance_guard"]["transition_state"],
                "PROVISIONAL",
            )
            self.assertNotEqual(after_landing["record"]["CLEAN_IDLE"], "YES")
            followed = ledger_module.update(
                ledger,
                after_landing["revision"],
                {"TASKS_COMPLETED": 3},
                "another-worker",
                1.0,
            )
            self.assertEqual(
                followed["acceptance_guard"]["transition_state"],
                "CANONICAL_ACCEPTED",
            )


    def test_reject_copied_proof_with_different_sha(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            
            # Step 1: Add a valid proof for SHA A
            landed = ledger_module.copy.deepcopy(bundle["acceptance_guard"])
            proof = {
                "source_url": "https://github.com/example/project/actions/runs/99",
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-09-17T18:00:00Z",
                "evidence_sha": "a" * 40,
                "runtime_binding": "runtime-a",
                "validity": "UNKNOWN",
                "reason": "foreign attestation",
                "producer_id": "foreign-producer",
                "verifier_id": "foreign-verifier",
            }
            landed["evidence"].append(proof)
            landed["evidence"][0]["validity"] = "STALE"
            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            landed["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
            b2 = ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "worker1", 1.0, landed)
            
            # Step 2: Try to reuse the SAME URL but change the SHA to B (Copied Proof)
            landed2 = ledger_module.copy.deepcopy(b2["acceptance_guard"])
            proof2 = ledger_module.copy.deepcopy(proof)
            proof2["evidence_sha"] = "b" * 40
            landed2["evidence"][2] = proof2
            landed2["evidence"][0]["validity"] = "STALE"
            landed2["evidence"][1]["validity"] = "STALE"
            landed2["evidence"][2]["validity"] = "UNKNOWN"
            landed2["binding"]["current_sha"] = "b"*40
            
            with self.assertRaisesRegex(ledger_module.LedgerError, "copied proof: URL https://github.com/example/project/actions/runs/99 was historically bound to SHA"):
                ledger_module.update(ledger, b2["revision"], {"CURRENT_SHA": "b"*40}, "worker2", 1.0, landed2)

    def test_reject_caller_created_machine_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            
            landed = ledger_module.copy.deepcopy(bundle["acceptance_guard"])
            proof = {
                "source_url": "https://github.com/example/project/actions/runs/100",
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-09-17T18:00:00Z",
                "evidence_sha": "a" * 40,
                "runtime_binding": "runtime-a",
                "validity": "UNKNOWN",
                "reason": "attestation",
                "producer_id": "caller",
                "verifier_id": "verifier",
            }
            landed["evidence"].append(proof)
            landed["evidence"][0]["validity"] = "STALE"
            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            landed["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
            # The updater is "caller", which matches producer_id -> Self-certification!
            with self.assertRaisesRegex(ledger_module.LedgerError, "caller-created or self-certifying MACHINE_ARTIFACT evidence rejected"):
                ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "caller", 1.0, landed)

    def test_reject_arbitrary_producer_verifier(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            
            landed = ledger_module.copy.deepcopy(bundle["acceptance_guard"])
            proof = {
                "source_url": "https://github.com/example/project/actions/runs/101",
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-09-17T18:00:00Z",
                "evidence_sha": "a" * 40,
                "runtime_binding": "runtime-a",
                "validity": "UNKNOWN",
                "reason": "attestation",
                "producer_id": "arbitrary",
                "verifier_id": "verifier",
            }
            landed["evidence"].append(proof)
            landed["evidence"][0]["validity"] = "STALE"
            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            landed["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
            with self.assertRaisesRegex(ledger_module.LedgerError, "evidence produced by the acceptance decision path itself or uses arbitrary strings"):
                ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "worker", 1.0, landed)


    def test_clean_idle_rejected_with_unproven_work(self):
        rec = record()
        rec["CLEAN_IDLE"] = "YES"
        rec["NEXT_EXECUTABLE_ACTION"] = "NONE"
        rec["UNPROVEN_EDGES"] = ["RELEASE"]
        with self.assertRaisesRegex(
            ledger_module.LedgerError, "UNPROVEN_EDGES"
        ):
            ledger_module.validate_record(rec, allow_unknown_sha=False)

    def test_clean_idle_rejected_without_canonical_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            bundle["record"]["CLEAN_IDLE"] = "YES"
            bundle["record"]["NEXT_EXECUTABLE_ACTION"] = "NONE"
            bundle["record"]["UNPROVEN_EDGES"] = []
            self.assertEqual(
                bundle["acceptance_guard"]["transition_state"], "PROVISIONAL"
            )
            with self.assertRaisesRegex(
                ledger_module.LedgerError, "CANONICAL_ACCEPTED"
            ):
                ledger_module.validate_bundle(bundle)

    def test_bare_external_names_unproven_without_physical_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            seeded = ledger_module.update(
                ledger,
                bundle["revision"],
                {
                    "PROVEN_EDGES": [
                        "SALES PACKAGE",
                        "POST-PILOT HARDENING",
                        "RELEASE",
                    ]
                },
                "probe-worker",
                1.0,
            )
            # Without bound physical proof the stale-proof rule must refuse
            # to keep bare external names in PROVEN_EDGES.
            updated = ledger_module.update(
                ledger,
                seeded["revision"],
                {"TASKS_COMPLETED": 3},
                "probe-worker",
                1.0,
                seeded["acceptance_guard"],
            )
            self.assertNotIn("SALES PACKAGE", updated["record"]["PROVEN_EDGES"])
            self.assertNotIn(
                "POST-PILOT HARDENING", updated["record"]["PROVEN_EDGES"]
            )
            self.assertNotIn("RELEASE", updated["record"]["PROVEN_EDGES"])
            self.assertIn("SALES PACKAGE", updated["record"]["UNPROVEN_EDGES"])
            self.assertEqual(
                updated["acceptance_guard"]["transition_state"], "PROVISIONAL"
            )

    def test_concurrent_readers_only_observe_valid_atomic_snapshots(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            errors = []
            stop = threading.Event()

            def reader() -> None:
                while not stop.is_set():
                    try:
                        bundle = ledger_module.load_bundle(ledger)
                        if bundle["revision"] not in {0, 1}:
                            errors.append(f"unexpected revision {bundle['revision']}")
                    except Exception as exc:
                        errors.append(str(exc))

            readers = [threading.Thread(target=reader) for _ in range(8)]
            for thread in readers:
                thread.start()
            ledger_module.update(ledger, 0, {"STATUS": "VALIDATING"}, "writer", 1.0)
            stop.set()
            for thread in readers:
                thread.join()
            self.assertEqual(errors, [])

    def test_atomic_replace_failure_preserves_previous_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            original = initialize(ledger)
            with mock.patch.object(
                ledger_module.os, "replace", side_effect=OSError("simulated failure")
            ):
                with self.assertRaises(OSError):
                    ledger_module.update(
                        ledger, 0, {"STATUS": "VALIDATING"}, "writer", 1.0
                    )
            self.assertEqual(ledger_module.load_bundle(ledger), original)
            self.assertEqual(list(ledger.parent.glob(f".{ledger.name}.*.tmp")), [])

    def test_bounded_cross_process_lock_fails_busy_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            holder_code = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import agent_handoff_ledger
with agent_handoff_ledger.writer_lock(Path(sys.argv[2]), 1.0):
    print("LOCKED", flush=True)
    time.sleep(2)
"""
            holder = subprocess.Popen(
                [sys.executable, "-c", holder_code, str(ROOT / "scripts"), str(ledger)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                assert holder.stdout
                self.assertEqual(holder.stdout.readline().strip(), "LOCKED")
                blocked = run_cli(
                    "update",
                    str(ledger),
                    "--expected-revision",
                    "0",
                    "--updated-by",
                    "blocked-writer",
                    "--set",
                    "STATUS=VALIDATING",
                    "--lock-timeout",
                    "0.05",
                    check=False,
                )
                self.assertEqual(blocked.returncode, 2)
                self.assertIn("writer lock busy", blocked.stderr)
                self.assertEqual(ledger_module.load_bundle(ledger)["revision"], 0)
            finally:
                holder.terminate()
                holder.communicate(timeout=5)

    def test_missing_corrupt_tampered_and_secret_data_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            missing = run_cli("read", str(base / "missing.json"), check=False)
            self.assertEqual(missing.returncode, 2)
            self.assertIn("does not exist", missing.stderr)

            corrupt = base / "corrupt.json"
            corrupt.write_text("{", encoding="utf-8")
            result = run_cli("read", str(corrupt), check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("corrupt JSON", result.stderr)

            ledger = base / "ledger.json"
            initialize(ledger)
            tampered = json.loads(ledger.read_text(encoding="utf-8"))
            tampered["record"]["STATUS"] = "DONE"
            ledger.write_text(json.dumps(tampered), encoding="utf-8")
            result = run_cli("read", str(ledger), check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("does not match", result.stderr)

            secret_guard = guard()
            secret_guard["worker_state"] = "authorization: Bearer value"
            with self.assertRaisesRegex(ledger_module.LedgerError, "likely secret"):
                ledger_module.validate_guard(secret_guard)

    def test_render_and_next_action_are_deterministic_and_scoped(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            first = run_cli("render", str(ledger)).stdout
            second = run_cli("render", str(ledger)).stdout
            self.assertEqual(first, second)
            self.assertIn("TRANSITION_STATE: PROVISIONAL", first)
            action = json.loads(run_cli("next-action", str(ledger)).stdout)
            self.assertEqual(action["WORKER_STATE"], "READY_FOR_FOREIGN_VALIDATION")
            self.assertEqual(
                action["FLOW"],
                [
                    "EXECUTION",
                    "EVIDENCE",
                    "ACCEPTANCE_GUARD",
                    "LEDGER_TRANSITION",
                    "NEXT_EXECUTABLE_ACTION",
                ],
            )


if __name__ == "__main__":
    unittest.main()
