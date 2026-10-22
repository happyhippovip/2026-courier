#!/usr/bin/env python3
"""Local synthetic A→B. Two agent identities, 0 EUR, no network provider.

Prints the definition-of-done lines and exits 0 only when every local
check holds. This does not call a provider, take payment, or sign a wallet.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from courier_runtime.lease import LeaseConflict, LeaseStore, StaleLease
from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    EventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import reduce_store
from scripts.courier_mailbox import process_inbox
from scripts.github_coordination import FileCoordinationStore
from scripts.ledger_v1_bridge import _write_new
from scripts.resource_policy import CostGate


def _event(event_id: str, agent: AgentID, owner: str, created_at: str, event_type: EventType) -> CoordinationEvent:
    return CoordinationEvent(
        event_id=event_id,
        mission_id="mission-ab",
        agent_id=agent,
        host_id=HostID.WINDOWS_REMOTE if agent == AgentID.GOOGLE_WINDOWS else HostID.MAC_LOCAL,
        event_type=event_type,
        status=MissionStatus.WORKING,
        depends_on=[],
        head="abc",
        evidence_ref="synthetic",
        created_at=created_at,
        payload_hash="a" * 64,
        ownership=owner,
    )


def _say(key: str, value: str) -> None:
    print(f"{key}={value}", flush=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="courier-ab-demo-") as raw:
        root = Path(raw)
        ledger_path = root / "coordination_ledger.jsonl"
        store = FileCoordinationStore(ledger_path)
        reducer = reduce_store(store)
        windows = _event(
            "ab-win", AgentID.GOOGLE_WINDOWS, "GOOGLE_WINDOWS",
            "2026-10-22T09:00:00Z", EventType.ASSIGNED,
        )
        mac = _event(
            "ab-mac", AgentID.MUSE_MAC, "MUSE_MAC",
            "2026-10-22T09:01:00Z", EventType.PARTIAL,
        )
        if _write_new(store, reducer, windows) is not True:
            _say("LEDGER", "BLOCKED")
            return 2
        if _write_new(store, reducer, mac) is not False:
            _say("LEDGER", "BLOCKED")
            return 2
        lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) != 1 or json.loads(lines[0])["ownership"] != "GOOGLE_WINDOWS":
            _say("LEDGER", "BLOCKED")
            return 2

        leases = LeaseStore(str(root / "agents.db"))
        try:
            held = leases.acquire("repo://ab", "agent-windows", "wk-ab", ttl_s=60)
            try:
                leases.acquire("repo://ab", "agent-mac", "wk-ab", ttl_s=60)
            except LeaseConflict:
                pass
            else:
                _say("LEASE_FENCING", "BLOCKED")
                return 2
            checked = leases.check_write("repo://ab", held.token, "agent-windows")
            if checked.holder != "agent-windows":
                _say("LEASE_FENCING", "BLOCKED")
                return 2
            try:
                leases.check_write("repo://ab", held.token, "agent-mac")
            except StaleLease:
                pass
            else:
                _say("LEASE_FENCING", "BLOCKED")
                return 2
        finally:
            leases.close()

        allowed = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0)
        blocked = CostGate.evaluate_spend_request("google_antigravity_plus")
        if allowed.get("allowed") is not True or blocked.get("reason") != "UNKNOWN_COST" or blocked.get("allowed") is not False:
            _say("COST_GATE", "BLOCKED")
            return 2

        inbox = root / "inbox.jsonl"
        outbox = root / "outbox.jsonl"
        home = root / "home"
        task = {
            "task_id": "ab-chip",
            "name": "synthetic",
            "estimated_cost_eur": 0.0,
            "status": "PENDING",
        }
        line = json.dumps(task)
        inbox.write_text(line + "\n" + line + "\n", encoding="utf-8")
        results = process_inbox(inbox, outbox, home_path=home)
        if len(results) != 1 or results[0]["execution_result"].get("cost_eur") != 0.0:
            _say("IDEMPOTENCY", "BLOCKED")
            return 2

    _say("A_TO_B_SYNTHETIC", "VERIFIED")
    _say("A_TO_B_REAL_PROVIDER", "NOT_TESTED")
    _say("LEASE_FENCING", "VERIFIED")
    _say("COST_GATE", "VERIFIED")
    _say("LEDGER", "VERIFIED")
    _say("IDEMPOTENCY", "VERIFIED")
    _say("COST_EUR", "0")
    _say("AGENTS", "GOOGLE_WINDOWS,MUSE_MAC")
    _say("PR", "NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
