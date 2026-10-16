"""Courier Runtime: Multi-Task Workflow Continuation Engine.

Orchestrates sequential, dependent multi-task workflows through the canonical
L2 Courier Controller (courier_core.controller.Controller).

Enforces:
1. Single workflow admission initializes the multi-stage pipeline.
2. Stage A produces deterministic test data.
3. Stage B consumes and processes Stage A's output artifact.
4. Stage C validates Stage B's processed result against ground-truth invariants.
5. Autonomous continuation: valid verification of stage N immediately admits and triggers stage N+1.
6. Zero human intervention: Human-Relay-Count remains strictly 0.
7. Real local execution metrics and persistent SQLite journal evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from courier_core.controller import Controller
from courier_core.verification import Verdict


@dataclass(frozen=True)
class WorkflowStage:
    workkey: str
    stage_id: str  # "A", "B", "C"
    action: str    # "produce", "process", "validate"
    adapter: str = "synthetic"
    depends_on: List[str] = field(default_factory=list)


@dataclass
class WorkflowAdmissionPacket:
    workflow_id: str
    stages: List[WorkflowStage]
    initiated_by: str = "workflow-intake-single-admission"
    timestamp: float = field(default_factory=time.time)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def workflow_stage_verifier(task, result, home: Path) -> Verdict:
    """Verifies that each stage produced its required physical evidence correctly."""
    artifacts = result.payload.get("artifacts", [])
    if not artifacts:
        return Verdict(False, "MISSING_ARTIFACTS: No artifacts reported in result")

    for art in artifacts:
        rel_path = art.get("path")
        claimed_sha = art.get("sha256")
        if not rel_path or not claimed_sha:
            return Verdict(False, "INVALID_ARTIFACT_SPEC: Missing path or sha256")

        full_path = (home / rel_path).resolve()
        if not str(full_path).startswith(str(home.resolve())):
            return Verdict(False, f"PATH_TRAVERSAL: Artifact {rel_path} escapes home {home}")
        if not full_path.is_file():
            return Verdict(False, f"FILE_NOT_FOUND: Artifact {rel_path} does not exist on disk")

        actual_sha = sha256_file(full_path)
        if actual_sha != claimed_sha:
            return Verdict(False, f"SHA_MISMATCH: Claimed {claimed_sha} != actual {actual_sha}")

        # Content validation based on task parameters
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = json.load(f)
        except Exception as e:
            return Verdict(False, f"INVALID_JSON: Artifact is not valid JSON: {e}")

        stage = task.params.get("stage")
        if stage == "A":
            if "raw_numbers" not in content or not isinstance(content["raw_numbers"], list):
                return Verdict(False, "STAGE_A_SCHEMA_INVALID: Missing raw_numbers list")
        elif stage == "B":
            if "sum" not in content or "mean" not in content:
                return Verdict(False, "STAGE_B_SCHEMA_INVALID: Missing computed sum/mean")
        elif stage == "C":
            if content.get("status") != "VALIDATED" or not content.get("validation_passed"):
                return Verdict(False, "STAGE_C_VALIDATION_FAILED: Validation checks did not pass")

    return Verdict(True, "All stage artifact and content invariants verified successfully")


class WorkflowContinuationEngine:
    """Coordinates sequential multi-task execution over the Courier Controller."""

    def __init__(
        self,
        controller: Controller,
        home: Path,
        worker_id: str = "surrogate-worker-a018",
        use_subprocess_runner: bool = False,
    ):
        self.controller = controller
        self.home = Path(home)
        self.worker_id = worker_id
        self.use_subprocess_runner = use_subprocess_runner
        self.completed_stages: Dict[str, Dict[str, Any]] = {}
        self.execution_counts: Dict[str, int] = {}
        self.subprocess_runs: List[Dict[str, Any]] = []
        self.receipts_written: List[Path] = []
        self.human_relay_count: int = 0
        self.artifacts_produced: Dict[str, Path] = {}

    def recover_from_ledger(self, packet: WorkflowAdmissionPacket) -> Dict[str, str]:
        """Recovers workflow progress and completed artifacts from the Controller ledger."""
        from courier_core.state_machine import ACTIVE_LEASE, TaskStatus

        recovered = {}
        for stage in packet.stages:
            idemp_key = f"{packet.workflow_id}:{stage.workkey}"
            task_id = "task-" + hashlib.sha256(idemp_key.encode("utf-8")).hexdigest()[:32]
            task_rec = self.controller.journal.task(task_id)
            if task_rec is None:
                continue

            if task_rec.status is TaskStatus.COMPLETE:
                res_event = self.controller.journal.get_event_by_dedupe_key(
                    f"result:{task_rec.dispatch_id}:{task_rec.accepted_result_id}"
                )
                artifacts = res_event.payload.get("artifacts", []) if res_event else []
                art = artifacts[0] if artifacts else {}
                self.completed_stages[stage.workkey] = {
                    "workkey": stage.workkey,
                    "stage_id": stage.stage_id,
                    "task_id": task_id,
                    "dispatch_id": task_rec.dispatch_id,
                    "result_id": task_rec.accepted_result_id,
                    "artifact_rel_path": art.get("path"),
                    "artifact_sha": art.get("sha256"),
                    "status": "COMPLETE",
                }
                if stage.workkey not in self.execution_counts:
                    self.execution_counts[stage.workkey] = 1
                if art.get("path"):
                    self.artifacts_produced[stage.workkey] = self.home / art["path"]
                recovered[stage.workkey] = "COMPLETE"
            elif task_rec.status in ACTIVE_LEASE:
                recovered[stage.workkey] = task_rec.status.value

        return recovered

    def admit_and_run(self, packet: WorkflowAdmissionPacket) -> Dict[str, Any]:
        """Performs single admission and drives A -> B -> C continuation to completion."""
        from courier_core.state_machine import ACTIVE_LEASE, TaskStatus

        print(f"\n[WORKFLOW ADMIT] Admission / continuation for workflow '{packet.workflow_id}' with {len(packet.stages)} stages.")

        # Reconstruct any existing progress from ledger
        self.recover_from_ledger(packet)

        for stage in packet.stages:
            if stage.workkey not in self.execution_counts:
                self.execution_counts[stage.workkey] = 0

        # Autonomous continuation loop
        for idx, stage in enumerate(packet.stages):
            print(f"\n--- [CONTINUATION STAGE {stage.stage_id}] Workkey: {stage.workkey} (Depends on: {stage.depends_on}) ---")

            # Check if stage is already verified and COMPLETE in ledger
            if stage.workkey in self.completed_stages and self.completed_stages[stage.workkey]["status"] == "COMPLETE":
                print(f"   -> Stage {stage.stage_id} ({stage.workkey}) already COMPLETE in ledger, preserving state.")
                continue

            # Dependency verification
            for dep in stage.depends_on:
                if dep not in self.completed_stages or self.completed_stages[dep]["status"] != "COMPLETE":
                    raise RuntimeError(f"CANNOT_CONTINUE: Dependency '{dep}' is not completed before stage '{stage.workkey}'")

            # 1. Create task on Controller with stage-specific parameters
            stage_params = {
                "stage": stage.stage_id,
                "action": stage.action,
                "workkey": stage.workkey,
                "workflow_id": packet.workflow_id,
            }

            if stage.stage_id == "A":
                stage_params["raw_numbers"] = [10, 20, 30, 40]
                stage_params["write"] = "data_a.json"
                stage_params["content"] = json.dumps({
                    "stage": "A",
                    "workkey": stage.workkey,
                    "raw_numbers": [10, 20, 30, 40],
                    "count": 4,
                    "created_at": time.time(),
                }, indent=2)
            elif stage.stage_id == "B":
                dep_a = self.completed_stages[stage.depends_on[0]]
                stage_params["input_artifact"] = dep_a["artifact_rel_path"]
                # Process A's data
                a_file = self.home / dep_a["artifact_rel_path"]
                a_content = json.loads(a_file.read_text(encoding="utf-8"))
                numbers = a_content["raw_numbers"]
                total = sum(numbers)
                mean = total / len(numbers)
                stage_params["write"] = "data_b.json"
                stage_params["content"] = json.dumps({
                    "stage": "B",
                    "workkey": stage.workkey,
                    "source_workkey": stage.depends_on[0],
                    "sum": total,
                    "mean": mean,
                    "count": len(numbers),
                    "min": min(numbers),
                    "max": max(numbers),
                    "processed_at": time.time(),
                }, indent=2)
            elif stage.stage_id == "C":
                dep_b = self.completed_stages[stage.depends_on[0]]
                stage_params["input_artifact"] = dep_b["artifact_rel_path"]
                # Validate B's data
                b_file = self.home / dep_b["artifact_rel_path"]
                b_content = json.loads(b_file.read_text(encoding="utf-8"))
                check_sum = b_content["sum"] == 100
                check_mean = b_content["mean"] == 25.0
                check_count = b_content["count"] == 4
                all_passed = check_sum and check_mean and check_count
                stage_params["write"] = "data_c.json"
                stage_params["content"] = json.dumps({
                    "stage": "C",
                    "workkey": stage.workkey,
                    "validated_workkey": stage.depends_on[0],
                    "status": "VALIDATED" if all_passed else "FAILED",
                    "validation_passed": all_passed,
                    "checks": {
                        "check_sum_equals_100": check_sum,
                        "check_mean_equals_25": check_mean,
                        "check_count_equals_4": check_count,
                    },
                    "validated_at": time.time(),
                }, indent=2)

            task_body = {
                "adapter": stage.adapter,
                "params": stage_params,
                "effect_class": "idempotent",
                "max_attempts": 2,
                "lease_ttl_s": 60,
                "idempotency_key": f"{packet.workflow_id}:{stage.workkey}",
            }

            idemp_key = f"{packet.workflow_id}:{stage.workkey}"
            expected_task_id = "task-" + hashlib.sha256(idemp_key.encode("utf-8")).hexdigest()[:32]
            existing_task = self.controller.journal.task(expected_task_id)

            if existing_task is not None and existing_task.status in ACTIVE_LEASE:
                # Task is in-flight across restart (already created and claimed)
                task_id = existing_task.task_id
                dispatch_id = existing_task.dispatch_id
                print(f"   -> Resuming in-flight stage {stage.stage_id} under active lease {dispatch_id} ({existing_task.status.value}).")
            else:
                st, res = self.controller.create_task(task_body)
                assert st in (200, 201), f"Task creation failed with status {st}: {res}"
                task_id = res["task_id"]

                # 2. Worker claims task
                lease = self.controller.claim({"worker_id": self.worker_id})
                assert lease is not None, "Failed to claim task"
                assert lease["task_id"] == task_id
                dispatch_id = lease["dispatch_id"]

                # 3. Worker starts task
                start_resp = self.controller.start({"dispatch_id": dispatch_id})
                assert start_resp["status"] in ("STARTED", "ALREADY_STARTED")

            # 4. Physical execution by worker (either real subprocess or in-process)
            workdir = self.home / "artifacts" / dispatch_id
            workdir.mkdir(parents=True, exist_ok=True)
            out_path = workdir / f"data_{stage.stage_id.lower()}.json"

            if out_path.is_file():
                print(f"   -> Stage {stage.stage_id} artifact already produced on disk ({out_path.name}), skipping duplicate execution.")
                self.artifacts_produced[stage.workkey] = out_path
            else:
                self.execution_counts[stage.workkey] += 1
                if self.use_subprocess_runner:
                    import subprocess
                    import sys
                    from courier_worker import adapter_bridge as bridge

                    req_path = self.home / "run" / "requests" / f"{dispatch_id}.json"
                    req_path.parent.mkdir(parents=True, exist_ok=True)
                    rep_path = self.home / "run" / "reports" / f"{dispatch_id}.json"
                    rep_path.parent.mkdir(parents=True, exist_ok=True)

                    req_data = {
                        "adapter": stage.adapter,
                        "params": stage_params,
                        "attempt": 1,
                        "task_id": task_id,
                        "dispatch_id": dispatch_id,
                        "effect_key": f"eff-{dispatch_id}",
                        "workdir": str(workdir),
                        "report": str(rep_path),
                    }
                    req_path.write_text(json.dumps(req_data), encoding="utf-8")

                    cmd = [sys.executable, bridge.RUNNER_SCRIPT, str(req_path)]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    assert proc.returncode == 0, f"Subprocess runner failed (exit {proc.returncode}): {proc.stderr}"
                    assert out_path.is_file(), f"Subprocess runner did not create artifact {out_path}"
                    assert rep_path.is_file(), f"Subprocess runner did not create report {rep_path}"

                    self.subprocess_runs.append({
                        "stage": stage.stage_id,
                        "workkey": stage.workkey,
                        "cmd": cmd,
                        "returncode": proc.returncode,
                        "artifact": str(out_path),
                        "report": str(rep_path),
                    })
                    self.artifacts_produced[stage.workkey] = out_path
                else:
                    if stage.stage_id == "A":
                        data_a = {
                            "stage": "A",
                            "workkey": stage.workkey,
                            "raw_numbers": [10, 20, 30, 40],
                            "count": 4,
                            "created_at": time.time(),
                        }
                        out_path.write_text(json.dumps(data_a, indent=2), encoding="utf-8")
                        self.artifacts_produced[stage.workkey] = out_path

                    elif stage.stage_id == "B":
                        dep_a_info = self.completed_stages[stage.depends_on[0]]
                        a_file = self.home / dep_a_info["artifact_rel_path"]
                        assert a_file.is_file(), f"Input file {a_file} does not exist"
                        a_content = json.loads(a_file.read_text(encoding="utf-8"))

                        numbers = a_content["raw_numbers"]
                        total = sum(numbers)
                        mean = total / len(numbers)

                        data_b = {
                            "stage": "B",
                            "workkey": stage.workkey,
                            "source_workkey": stage.depends_on[0],
                            "sum": total,
                            "mean": mean,
                            "count": len(numbers),
                            "min": min(numbers),
                            "max": max(numbers),
                            "processed_at": time.time(),
                        }
                        out_path.write_text(json.dumps(data_b, indent=2), encoding="utf-8")
                        self.artifacts_produced[stage.workkey] = out_path

                    elif stage.stage_id == "C":
                        dep_b_info = self.completed_stages[stage.depends_on[0]]
                        b_file = self.home / dep_b_info["artifact_rel_path"]
                        assert b_file.is_file(), f"Input file {b_file} does not exist"
                        b_content = json.loads(b_file.read_text(encoding="utf-8"))

                        check_sum = b_content["sum"] == 100
                        check_mean = b_content["mean"] == 25.0
                        check_count = b_content["count"] == 4
                        all_passed = check_sum and check_mean and check_count

                        data_c = {
                            "stage": "C",
                            "workkey": stage.workkey,
                            "validated_workkey": stage.depends_on[0],
                            "status": "VALIDATED" if all_passed else "FAILED",
                            "validation_passed": all_passed,
                            "checks": {
                                "check_sum_equals_100": check_sum,
                                "check_mean_equals_25": check_mean,
                                "check_count_equals_4": check_count,
                            },
                            "validated_at": time.time(),
                        }
                        out_path.write_text(json.dumps(data_c, indent=2), encoding="utf-8")
                        self.artifacts_produced[stage.workkey] = out_path

            file_sha = sha256_file(out_path)
            rel_artifact_path = f"artifacts/{dispatch_id}/{out_path.name}"

            # 5. Worker reports result to Controller
            res_body = {
                "dispatch_id": dispatch_id,
                "result_id": f"res-{dispatch_id}",
                "outcome": "success",
                "artifacts": [{"path": rel_artifact_path, "sha256": file_sha}],
            }
            res_code, res_resp = self.controller.result(res_body)
            assert res_code == 200
            assert res_resp["status"] == "ACCEPTED_FOR_VERIFY"

            # 6. Controller verifies and transitions task to COMPLETE
            self.controller.drain()
            task_rec = self.controller.journal.task(task_id)
            assert task_rec.status.value == "COMPLETE", f"Task {task_id} did not reach COMPLETE (got {task_rec.status.value})"

            # 7. Record durable receipt file on disk
            receipt_dir = self.home / "receipts"
            receipt_dir.mkdir(parents=True, exist_ok=True)
            receipt_file = receipt_dir / f"rcpt-{dispatch_id}.json"
            receipt_data = {
                "task_id": task_id,
                "dispatch_id": dispatch_id,
                "stage_id": stage.stage_id,
                "workkey": stage.workkey,
                "result_id": f"res-{dispatch_id}",
                "outcome": "success",
                "artifact_path": rel_artifact_path,
                "artifact_sha256": file_sha,
                "timestamp": time.time(),
            }
            receipt_file.write_text(json.dumps(receipt_data, indent=2), encoding="utf-8")
            self.receipts_written.append(receipt_file)

            # 8. Record stage completion in memory
            self.completed_stages[stage.workkey] = {
                "workkey": stage.workkey,
                "stage_id": stage.stage_id,
                "task_id": task_id,
                "dispatch_id": dispatch_id,
                "result_id": f"res-{dispatch_id}",
                "artifact_rel_path": rel_artifact_path,
                "artifact_sha": file_sha,
                "receipt_path": f"receipts/rcpt-{dispatch_id}.json",
                "status": "COMPLETE",
            }
            print(f"   -> Stage {stage.stage_id} verified & COMPLETE! Artifact: {rel_artifact_path} (SHA: {file_sha[:12]}...)")

        print(f"\n[WORKFLOW COMPLETE] All {len(packet.stages)} stages finished with Human-Relay-Count=0.")

        return {
            "workflow_id": packet.workflow_id,
            "status": "COMPLETED",
            "stages_completed": [s.workkey for s in packet.stages],
            "workkeys": {s.stage_id: s.workkey for s in packet.stages},
            "execution_counts": dict(self.execution_counts),
            "total_local_executions": sum(self.execution_counts.values()),
            "actual_process_starts": len(self.subprocess_runs),
            "subprocess_runs": self.subprocess_runs,
            "receipts": [str(r) for r in self.receipts_written],
            "model_calls": 0,
            "human_relay_count": self.human_relay_count,
            "completed_stages": self.completed_stages,
        }
