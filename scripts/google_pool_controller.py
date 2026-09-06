#!/usr/bin/env python3
"""Four-pool, local-only Google capacity continuity controller.

This tool manages aliases and local continuation checkpoints only.  It never
opens a browser, touches a provider session, stores authentication material,
or claims that a human login/entitlement has been verified.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import uuid
from pathlib import Path
from typing import Any

try:
    from multi_account_workspace_switch import (
        ALLOWED_POOLS, DEFAULT_WORKSPACE_PATH, MultiAccountWorkspaceSwitchEngine,
        ThreePoolResourceRegistry, atomic_write_json,
    )
except ImportError:
    from scripts.multi_account_workspace_switch import (
        ALLOWED_POOLS, DEFAULT_WORKSPACE_PATH, MultiAccountWorkspaceSwitchEngine,
        ThreePoolResourceRegistry, atomic_write_json,
    )


CAPACITY_STATES = {"UNKNOWN", "AVAILABLE", "LOW", "EXHAUSTED", "RESET_PENDING", "UNAVAILABLE", "NOT_CONFIGURED"}


class GooglePoolController:
    def __init__(self, workspace: Path = DEFAULT_WORKSPACE_PATH):
        self.workspace = workspace.resolve()
        self.engine = MultiAccountWorkspaceSwitchEngine(self.workspace)
        self.registry = ThreePoolResourceRegistry(self.workspace)
        self.state_file = self.workspace / "events" / "resource-intelligence" / "google_pool_switch_state.json"

    def _state(self) -> dict[str, Any]:
        try:
            result = json.loads(self.state_file.read_text(encoding="utf-8"))
            return result if isinstance(result, dict) else {}
        except (OSError, ValueError):
            return {}

    def status(self) -> dict[str, Any]:
        return {"canonical_workspace": str(self.workspace), "pools": self.registry.load_registry(), "switch_state": self._state(), "credentials_stored": False}

    def recommend(self, current_pool: str) -> dict[str, Any]:
        pools = self.registry.load_registry()
        current = pools.get(current_pool, {})
        current_state = current.get("capacity_state", "UNKNOWN")
        exhausted = current_state in {"EXHAUSTED", "UNAVAILABLE"} or current.get("five_hour_remaining_pct") == 0
        if not exhausted and current_state not in {"LOW", "RESET_PENDING"}:
            return {"status": "CONTINUE_CURRENT_POOL", "current_pool": current_pool, "recommended_pool": current_pool, "account_switch_required": False}
        for alias in sorted(ALLOWED_POOLS):
            record = pools.get(alias, {})
            if alias != current_pool and record.get("authorization_state") == "AUTHORIZED" and record.get("verification_state") == "VERIFIED" and record.get("capacity_state") == "AVAILABLE":
                return {"status": "ACCOUNT_SWITCH_RECOMMENDED", "current_pool": current_pool, "current_pool_state": current_state, "recommended_pool": alias, "alternative_pool_available": True, "account_switch_required": True}
        return {"status": "RESOURCE_WAIT", "current_pool": current_pool, "current_pool_state": current_state, "recommended_pool": None, "alternative_pool_available": False, "account_switch_required": False, "no_provider_call_started": True}

    def prepare_switch(self, from_pool: str, to_pool: str, task_id: str = "NONE") -> dict[str, Any]:
        if from_pool not in ALLOWED_POOLS or to_pool not in ALLOWED_POOLS or from_pool == to_pool:
            return {"status": "HUMAN_GATE_REQUIRED", "reason": "INVALID_POOL_SWITCH"}
        target = self.registry.get_pool(to_pool) or {}
        if target.get("authorization_state") == "NOT_CONFIGURED":
            return {"status": "PAYMENT_APPROVAL_REQUIRED", "reason": "TARGET_POOL_NOT_CONFIGURED", "target_pool": to_pool}
        safety = self.engine.check_active_task_safety()
        if not safety.get("can_switch"):
            return {"status": "SWITCH_BLOCKED_ACTIVE_WRITE", "reason": safety.get("reason")}
        workspace = self.engine.compute_workspace_fingerprint()
        checkpoint = {
            "checkpoint_id": f"pool-switch-{uuid.uuid4().hex[:16]}", "task_id": task_id,
            "chief_turn_id": "UNKNOWN", "correlation_id": "UNKNOWN", "current_phase": "SWITCH_REQUESTED",
            "completed_phases": [], "remaining_phases": ["HUMAN_AUTH", "VERIFYING_NEW_POOL", "CONTINUATION_READY"],
            "last_successful_result": None, "working_files": [], "git_head": workspace["head_sha"],
            "git_status_fingerprint": workspace["git_fingerprint"], "workspace_fingerprint": workspace["composite_fingerprint"],
            "resource_pool": from_pool, "next_safe_action": "Human performs supported provider login, then verify-switch",
            "risk_class": "LOW", "human_gate_state": "HUMAN_AUTH_REQUIRED", "money_gate_state": "ZERO_SPEND_ONLY",
            "provider_chat_history_included": False,
        }
        atomic_write_json(self.workspace / "events" / "resource-intelligence" / "continuation-checkpoints" / f"{checkpoint['checkpoint_id']}.json", checkpoint)
        state = {"state": "HUMAN_AUTH_REQUIRED", "from_pool": from_pool, "to_pool": to_pool, "checkpoint": checkpoint, "prepared_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        atomic_write_json(self.state_file, state)
        self.registry.update_pool(from_pool, continuation_checkpoint=checkpoint["checkpoint_id"])
        return {"status": "SAFE_TO_SWITCH", "work_preserved": True, "account_switch_required": True, "checkpoint_id": checkpoint["checkpoint_id"], "from_pool": from_pool, "to_pool": to_pool}

    def verify_switch(self, pool: str, human_auth_confirmed: bool = False) -> dict[str, Any]:
        state = self._state()
        if pool not in ALLOWED_POOLS or state.get("to_pool") != pool:
            return {"status": "NEW_POOL_NOT_VERIFIED", "reason": "NO_MATCHING_PREPARED_SWITCH"}
        checkpoint = state.get("checkpoint", {})
        workspace = self.engine.compute_workspace_fingerprint()
        if workspace.get("composite_fingerprint") != checkpoint.get("workspace_fingerprint"):
            return {"status": "WORKSPACE_MISMATCH", "reason": "CHECKPOINT_FINGERPRINT_MISMATCH"}
        if not human_auth_confirmed:
            return {"status": "AUTH_NOT_CONFIRMED", "reason": "SUPPORTED_HUMAN_LOGIN_MUST_BE_CONFIRMED", "workspace_verified": True}
        self.registry.update_pool(pool, workspace_verified=True, switch_ready=True, verification_state="VERIFIED", authorization_state="AUTHORIZED", capacity_state="AVAILABLE", status="VERIFIED", continuation_checkpoint=checkpoint.get("checkpoint_id"))
        state.update({"state": "CONTINUATION_READY", "verified_at": dt.datetime.now(dt.timezone.utc).isoformat()})
        atomic_write_json(self.state_file, state)
        return {"status": "CONTINUATION_READY", "same_workspace": True, "work_preserved": True, "pool": pool, "next_safe_action": checkpoint.get("next_safe_action")}

    def register_observation(self, pool: str, capacity_state: str, five_hour: float | None = None, weekly: float | None = None) -> dict[str, Any]:
        if pool not in ALLOWED_POOLS or capacity_state not in CAPACITY_STATES:
            return {"status": "REJECTED", "reason": "INVALID_NON_SECRET_OBSERVATION"}
        record = self.registry.update_pool(pool, capacity_state=capacity_state, availability="RATE_LIMITED" if capacity_state == "EXHAUSTED" else "AVAILABLE" if capacity_state == "AVAILABLE" else "UNKNOWN", five_hour_remaining_pct=five_hour, weekly_remaining_pct=weekly)
        return {"status": "OBSERVATION_RECORDED", "pool": pool, "capacity_state": record["capacity_state"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Local-only four-pool continuity controller")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("status")
    recommend = subs.add_parser("recommend"); recommend.add_argument("--current", required=True, choices=sorted(ALLOWED_POOLS))
    continue_cmd = subs.add_parser("continue"); continue_cmd.add_argument("--current", required=True, choices=sorted(ALLOWED_POOLS))
    prepare = subs.add_parser("prepare-switch"); prepare.add_argument("--from", dest="from_pool", required=True, choices=sorted(ALLOWED_POOLS)); prepare.add_argument("--to", required=True, choices=sorted(ALLOWED_POOLS)); prepare.add_argument("--task-id", default="NONE")
    verify = subs.add_parser("verify-switch"); verify.add_argument("--pool", required=True, choices=sorted(ALLOWED_POOLS)); verify.add_argument("--human-auth-confirmed", action="store_true")
    observe = subs.add_parser("register-observation"); observe.add_argument("--pool", required=True, choices=sorted(ALLOWED_POOLS)); observe.add_argument("--capacity-state", required=True, choices=sorted(CAPACITY_STATES)); observe.add_argument("--five-hour", type=float); observe.add_argument("--weekly", type=float)
    args = parser.parse_args(); controller = GooglePoolController()
    if args.command == "status": result = controller.status()
    elif args.command in {"recommend", "continue"}:
        result = controller.recommend(args.current)
        result["provider_call_started"] = False
        result["continuation_mode"] = "LOCAL_RECOMMENDATION_ONLY"
    elif args.command == "prepare-switch": result = controller.prepare_switch(args.from_pool, args.to, args.task_id)
    elif args.command == "verify-switch": result = controller.verify_switch(args.pool, args.human_auth_confirmed)
    else: result = controller.register_observation(args.pool, args.capacity_state, args.five_hour, args.weekly)
    print(json.dumps(result, indent=2)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
