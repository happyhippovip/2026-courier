"""Fail-closed local self-repair coordination for Courier.

This module never executes a worker.  It classifies structured failures,
persists bounded repair state, and creates a normal queue mission only when a
caller supplies a complete, locally verifiable repair descriptor.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from scripts.courier_safety_dispatcher import MissionQueue, canonical_hash, write_json_atomic


FAILURE_CLASSES = frozenset({
    "REPAIRABLE_INTERNAL_DEFECT", "WORKER_FAILURE", "VERIFICATION_FAILURE",
    "TRANSIENT_LOCAL_FAILURE", "CAPACITY_UNAVAILABLE", "HUMAN_GATE",
    "SAFETY_GATE", "EXTERNAL_ACTION_REQUIRED", "AMBIGUOUS_HIGH_RISK",
    "TERMINAL_FAILURE",
})
NEXT_SAFE_ACTIONS = frozenset({
    "PLAN", "EXECUTE", "VERIFY", "REPAIR", "REPLAN", "WAIT",
    "HUMAN_GATE", "SATISFIED", "FAILED",
})


class CourierSelfRepair:
    """Single-writer durable repair and verification-economics coordinator."""

    def __init__(self, workspace_dir: str | Path, max_repair_attempts: int = 1):
        self.workspace_dir = Path(workspace_dir)
        self.path = self.workspace_dir / "events" / "self-repair" / "state.json"
        self.lock_path = self.path.with_suffix(".lock")
        self.max_repair_attempts = max_repair_attempts
        if not self.path.exists():
            write_json_atomic(self.path, {"schema_version": "1.0", "goals": {}, "proof_cache": {}})

    def _lock(self) -> int:
        try:
            return os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("SELF_REPAIR_BUSY_FAIL_CLOSED") from exc

    def _mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        fd = self._lock()
        try:
            try:
                with open(self.path, encoding="utf-8") as handle:
                    state = json.load(handle)
            except Exception as exc:
                raise RuntimeError("SELF_REPAIR_STATE_CORRUPT_FAIL_CLOSED") from exc
            if not isinstance(state, dict) or not isinstance(state.get("goals"), dict):
                raise RuntimeError("SELF_REPAIR_STATE_CORRUPT_FAIL_CLOSED")
            outcome = fn(state)
            write_json_atomic(self.path, state)
            return outcome
        finally:
            os.close(fd)
            self.lock_path.unlink(missing_ok=True)

    def state_for(self, goal_id: str) -> Optional[dict[str, Any]]:
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle).get("goals", {}).get(goal_id)

    @staticmethod
    def classify_failure(error: Any, *, human_gate: bool = False, safety_gate: bool = False,
                         external_required: bool = False) -> str:
        """Classify only structured error text, never opaque IDs or hashes."""
        if human_gate:
            return "HUMAN_GATE"
        if safety_gate:
            return "SAFETY_GATE"
        if external_required:
            return "EXTERNAL_ACTION_REQUIRED"
        raw_text = str(error or "").strip()
        # An identifier is evidence *about a record*, not a failure message.  In
        # particular, labels or values can happen to contain words such as
        # ``oauth``.  Do not turn that into a human-authentication state.
        if re.fullmatch(
            r"(?:goal_id|mission_id|task_id|correlation_id|failure_id|fingerprint)\s*(?:[:=]|\s)\s*[^\s]+",
            raw_text,
            flags=re.IGNORECASE,
        ) or re.fullmatch(r"[0-9a-f]{32,128}", raw_text, flags=re.IGNORECASE):
            return "AMBIGUOUS_HIGH_RISK"
        text = raw_text.upper()
        if "EMPTY_WRITE_CRITERIA" in text or "INTERNAL_DEFECT" in text:
            return "REPAIRABLE_INTERNAL_DEFECT"
        if "WORKER_FAILURE" in text:
            return "WORKER_FAILURE"
        if "WORKER_UNAVAILABLE" in text or "EXECUTABLE_NOT_FOUND" in text:
            return "CAPACITY_UNAVAILABLE"
        if "VERIFY" in text or "EFFECT" in text or "FRESHNESS" in text:
            return "VERIFICATION_FAILURE"
        if "TIMEOUT" in text or "TEMPORARY" in text:
            return "TRANSIENT_LOCAL_FAILURE"
        if "AUTH" in text or "LOGIN" in text or "OAUTH" in text or "2FA" in text or "CAPTCHA" in text:
            return "HUMAN_GATE"
        if not text:
            return "AMBIGUOUS_HIGH_RISK"
        return "TERMINAL_FAILURE"

    @staticmethod
    def _safe_descriptor(descriptor: Any) -> tuple[bool, str]:
        if not isinstance(descriptor, dict):
            return False, "MISSING_REPAIR_DESCRIPTOR"
        if descriptor.get("local_internal") is not True or descriptor.get("verifiable") is not True:
            return False, "REPAIR_NOT_LOCAL_AND_VERIFIABLE"
        if descriptor.get("requires_write") is not True or descriptor.get("writer_conflict"):
            return False, "REPAIR_WRITER_UNSAFE"
        if descriptor.get("human_gate") or descriptor.get("external_action") or descriptor.get("spend_eur", 0) != 0:
            return False, "REPAIR_GATE_OR_SPEND_UNSAFE"
        criteria = descriptor.get("acceptance_criteria")
        files = descriptor.get("target_files")
        if not isinstance(criteria, dict) or not criteria or not isinstance(files, list) or not files:
            return False, "REPAIR_ACCEPTANCE_INSUFFICIENT"
        for path in files:
            candidate = Path(str(path))
            if str(candidate) in {"", "."} or candidate.is_absolute() or ".." in candidate.parts:
                return False, "REPAIR_PATH_UNSAFE"
        return True, "SAFE"

    def handle_failure(self, *, goal_id: str, original_goal: str, failure: Any,
                       descriptor: Optional[dict[str, Any]] = None,
                       human_gate: bool = False, safety_gate: bool = False,
                       external_required: bool = False) -> dict[str, Any]:
        failure_class = self.classify_failure(
            failure, human_gate=human_gate, safety_gate=safety_gate,
            external_required=external_required,
        )
        fingerprint = canonical_hash({"class": failure_class, "failure": str(failure)})
        safe, reason = self._safe_descriptor(descriptor)

        def update(state: dict[str, Any]) -> dict[str, Any]:
            record = state["goals"].setdefault(goal_id, {
                "goal_id": goal_id, "original_goal": original_goal,
                "repair_attempt_count": 0, "failure_fingerprints": [],
                "next_safe_action": "PLAN",
            })
            record["failure_class"] = failure_class
            record["failure_fingerprint"] = fingerprint
            record["failure_fingerprints"] = list(dict.fromkeys(record["failure_fingerprints"] + [fingerprint]))
            record["updated_at"] = time.time()
            if failure_class == "HUMAN_GATE":
                record["next_safe_action"] = "HUMAN_GATE"
                return {"status": "HUMAN_GATE", "reason": failure_class}
            if failure_class in {"SAFETY_GATE", "EXTERNAL_ACTION_REQUIRED", "AMBIGUOUS_HIGH_RISK", "TERMINAL_FAILURE"}:
                record["next_safe_action"] = "FAILED"
                return {"status": "STOPPED", "reason": failure_class}
            if failure_class != "REPAIRABLE_INTERNAL_DEFECT" or not safe:
                record["next_safe_action"] = "WAIT"
                return {"status": "WAIT", "reason": reason if not safe else failure_class}
            if record["repair_attempt_count"] >= self.max_repair_attempts:
                record["next_safe_action"] = "WAIT"
                return {"status": "REPAIR_BUDGET_EXHAUSTED", "reason": "REPAIR_BUDGET_EXHAUSTED"}

            mission_id = f"repair-{uuid.uuid4()}"
            queue = MissionQueue(self.workspace_dir)
            queue.enqueue({
                "mission_id": mission_id,
                "parent_mission_id": descriptor.get("source_mission_id"),
                "goal": f"Repair internal Courier defect for goal {goal_id}",
                "normalized_task": str(descriptor.get("summary", "Repair bounded internal defect")),
                "capability_required": "implementation",
                "preferred_agent": "GEMINI",
                "requires_write": True,
                "is_heavy": False,
                "risk_class": "SAFE",
                "verification_required": True,
                "task": {
                    "action": "repair_internal_defect",
                    "original_goal_id": goal_id,
                    "failure_fingerprint": fingerprint,
                    "target_files": descriptor["target_files"],
                    "acceptance_criteria": descriptor["acceptance_criteria"],
                    "requires_write": True,
                    "spend_eur": 0,
                },
            })
            record["repair_attempt_count"] += 1
            record["repair_mission_id"] = mission_id
            record["next_safe_action"] = "REPAIR"
            return {"status": "REPAIR_QUEUED", "mission_id": mission_id}

        return self._mutate(update)

    def complete_repair(self, goal_id: str, repair_mission_id: str, *, verified: bool,
                        intake: Any = None, lesson_recorder: Optional[Callable[..., str]] = None) -> dict[str, Any]:
        def update(state: dict[str, Any]) -> dict[str, Any]:
            record = state["goals"].get(goal_id)
            if not record or record.get("repair_mission_id") != repair_mission_id:
                raise RuntimeError("REPAIR_IDENTITY_MISMATCH_FAIL_CLOSED")
            if not verified:
                record["next_safe_action"] = "WAIT"
                return {"status": "REPAIR_UNVERIFIED"}
            record["repair_verified"] = True
            record["next_safe_action"] = "REPLAN"
            return {"status": "REPLAN_ORIGINAL_GOAL", "goal_id": goal_id}

        outcome = self._mutate(update)
        if outcome["status"] == "REPLAN_ORIGINAL_GOAL" and intake is not None:
            intake.set_status(goal_id, "PENDING")
        if outcome["status"] == "REPLAN_ORIGINAL_GOAL" and lesson_recorder is not None:
            lesson_recorder(
                goal="discovery-to-implementation planning", task="self-repair",
                result="repair verified", error="", root_cause="bounded internal defect",
                lesson="Verified repairs resume the original goal rather than satisfying it.",
                reusable_pattern="repair-verify-replan-original-goal",
            )
        return outcome

    def mark_original_goal_satisfied(self, goal_id: str, *, original_acceptance_verified: bool,
                                     intake: Any = None) -> dict[str, Any]:
        if not original_acceptance_verified:
            return {"status": "ORIGINAL_ACCEPTANCE_NOT_VERIFIED"}

        def update(state: dict[str, Any]) -> dict[str, Any]:
            record = state["goals"].get(goal_id)
            if not record or record.get("next_safe_action") not in {"REPLAN", "VERIFY"}:
                raise RuntimeError("ORIGINAL_GOAL_NOT_READY_FOR_SATISFACTION")
            record["next_safe_action"] = "SATISFIED"
            return {"status": "SATISFIED"}

        outcome = self._mutate(update)
        if intake is not None:
            intake.mark_satisfied(goal_id)
        return outcome

    @staticmethod
    def proof_key(*, input_fingerprint: str, workspace_fingerprint: str,
                  acceptance_context: str, method: str) -> str:
        return canonical_hash({"input": input_fingerprint, "workspace": workspace_fingerprint,
                               "context": acceptance_context, "method": method})

    def verification_policy(self, facts: dict[str, Any]) -> str:
        key = self.proof_key(
            input_fingerprint=str(facts.get("input_fingerprint", "")),
            workspace_fingerprint=str(facts.get("workspace_fingerprint", "")),
            acceptance_context=str(facts.get("acceptance_context", "")),
            method=str(facts.get("method", "")),
        )
        with open(self.path, encoding="utf-8") as handle:
            cached = json.load(handle).get("proof_cache", {}).get(key)
        if cached and cached.get("result_fingerprint") == facts.get("result_fingerprint"):
            return "NO_NEW_VERIFY"
        if facts.get("risk") == "HIGH" or facts.get("ambiguity") is True or facts.get("criticality") == "HIGH":
            return "EXPENSIVE_SPECIALIST_REVIEW"
        independent = facts.get("independent_verifiers", [])
        if (facts.get("two_cheap_cost", float("inf")) < facts.get("specialist_cost", float("inf"))
                and len(set(independent)) >= 2
                and len(set(facts.get("proof_sources", []))) >= 2):
            return "TWO_CHEAP_INDEPENDENT_VERIFIERS"
        if facts.get("low_risk_deterministic") is True:
            return "ONE_CHEAP_VERIFY"
        return "TARGETED_PRIMARY_VERIFY"

    def record_proof(self, facts: dict[str, Any], verifier: str, proof_source: str) -> None:
        key = self.proof_key(
            input_fingerprint=str(facts.get("input_fingerprint", "")),
            workspace_fingerprint=str(facts.get("workspace_fingerprint", "")),
            acceptance_context=str(facts.get("acceptance_context", "")),
            method=str(facts.get("method", "")),
        )
        if not verifier or not proof_source or not facts.get("result_fingerprint"):
            raise RuntimeError("INVALID_PROOF_BINDING_FAIL_CLOSED")
        def update(state: dict[str, Any]) -> None:
            state["proof_cache"][key] = {
                "result_fingerprint": facts["result_fingerprint"], "verifier": verifier,
                "proof_source": proof_source, "recorded_at": time.time(),
            }
        self._mutate(update)
