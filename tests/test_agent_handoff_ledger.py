#!/usr/bin/env python3
"""Executable handoff and durability tests for the coordination-only ledger."""

from __future__ import annotations

import importlib.util
import json
import os
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
        "RUNTIME_IDENTITY": "test-runtime",
        "RUNTIME_OWNER": "test-owner",
        "STATUS": "BLOCKED",
        "PROVEN_EDGES": ["edge-a"],
        "UNPROVEN_EDGES": ["edge-b"],
        "FIRST_CAUSAL_BLOCKER": "edge-b",
        "BLOCKER_OWNER": "session-b",
        "NEXT_EXECUTABLE_ACTION": "Run deterministic continuation step.",
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
        "LAST_EVIDENCE": ["https://github.com/example/project/issues/1#issuecomment-1"],
        "LAST_UPDATED_BY": "session-a",
        "CONTINUATION_CHECKPOINT": "Session B starts from edge-b.",
    }


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
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
            record_path.write_text(json.dumps(record()), encoding="utf-8")

            session_a = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import subprocess,sys;"
                        "subprocess.run([sys.executable,sys.argv[1],'init',sys.argv[2],"
                        "'--record',sys.argv[3]],check=True,capture_output=True,text=True)"
                    ),
                    str(CLI),
                    str(ledger),
                    str(record_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(session_a.returncode, 0)

            session_b_code = """
import json, subprocess, sys
cli, ledger = sys.argv[1], sys.argv[2]
action = json.loads(subprocess.run(
    [sys.executable, cli, "next-action", ledger],
    check=True, capture_output=True, text=True
).stdout)
assert action["CURRENT_SHA"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
assert action["NEXT_EXECUTABLE_ACTION"] == "Run deterministic continuation step."
subprocess.run([
    sys.executable, cli, "update", ledger,
    "--expected-revision", str(action["REVISION"]),
    "--updated-by", "session-b",
    "--set", "STATUS=IN_PROGRESS",
    "--set", 'PROVEN_EDGES=["edge-a","edge-b"]',
], check=True, capture_output=True, text=True)
"""
            subprocess.run(
                [sys.executable, "-c", session_b_code, str(CLI), str(ledger)],
                check=True,
                capture_output=True,
                text=True,
                env={},
            )

            bundle = json.loads(run_cli("read", str(ledger)).stdout)
            self.assertEqual(bundle["revision"], 1)
            self.assertEqual(bundle["record"]["STATUS"], "IN_PROGRESS")
            self.assertEqual(bundle["record"]["TASKS_COMPLETED"], 2)
            self.assertEqual(bundle["record"]["UNPROVEN_EDGES"], ["edge-b"])
            self.assertEqual([item["operation"] for item in bundle["history"]], ["INIT", "UPDATE"])
            self.assertEqual(bundle["history"][1]["updated_by"], "session-b")

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
            self.assertEqual(
                json.loads(run_cli("read", str(ledger)).stdout)["record"]["STATUS"],
                "IN_PROGRESS",
            )

    def test_concurrent_readers_only_observe_valid_atomic_snapshots(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            ledger_module.initialize(ledger, record(), 1.0)
            errors = []
            stop = threading.Event()

            def reader() -> None:
                while not stop.is_set():
                    try:
                        bundle = ledger_module.load_bundle(ledger)
                        if bundle["revision"] not in {0, 1}:
                            errors.append(f"unexpected revision {bundle['revision']}")
                    except Exception as exc:  # Captured for assertion in the parent.
                        errors.append(str(exc))

            readers = [threading.Thread(target=reader) for _ in range(8)]
            for thread in readers:
                thread.start()
            ledger_module.update(
                ledger,
                0,
                {"STATUS": "IN_PROGRESS"},
                "writer",
                1.0,
            )
            stop.set()
            for thread in readers:
                thread.join()
            self.assertEqual(errors, [])

    def test_atomic_replace_failure_preserves_previous_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            original = ledger_module.initialize(ledger, record(), 1.0)
            with mock.patch.object(
                ledger_module.os, "replace", side_effect=OSError("simulated failure")
            ):
                with self.assertRaises(OSError):
                    ledger_module.update(
                        ledger,
                        0,
                        {"STATUS": "IN_PROGRESS"},
                        "writer",
                        1.0,
                    )
            self.assertEqual(ledger_module.load_bundle(ledger), original)
            self.assertEqual(list(ledger.parent.glob(f".{ledger.name}.*.tmp")), [])

    def test_bounded_cross_process_lock_fails_busy_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            ledger_module.initialize(ledger, record(), 1.0)
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
                [
                    sys.executable,
                    "-c",
                    holder_code,
                    str(ROOT / "scripts"),
                    str(ledger),
                ],
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
                    "STATUS=IN_PROGRESS",
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
            ledger_module.initialize(ledger, record(), 1.0)
            tampered = json.loads(ledger.read_text(encoding="utf-8"))
            tampered["record"]["STATUS"] = "DONE"
            ledger.write_text(json.dumps(tampered), encoding="utf-8")
            result = run_cli("read", str(ledger), check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("does not match", result.stderr)

            secret_record = record()
            secret_record["CONTINUATION_CHECKPOINT"] = "authorization: Bearer abcdef"
            with self.assertRaisesRegex(ledger_module.LedgerError, "likely secret"):
                ledger_module.validate_record(secret_record, allow_unknown_sha=False)

    def test_render_and_next_action_are_deterministic_and_scoped(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            ledger_module.initialize(ledger, record(), 1.0)
            first = run_cli("render", str(ledger)).stdout
            second = run_cli("render", str(ledger)).stdout
            self.assertEqual(first, second)
            self.assertIn("NON_AUTHORITY: Coordination metadata only", first)
            action = json.loads(run_cli("next-action", str(ledger)).stdout)
            self.assertEqual(
                set(action),
                {
                    "BRANCH",
                    "CURRENT_SHA",
                    "FIRST_CAUSAL_BLOCKER",
                    "BLOCKER_OWNER",
                    "NEXT_EXECUTABLE_ACTION",
                    "RUNTIME_IDENTITY",
                    "STATUS",
                    "CONTINUATION_CHECKPOINT",
                    "REVISION",
                    "NON_AUTHORITY",
                },
            )


if __name__ == "__main__":
    unittest.main()
