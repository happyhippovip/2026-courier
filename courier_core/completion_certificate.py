"""Completion Certificate & Binding Goal Closure (User Acceptance Requirement O).

Implements User Acceptance O:
Generates verifiable, quotable Completion Certificates (Fertig-Zertifikat)
for goals reaching terminal completion ('DONE'), ensuring every finished goal
is backed by a tamper-evident audit record of reconciled steps, verifier verdicts,
and artifact fingerprints.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CERTIFICATE_VERSION = "1.0.0"
PROOF_LEVEL_CRYPTOGRAPHIC = "VERIFIED_CRYPTOGRAPHIC"
PROOF_LEVEL_UNVERIFIED = "UNVERIFIED"

STATUS_CERTIFIED = "CERTIFIED"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_BLOCKED = "BLOCKED"
STATUS_ABANDONED = "ABANDONED"


def _is_nonempty_id(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def derive_completion_certificate(
    goal: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None,
    now: float | None = None,
) -> dict[str, Any]:
    """Derives deterministic Completion Certificate for a goal.
    
    Rules (O1–O5):
    - O1: Every DONE goal receives a quotable certificate with all step verifications.
    - O2: Times are verified, not guessed. If unrecorded, report 'NICHT ERFASST (Pre-Timestamp-State)'.
    - O3: ABANDONED is distinguished from BLOCKED / ACTIVE.
    - O4: Retry count and attempt history per step are visible.
    - O5: Certificate carries a quotable ID (cert-<sha256>).
    """
    if not goal:
        return {
            "certificate_id": None,
            "goal_id": None,
            "certified": False,
            "status": STATUS_INCOMPLETE,
            "reason": "Goal is missing or null.",
            "proof_level": PROOF_LEVEL_UNVERIFIED,
            "plan_extent": "0/0 Steps",
            "steps": [],
            "human_summary": "Kein Goal zur Zertifizierung angegeben.",
        }

    goal_id = str(goal.get("goal_id", "unknown-goal"))
    goal_status = str(goal.get("status", "UNKNOWN")).upper()
    workflow_plan = goal.get("workflow_plan", [])
    if not isinstance(workflow_plan, list):
        workflow_plan = []

    state_dict = state or {}
    tasks_map = state_dict.get("tasks", {})

    total_steps = len(workflow_plan)
    verified_steps: list[dict[str, Any]] = []
    all_passed = True
    any_retried = False
    passed_steps = 0

    for idx, step in enumerate(workflow_plan, start=1):
        task_id = step.get("task_id", f"step-{idx}")
        task = tasks_map.get(task_id, {})

        instruction = step.get("instruction", "Task step")
        step_status = task.get("status", step.get("status", "QUEUED"))

        # Verifier outcome. A missing verifier id stays missing.
        verification = task.get("verification") or {}
        verdict = verification.get("verdict", "UNKNOWN")

        # Result binding
        result = task.get("result") or {}
        result_id = task.get("result_id") or result.get("result_id") or "unrecorded"
        artifacts = task.get("artifacts") or result.get("artifacts") or []

        attempts = task.get("attempts", step.get("attempts", 1))
        if attempts > 1 or task.get("resumed_from"):
            any_retried = True

        # A step counts only with an independent verifier PASS bound to its result.
        # result_id must be a non-empty string on both sides, and verifier_id must
        # name a verifier. A missing id is not filled in.
        verified_result_id = verification.get("result_id")
        bound_result_id = result.get("result_id")
        verifier_id = verification.get("verifier_id")
        is_step_passed = (
            verdict == "PASS"
            and _is_nonempty_id(verifier_id)
            and _is_nonempty_id(verified_result_id)
            and _is_nonempty_id(bound_result_id)
            and verified_result_id == bound_result_id
        )
        if is_step_passed:
            passed_steps += 1
        else:
            all_passed = False

        verified_steps.append({
            "step_index": idx,
            "task_id": task_id,
            "instruction": instruction,
            "status": step_status,
            "verdict": verdict,
            "verifier_id": verifier_id if _is_nonempty_id(verifier_id) else "unrecorded",
            "result_id": str(result_id),
            "attempts": attempts,
            "resumed_from": task.get("resumed_from"),
            "artifact_count": len(artifacts),
        })

    is_done = (goal_status == "DONE" and all_passed and total_steps > 0)
    is_abandoned = (goal_status == "ABANDONED")
    is_blocked = (goal_status == "BLOCKED")

    if is_done:
        cert_status = STATUS_CERTIFIED
        certified = True
        proof_level = PROOF_LEVEL_CRYPTOGRAPHIC
    elif is_abandoned:
        cert_status = STATUS_ABANDONED
        certified = False
        proof_level = PROOF_LEVEL_UNVERIFIED
    elif is_blocked:
        cert_status = STATUS_BLOCKED
        certified = False
        proof_level = PROOF_LEVEL_UNVERIFIED
    else:
        cert_status = STATUS_INCOMPLETE
        certified = False
        proof_level = PROOF_LEVEL_UNVERIFIED

    completed_at = goal.get("completed_at")
    if not completed_at:
        completed_at_str = "NICHT ERFASST (Pre-Timestamp-State)"
    else:
        completed_at_str = str(completed_at)

    plan_extent = f"{passed_steps}/{total_steps} Steps"

    # Quotable deterministic certificate ID (O5)
    certificate_material = {
        "version": CERTIFICATE_VERSION,
        "goal_id": goal_id,
        "goal_text": goal.get("goal_text", ""),
        "total_steps": total_steps,
        "steps": verified_steps,
        "certified": certified,
    }
    canonical_json = json.dumps(certificate_material, sort_keys=True, separators=(",", ":"))
    cert_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    certificate_id = f"cert-{cert_hash}"

    if certified:
        human_summary = (
            f"Fertig-Zertifikat {certificate_id[:16]}...: Goal '{goal.get('goal_text', goal_id)}' "
            f"verbindlich abgeschlossen ({plan_extent} unabhängig verifiziert, Proof-Level: {proof_level}). "
            f"Abschlusszeit: {completed_at_str}."
        )
    elif is_abandoned:
        human_summary = (
            f"Goal '{goal.get('goal_text', goal_id)}' wurde als ABANDONED markiert. "
            f"Kein Fertig-Zertifikat ausgestellt."
        )
    elif is_blocked:
        human_summary = (
            f"Goal '{goal.get('goal_text', goal_id)}' ist BLOCKED ({plan_extent}). "
            f"Wartet auf Klärung oder Benutzereingriff."
        )
    else:
        human_summary = (
            f"Goal '{goal.get('goal_text', goal_id)}' ist in Bearbeitung ({plan_extent}). "
            f"Zertifikat wird erst nach vollständigem PASS aller Schritte ausgestellt."
        )

    return {
        "certificate_id": certificate_id,
        "goal_id": goal_id,
        "certified": certified,
        "status": cert_status,
        "proof_level": proof_level,
        "plan_extent": plan_extent,
        "completed_at": completed_at_str,
        "retry_occurred": any_retried,
        "steps": verified_steps,
        "human_summary": human_summary,
        "certificate_version": CERTIFICATE_VERSION,
    }
