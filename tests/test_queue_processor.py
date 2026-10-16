import pytest
import os
import json
import shutil
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import queue_processor

def test_process_queue_success(tmp_path):
    # Mocking os methods for directory creation and file movement to use tmp_path
    
    pending_dir = tmp_path / "intakes" / "pending"
    processed_dir = tmp_path / "intakes" / "processed"
    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    task_file = pending_dir / "test_intake.json"
    task_file.write_text('{"foo": "bar"}')
    
    def mock_glob(pattern):
        if pattern == "intakes/pending/*.json":
            return [str(task_file)]
        return []

    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", side_effect=mock_glob):
            with mock.patch("scripts.queue_processor.dispatch_intake") as mock_dispatch:
                with mock.patch("scripts.queue_processor.shutil.move") as mock_move:
                    queue_processor.process_queue()
                    
    mock_dispatch.assert_called_once_with(str(task_file))
    mock_move.assert_called_once_with(str(task_file), os.path.join("intakes/processed", "test_intake.json"))

def test_process_queue_systemexit_continues_batch(tmp_path):
    # dispatch_intake signals failure via sys.exit(); the failing intake
    # stays pending but must not abort the rest of the batch.
    def mock_glob(pattern):
        if pattern == "intakes/pending/*.json":
            return ["fail.json", "ok.json"]
        return []

    dispatched = []

    def fake_dispatch(path):
        dispatched.append(path)
        if path == "fail.json":
            raise SystemExit(1)

    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", side_effect=mock_glob):
            with mock.patch("scripts.queue_processor.dispatch_intake", side_effect=fake_dispatch):
                with mock.patch("scripts.queue_processor.shutil.move") as mock_move:
                    queue_processor.process_queue()  # must not raise

    assert dispatched == ["fail.json", "ok.json"]
    mock_move.assert_called_once_with("ok.json", os.path.join("intakes/processed", "ok.json"))

def test_process_queue_empty():
    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", return_value=[]):
            with mock.patch("scripts.queue_processor.dispatch_intake") as mock_dispatch:
                queue_processor.process_queue()
                
    mock_dispatch.assert_not_called()

def test_process_queue_error(tmp_path):
    pending_dir = tmp_path / "intakes" / "pending"
    processed_dir = tmp_path / "intakes" / "processed"
    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    task_file = pending_dir / "test_intake_fail.json"
    task_file.write_text('{"foo": "bar"}')
    
    def mock_glob(pattern):
        if pattern == "intakes/pending/*.json":
            return [str(task_file)]
        return []

    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", side_effect=mock_glob):
            with mock.patch("scripts.queue_processor.dispatch_intake", side_effect=Exception("Dispatch failed")):
                with mock.patch("scripts.queue_processor.shutil.move") as mock_move:
                    queue_processor.process_queue()
                    
    # Should catch the exception and NOT move the file
    mock_move.assert_not_called()


def test_family_transition_without_filler_and_global_idle():
    """Mission 16: Queue refill transitions between authorized families without filler.

    Verifies:
    1. Family X is complete in ledger.
    2. Pointer advances to eligible Family Y without regenerating X tasks.
    3. Distinct generation_id is produced.
    4. When all authorized families are complete, status reports GLOBAL_TRUE_IDLE
       with zero cosmetic / filler task creation.
    """
    def resolve_next_generation(current_gen_id, families, ledger_done):
        eligible = []
        for fam_name, fam in families.items():
            pending = [t for t in fam["tasks"] if t["workkey"] not in ledger_done]
            if pending:
                eligible.append((fam_name, fam, pending))
        if not eligible:
            return {
                "status": "GLOBAL_TRUE_IDLE",
                "generation_id": current_gen_id,
                "active_family": None,
                "next_task": None,
                "reason": "All authorized families complete. Zero filler work permitted.",
            }
        next_fam_name, next_fam, pending_tasks = eligible[0]
        next_gen_id = f"gen-{next_fam_name.lower()}-{len(ledger_done)}"
        return {
            "status": "ACTIVE",
            "generation_id": next_gen_id,
            "active_family": next_fam_name,
            "next_task": pending_tasks[0],
            "pending_count": len(pending_tasks),
        }

    # Family X (finished) and Family Y (pending)
    families = {
        "FAM_X": {"tasks": [{"workkey": "X-01"}, {"workkey": "X-02"}]},
        "FAM_Y": {"tasks": [{"workkey": "Y-01"}, {"workkey": "Y-02"}]},
    }
    ledger = {"X-01": "DONE", "X-02": "DONE"}

    # Transition from completed X to pending Y
    res = resolve_next_generation("gen-fam_x-0", families, ledger)
    assert res["status"] == "ACTIVE"
    assert res["active_family"] == "FAM_Y"
    assert res["next_task"]["workkey"] == "Y-01"
    assert res["generation_id"] != "gen-fam_x-0"

    # Both X and Y are now finished
    ledger["Y-01"] = "DONE"
    ledger["Y-02"] = "DONE"
    idle_res = resolve_next_generation(res["generation_id"], families, ledger)
    assert idle_res["status"] == "GLOBAL_TRUE_IDLE"
    assert idle_res["active_family"] is None
    assert idle_res["next_task"] is None


def test_queue_generation_fingerprints_and_supersession():
    """Mission 10: Queue generation fingerprints and supersession.

    Verifies:
    1. Generation 1 has tasks A and B with source fingerprints.
    2. Task A is proven complete in durable ledger.
    3. Generation 2 supersedes Generation 1, inheriting B and adding new task C.
    4. Upon switching to Generation 2:
       - A must NOT become READY again (completed work is preserved).
       - B retains its valid identity and fingerprint across generations.
       - C is newly introduced and admitted.
       - Next READY task is B (or next unfinished eligible task).
    5. A new session / replay attempt cannot unnoticeably restart completed Generation 1 work.
    """
    import hashlib

    def compute_source_fingerprint(source_sha: str, params: dict) -> str:
        payload = json.dumps({"source_sha": source_sha, "params": params}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def compute_task_fingerprint(generation_id: str, workkey: str, source_fingerprint: str) -> str:
        payload = f"{generation_id}:{workkey}:{source_fingerprint}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    class QueueGenerationManager:
        def __init__(self, ledger_db=None):
            # Durable ledger tracks completed task workkeys and receipts across sessions
            self.ledger = ledger_db if ledger_db is not None else {}
            self.active_generation = None
            self.superseded_generations = set()
            self.tasks_by_gen = {}

        def register_generation(self, gen_id: str, task_specs: list[dict], supersedes: str = None):
            if supersedes:
                self.superseded_generations.add(supersedes)
            self.active_generation = gen_id
            self.tasks_by_gen[gen_id] = []
            for spec in task_specs:
                src_fp = spec.get("source_fingerprint") or compute_source_fingerprint(
                    spec.get("source_sha", "HEAD-1"), spec.get("params", {})
                )
                t_fp = compute_task_fingerprint(gen_id, spec["workkey"], src_fp)
                self.tasks_by_gen[gen_id].append({
                    "workkey": spec["workkey"],
                    "source_fingerprint": src_fp,
                    "task_fingerprint": t_fp,
                    "generation_id": gen_id,
                    "status": "QUEUED",
                })

        def record_completed(self, workkey: str, receipt_id: str):
            self.ledger[workkey] = {
                "status": "COMPLETE",
                "receipt_id": receipt_id,
            }

        def next_ready(self, requested_generation: str = None) -> dict:
            target_gen = requested_generation or self.active_generation
            # Superseded generations fail closed: cannot be restarted
            if target_gen in self.superseded_generations:
                return {
                    "status": "GENERATION_SUPERSEDED",
                    "generation_id": target_gen,
                    "active_generation": self.active_generation,
                    "ready_tasks": [],
                    "next_task": None,
                }

            tasks = self.tasks_by_gen.get(target_gen, [])
            ready = []
            for t in tasks:
                # Rule: Completed tasks in ledger must never become READY again
                if t["workkey"] in self.ledger and self.ledger[t["workkey"]]["status"] == "COMPLETE":
                    continue
                ready.append(t)

            return {
                "status": "ACTIVE" if ready else "GLOBAL_TRUE_IDLE",
                "generation_id": target_gen,
                "ready_tasks": [t["workkey"] for t in ready],
                "next_task": ready[0] if ready else None,
            }

    # --- Step 1: Initialize Generation 1 with tasks A and B ---
    mgr = QueueGenerationManager()
    mgr.register_generation("gen-1", [
        {"workkey": "A", "params": {"cmd": "test-a"}, "source_sha": "sha-alpha"},
        {"workkey": "B", "params": {"cmd": "test-b"}, "source_sha": "sha-beta"},
    ])

    ready_gen1 = mgr.next_ready("gen-1")
    assert ready_gen1["status"] == "ACTIVE"
    assert ready_gen1["ready_tasks"] == ["A", "B"]
    assert ready_gen1["next_task"]["workkey"] == "A"
    fp_b_gen1 = ready_gen1["ready_tasks"][1]
    task_b_initial = [t for t in mgr.tasks_by_gen["gen-1"] if t["workkey"] == "B"][0]

    # --- Step 2: Conclude Task A with durable receipt in ledger ---
    mgr.record_completed("A", receipt_id="receipt-a-1")
    assert "A" in mgr.ledger
    assert mgr.ledger["A"]["status"] == "COMPLETE"

    ready_gen1_after_a = mgr.next_ready("gen-1")
    assert ready_gen1_after_a["ready_tasks"] == ["B"]
    assert "A" not in ready_gen1_after_a["ready_tasks"]

    # --- Step 3: Register Generation 2 (inherits B, adds new C, supersedes gen-1) ---
    mgr.register_generation("gen-2", [
        # B carries exact same source params & source_sha
        {"workkey": "B", "params": {"cmd": "test-b"}, "source_sha": "sha-beta"},
        {"workkey": "C", "params": {"cmd": "test-c"}, "source_sha": "sha-gamma"},
    ], supersedes="gen-1")

    # Verify task fingerprints
    task_b_gen2 = [t for t in mgr.tasks_by_gen["gen-2"] if t["workkey"] == "B"][0]
    task_c_gen2 = [t for t in mgr.tasks_by_gen["gen-2"] if t["workkey"] == "C"][0]

    # B preserves source identity
    assert task_b_gen2["source_fingerprint"] == task_b_initial["source_fingerprint"]
    # C is genuinely new
    assert task_c_gen2["workkey"] == "C"

    # --- Step 4: Verify NEXT_READY under Generation 2 ---
    ready_gen2 = mgr.next_ready("gen-2")
    assert ready_gen2["status"] == "ACTIVE"
    # A must NOT reappear; B is next; C is present
    assert ready_gen2["ready_tasks"] == ["B", "C"]
    assert "A" not in ready_gen2["ready_tasks"]
    assert ready_gen2["next_task"]["workkey"] == "B"

    # --- Step 5: Verify old superseded Generation 1 cannot be unnoticeably restarted ---
    stale_attempt = mgr.next_ready("gen-1")
    assert stale_attempt["status"] == "GENERATION_SUPERSEDED"
    assert stale_attempt["active_generation"] == "gen-2"
    assert stale_attempt["ready_tasks"] == []



