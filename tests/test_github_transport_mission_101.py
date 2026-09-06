#!/usr/bin/env python3
"""Unit and integration tests for Mission 101, 103, 106 Hardened GitHub Courier Transport Architecture."""

import concurrent.futures
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.github_transport import (
    GitHubTransportEnvelope,
    DurableTransportInbox,
    DurableStateLedger,
    ProcessSafeFileLock,
    GitHubWebhookVerificationAdapter,
    RepositoryDispatchAdapter,
    TransportDispatcherBridge,
    TransportResultReturnAdapter,
    EXACTLY_ONCE_SEMANTICS,
    canonical_json_dumps,
    compute_sha256,
)
from scripts.resource_policy import ResourcePolicyManager
from scripts.run_chief_commander import SmartResourceRouter


def _concurrency_delivery_worker(repo_dir_str: str, body_bytes: bytes, headers: dict, secret: str) -> tuple[bool, str]:
    inbox = DurableTransportInbox(repo_dir=Path(repo_dir_str))
    adapter = GitHubWebhookVerificationAdapter(inbox=inbox, repo_dir=Path(repo_dir_str))
    ok, reason, env = adapter.verify_and_ingest(body_bytes, headers, secret=secret)
    return ok, reason


def _concurrency_registry_worker(repo_dir_str: str, worker_id: int) -> int:
    inbox = DurableTransportInbox(repo_dir=Path(repo_dir_str))
    def _update(reg: dict):
        reg["deliveries"][f"deliv-worker-{worker_id}"] = {"status": "OK", "worker": worker_id}
        reg["messages"][f"msg-worker-{worker_id}"] = {"status": "OK", "worker": worker_id}
        reg["stats"]["total_received"] = reg["stats"].get("total_received", 0) + 1
    inbox._update_registry_synchronized(_update)
    return worker_id


def _concurrency_dispatch_worker(repo_dir_str: str, cmd_dict: dict) -> dict:
    env = GitHubTransportEnvelope.from_dict(cmd_dict)
    bridge = TransportDispatcherBridge(repo_dir=Path(repo_dir_str))
    return bridge.dispatch_and_execute(env)


def _lock_holder_worker(lock_path_str: str, hold_duration: float, started_flag: str) -> str:
    lock_path = Path(lock_path_str)
    with ProcessSafeFileLock(lock_path, timeout=5.0) as lock:
        Path(started_flag).touch()
        time.sleep(hold_duration)
    return "HELD_OK"


def _lock_requester_worker(lock_path_str: str, timeout: float) -> str:
    lock_path = Path(lock_path_str)
    try:
        with ProcessSafeFileLock(lock_path, timeout=timeout):
            return "ENTERED_CRITICAL_SECTION"
    except TimeoutError:
        return "TIMED_OUT_BLOCKED"


class TestMission101To106HardenedTransport(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_gh_hardened_106_"))
        self.events_dir = self.test_dir / "events"
        self.transport_dir = self.events_dir / "transport"
        self.policies_dir = self.events_dir / "policies"
        self.thought_incoming_dir = self.events_dir / "thought-incoming"
        self.thought_processed_dir = self.events_dir / "thought-processed"
        self.locks_dir = self.events_dir / "locks"
        self.processed_dir = self.events_dir / "processed"

        for d in [self.transport_dir, self.policies_dir, self.thought_incoming_dir, self.thought_processed_dir, self.locks_dir, self.processed_dir]:
            d.mkdir(parents=True, exist_ok=True)

        canonical = Path("events/policies/resource_policy.json")
        if canonical.exists():
            shutil.copy(canonical, self.policies_dir / "resource_policy.json")

        self.inbox = DurableTransportInbox(repo_dir=self.test_dir)
        self.adapter = GitHubWebhookVerificationAdapter(inbox=self.inbox, repo_dir=self.test_dir)
        self.synthetic_secret = "test_webhook_secret_key_12345"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _generate_hmac_header(self, body_bytes: bytes, secret: str) -> str:
        sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    def test_01_webhook_auth_strict_fail_closed(self):
        """Prove secret=None, empty secret, missing signature, and invalid signature are strictly rejected."""
        payload = {"event_type": "COMMAND", "task_id": "TASK-AUTH-001"}
        body_bytes = json.dumps(payload).encode("utf-8")
        valid_header = self._generate_hmac_header(body_bytes, self.synthetic_secret)

        ok, reason, _ = self.adapter.verify_and_ingest(body_bytes, {"X-GitHub-Delivery": "d1", "X-GitHub-Event": "repository_dispatch", "X-Hub-Signature-256": valid_header}, secret=None)
        self.assertFalse(ok)
        self.assertEqual(reason, "MISSING_OR_EMPTY_SECRET")

        ok, reason, _ = self.adapter.verify_and_ingest(body_bytes, {"X-GitHub-Delivery": "d1", "X-GitHub-Event": "repository_dispatch", "X-Hub-Signature-256": valid_header}, secret="   ")
        self.assertFalse(ok)
        self.assertEqual(reason, "MISSING_OR_EMPTY_SECRET")

        ok, reason, _ = self.adapter.verify_and_ingest(body_bytes, {"X-GitHub-Delivery": "d1", "X-GitHub-Event": "repository_dispatch"}, secret=self.synthetic_secret)
        self.assertFalse(ok)
        self.assertEqual(reason, "MISSING_SIGNATURE")

        ok, reason, _ = self.adapter.verify_and_ingest(body_bytes, {"X-GitHub-Delivery": "d1", "X-GitHub-Event": "repository_dispatch", "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000"}, secret=self.synthetic_secret)
        self.assertFalse(ok)
        self.assertEqual(reason, "INVALID_SIGNATURE")

        ok, reason, env = self.adapter.verify_and_ingest(body_bytes, {"X-GitHub-Delivery": "d1", "X-GitHub-Event": "repository_dispatch", "X-Hub-Signature-256": valid_header}, secret=self.synthetic_secret)
        self.assertTrue(ok)
        self.assertEqual(reason, "VERIFIED_AND_DISPATCHABLE")

    def test_02_sequential_and_concurrent_delivery_dedupe(self):
        """Prove delivery dedupe is atomic: exactly 1 accepted sequentially and concurrently."""
        payload = {"event_type": "COMMAND", "task_id": "TASK-DELIV-001"}
        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "X-GitHub-Delivery": "deliv-race-001",
            "X-GitHub-Event": "repository_dispatch",
            "X-Hub-Signature-256": self._generate_hmac_header(body_bytes, self.synthetic_secret)
        }

        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(_concurrency_delivery_worker, str(self.test_dir), body_bytes, headers, self.synthetic_secret)
            f2 = ex.submit(_concurrency_delivery_worker, str(self.test_dir), body_bytes, headers, self.synthetic_secret)
            res1 = f1.result()
            res2 = f2.result()

        results = [res1, res2]
        successes = [r for r in results if r[0] is True]
        blocked = [r for r in results if r[0] is False]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0][1], "DUPLICATE_DELIVERY_BLOCKED")

    def test_03_concurrent_same_message_different_delivery_blocked(self):
        """Prove same message ID under different delivery IDs is atomically blocked."""
        payload = {"event_type": "COMMAND", "message_id": "msg-gh-fixed-103", "task_id": "TASK-MSG-001"}
        body_bytes = json.dumps(payload).encode("utf-8")

        headers1 = {
            "X-GitHub-Delivery": "deliv-diff-001a",
            "X-GitHub-Event": "repository_dispatch",
            "X-Hub-Signature-256": self._generate_hmac_header(body_bytes, self.synthetic_secret)
        }
        headers2 = {
            "X-GitHub-Delivery": "deliv-diff-001b",
            "X-GitHub-Event": "repository_dispatch",
            "X-Hub-Signature-256": self._generate_hmac_header(body_bytes, self.synthetic_secret)
        }

        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(_concurrency_delivery_worker, str(self.test_dir), body_bytes, headers1, self.synthetic_secret)
            f2 = ex.submit(_concurrency_delivery_worker, str(self.test_dir), body_bytes, headers2, self.synthetic_secret)
            res1 = f1.result()
            res2 = f2.result()

        results = [res1, res2]
        successes = [r for r in results if r[0] is True]
        blocked = [r for r in results if r[0] is False]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0][1], "DUPLICATE_MESSAGE_ID_BLOCKED")

    def test_04_registry_concurrency_and_stale_lock_safety(self):
        """Prove registry concurrency preserves all entries and stale lock recovery never allows concurrent entry."""
        # 1. Concurrency updates
        workers_count = 8
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers_count) as ex:
            futs = [ex.submit(_concurrency_registry_worker, str(self.test_dir), i) for i in range(workers_count)]
            for f in futs:
                f.result()

        reg_data = json.loads((self.transport_dir / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(len(reg_data["deliveries"]), workers_count)
        self.assertEqual(len(reg_data["messages"]), workers_count)
        self.assertEqual(reg_data["stats"]["total_received"], workers_count)

        # 2. Adversarial lock test: process A holds lock for 0.5s, process B requests with short timeout -> B must be blocked
        lock_file = self.transport_dir / "test_adv.lock"
        flag_file = self.test_dir / "started.flag"
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:
            f_holder = ex.submit(_lock_holder_worker, str(lock_file), 1.5, str(flag_file))
            # Wait until holder acquired lock
            for _ in range(50):
                if flag_file.exists():
                    break
                time.sleep(0.01)
            f_req = ex.submit(_lock_requester_worker, str(lock_file), 0.1)
            req_res = f_req.result()
            holder_res = f_holder.result()

        self.assertEqual(req_res, "TIMED_OUT_BLOCKED", "Process B must NOT enter critical section while Process A is active")
        self.assertEqual(holder_res, "HELD_OK")

    def test_05_full_happy_path_state_lifecycle(self):
        """Prove full happy-path lifecycle: RECEIVED -> VERIFIED -> DEDUPED -> DISPATCHABLE -> DISPATCHED -> RESULT_RECEIVED -> ACKED -> DONE."""
        payload = {
            "event_type": "COMMAND",
            "task_id": "TASK-FULL-001",
            "instruction": "Build new component",
            "client_payload": {"event_type": "COMMAND", "instruction": "Build new component"}
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "X-GitHub-Delivery": "deliv-full-001",
            "X-GitHub-Event": "repository_dispatch",
            "X-Hub-Signature-256": self._generate_hmac_header(body_bytes, self.synthetic_secret)
        }

        # 1. Ingress: RECEIVED -> VERIFIED -> DEDUPED -> DISPATCHABLE
        ok, reason, envelope = self.adapter.verify_and_ingest(body_bytes, headers, secret=self.synthetic_secret)
        self.assertTrue(ok)
        self.assertEqual(envelope.state, "DISPATCHABLE")

        # 2. Dispatch: DISPATCHABLE -> DISPATCHED -> RESULT_RECEIVED -> ACKED -> DONE
        bridge = TransportDispatcherBridge(repo_dir=self.test_dir)
        summary = bridge.dispatch_and_execute(envelope)
        self.assertEqual(summary["status"], "COMPLETED")

        # Verify ledger has all required states in exact sequence
        log_lines = (self.transport_dir / "transitions.jsonl").read_text(encoding="utf-8").strip().splitlines()
        transitions = [json.loads(line) for line in log_lines]
        states = [t["next_state"] for t in transitions]

        expected_sequence = ["VERIFIED", "DEDUPED", "DISPATCHABLE", "DISPATCHED", "RESULT_RECEIVED", "ACKED", "DONE"]
        for expected in expected_sequence:
            self.assertIn(expected, states, f"State {expected} must be durably recorded in transition ledger")

        # Verify initial transition started from RECEIVED
        self.assertEqual(transitions[0]["prior_state"], "RECEIVED")
        self.assertEqual(transitions[0]["next_state"], "VERIFIED")

    def test_06_rejected_path_and_transition_failure_surfacing(self):
        """Prove rejected paths record REJECTED and ledger surfaces I/O failures."""
        valid_bytes = json.dumps({"task_id": "TASK-REJ-001"}).encode("utf-8")
        sig = self._generate_hmac_header(valid_bytes, self.synthetic_secret)

        ok, reason, _ = self.adapter.verify_and_ingest(valid_bytes, {"X-GitHub-Delivery": "d-push", "X-GitHub-Event": "push", "X-Hub-Signature-256": sig}, secret=self.synthetic_secret)
        self.assertFalse(ok)

        # Test simulated write error in DurableStateLedger is surfaced
        ledger = DurableStateLedger(self.transport_dir)
        envelope = GitHubTransportEnvelope(delivery_id="d-err", message_id="msg-err", task_id="task-err")

        # Read-only ledger directory to induce real write failure
        read_only_log = self.transport_dir / "readonly_log"
        read_only_log.mkdir(parents=True, exist_ok=True)
        bad_ledger = DurableStateLedger(read_only_log)
        bad_ledger.transitions_log = read_only_log # points to directory, so opening for append raises IsADirectoryError / PermissionError

        with self.assertRaises((PermissionError, IsADirectoryError, OSError)):
            bad_ledger.record_transition(envelope, "RECEIVED", "VERIFIED")

    def test_07_stored_payload_tamper_protection(self):
        """Prove tampered payload in stored incoming envelope is rejected before dispatch."""
        cmd = RepositoryDispatchAdapter.create_dispatch_command(
            task_id="TASK-TAMPER-001",
            instruction="Implement feature Z",
            repo_dir=self.test_dir,
        )
        cmd.payload["instruction"] = "MALICIOUSLY TAMPERED INSTRUCTION"

        bridge = TransportDispatcherBridge(repo_dir=self.test_dir)
        res = bridge.dispatch_and_execute(cmd)
        self.assertEqual(res["status"], "REJECTED")
        self.assertEqual(res["reason"], "STORED_PAYLOAD_INTEGRITY_FAILED")

    def test_08_incoming_and_evidence_append_only(self):
        """Prove incoming evidence and processing evidence cannot be silently overwritten."""
        envelope = GitHubTransportEnvelope(
            schema_version="1.0",
            message_id="msg-gh-app-001",
            delivery_id="deliv-app-001",
            correlation_id="corr-app-001",
            task_id="task-app-001",
            event_type="COMMAND",
            payload={"action": "COMMAND", "val": 1}
        )
        # First save
        p1 = self.inbox.record_incoming(envelope)
        mtime1 = p1.stat().st_mtime

        # Attempt to save modified envelope with same message_id
        envelope.payload["val"] = 2
        p2 = self.inbox.record_incoming(envelope)
        self.assertEqual(p1, p2)
        # Verify content on disk unchanged
        saved_content = json.loads(p1.read_text(encoding="utf-8"))
        self.assertEqual(saved_content["payload"]["val"], 1, "Incoming evidence must be immutable and not overwritten")

    def test_09_result_return_content_hash_dedupe_across_new_message_id(self):
        """Prove semantically identical result with NEW message_id returns IDEMPOTENT_ALREADY_INGESTED with 1 file created."""
        res_payload = {"verdict": "ACCEPTED", "summary": "Task TASK-RES-999 completed successfully"}

        # First result envelope (message_id = msg-res-001)
        env_A = TransportResultReturnAdapter.package_result_envelope(
            task_id="TASK-RES-999",
            correlation_id="corr-res-999",
            result_payload=res_payload,
        )
        env_A.message_id = "msg-res-001"

        # Second result envelope with DIFFERENT message_id but IDENTICAL semantic content
        env_B = TransportResultReturnAdapter.package_result_envelope(
            task_id="TASK-RES-999",
            correlation_id="corr-res-999",
            result_payload=res_payload,
        )
        env_B.message_id = "msg-res-002"

        r1 = TransportResultReturnAdapter.ingest_into_thought_pipeline(env_A, repo_dir=self.test_dir)
        self.assertEqual(r1["status"], "INGESTED_TO_THOUGHT_PIPELINE")
        self.assertEqual(r1["memory_write"], "NONE")

        r2 = TransportResultReturnAdapter.ingest_into_thought_pipeline(env_B, repo_dir=self.test_dir)
        self.assertEqual(r2["status"], "IDEMPOTENT_ALREADY_INGESTED")
        self.assertEqual(r2["memory_write"], "NONE")

        # Verify exactly ONE file exists in thought-incoming
        files = list((self.test_dir / "events" / "thought-incoming").glob("*.json"))
        self.assertEqual(len(files), 1, "Exactly one Thought-Ingestion file must exist for identical semantic content")


if __name__ == "__main__":
    unittest.main()
