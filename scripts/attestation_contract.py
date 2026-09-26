"""Runtime-identity and result-attestation contract for the verification plane.

The server binds every dispatched task to its own runtime identity
(``server_binding``) and mints an attestation receipt only when an
independent verifier confirms the exact result on that binding.  These
helpers own the three derivations so the binding cannot drift between
the claim, verify, and attestation-read paths.
"""

from __future__ import annotations

import hashlib
import json


class ContractError(ValueError):
    """An attestation value cannot be derived or bound."""


def principal(secret: str) -> str:
    """Derive the stable principal id for an API secret.

    Mirrors ``server.app.get_auth_principal`` byte-for-byte: the principal
    is the hash of the full ``Bearer <secret>`` authorization header, so a
    principal observed from a request always equals the principal derived
    from the matching configured secret.
    """
    if not isinstance(secret, str) or not secret:
        raise ContractError("a non-empty secret string is required")
    return "principal_" + hashlib.sha256(f"Bearer {secret}".encode()).hexdigest()


def fingerprint(result: dict) -> str:
    """Deterministic sha256 over the canonical durable-result payload."""
    if not isinstance(result, dict):
        raise ContractError("result must be a dict")
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


_RECEIPT_IDENTITY_KEYS = (
    "goal_id",
    "task_id",
    "attempt_id",
    "dispatch_id",
    "execution_ref",
)


def current_receipt(
    receipt: dict,
    task: dict,
    goal: dict,
    binding: dict,
    producer_principal: str,
    verifier_principal: str,
) -> bool:
    """Return True only if ``receipt`` still describes the live ``task``.

    Fail-closed: any type mismatch raises, any content drift returns False
    so the caller answers 409 (stale/provenance mismatch) instead of
    serving a receipt for a superseded result, a rebound task, or a
    replaced runtime.
    """
    for name, value in (
        ("receipt", receipt),
        ("task", task),
        ("goal", goal),
        ("binding", binding),
    ):
        if not isinstance(value, dict):
            raise ContractError(f"{name} must be a dict")
    if receipt.get("verdict") != "PASS":
        return False
    if any(receipt.get(key) != task.get(key) for key in _RECEIPT_IDENTITY_KEYS):
        return False
    stored = task.get("result")
    if not isinstance(stored, dict):
        return False
    if receipt.get("result_id") != stored.get("result_id"):
        return False
    if receipt.get("result_sha256") != fingerprint(stored):
        return False
    if receipt.get("binding") != binding:
        return False
    if receipt.get("producer_principal") != producer_principal:
        return False
    if receipt.get("verifier_principal") != verifier_principal:
        return False
    if receipt.get("goal_id") != task.get("goal_id"):
        return False
    if not goal:
        return False
    plan = goal.get("workflow_plan")
    if plan:
        step_ids = {
            step.get("task_id") for step in plan if isinstance(step, dict)
        }
        if task.get("task_id") not in step_ids:
            return False
    return True
