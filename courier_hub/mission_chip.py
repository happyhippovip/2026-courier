"""Courier Mission Chip — V139 First Green Mission Executor.

Runs one isolated deterministic mission ("Erste grüne Mission") using the real
canonical Controller, Journal, and Verifier.
No external network, 0.00 EUR provider cost, fail-closed CostGate compliance.
"""

from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

from courier_core.controller import Controller
from courier_core.verification import Verdict


EXPECTED_GOLD_BYTES = b"COURIER-V139-MISSION-CHIP-VERIFIED"
EXPECTED_GOLD_SHA256 = hashlib.sha256(EXPECTED_GOLD_BYTES).hexdigest()


def _chip_verifier(adapter: str):
    """Deterministic verifier for the first green mission."""
    def _verify(task, result, home):
        artifacts = result.payload.get("artifacts", [])
        if not artifacts:
            return Verdict(False, "Artefakt fehlt im Ergebnis-Payload")
        for a in artifacts:
            sha = a.get("sha256")
            if not isinstance(sha, str) or len(sha) != 64:
                return Verdict(False, "Ungültiges SHA-256 Format")
            if sha != EXPECTED_GOLD_SHA256:
                return Verdict(False, f"SHA-256 stimmt nicht mit Gold-Referenz überein: {sha[:16]} != {EXPECTED_GOLD_SHA256[:16]}")
            art_path = home / a.get("path", "")
            if (home.is_symlink() or home.parent.is_symlink() or home.parent.parent.is_symlink()
                    or art_path.is_symlink() or art_path.parent.is_symlink()
                    or art_path.parent.parent.is_symlink()):
                return Verdict(False, "Artefaktpfad ist eine Verknuepfung")
            if art_path.is_file():
                content = art_path.read_bytes()
                if content != EXPECTED_GOLD_BYTES:
                    return Verdict(False, "Artefakt-Bytes stimmen nicht mit Gold-Referenz überein")
                if hashlib.sha256(content).hexdigest() != EXPECTED_GOLD_SHA256:
                    return Verdict(False, "Neu berechnete Prüfsumme der Datei weicht ab")
        return Verdict(True, "BYTE_LEVEL_GOLD_VERIFIED: Deterministischer SHA-256 Hash und Byte-Inhalt gegen Gold-Referenz verifiziert")
    return _verify


def run_mission_chip(target_home: Path | None = None) -> dict[str, Any]:
    """Execute the three deterministic checks of 'Erste grüne Mission'."""
    is_temp = target_home is None
    home = target_home or Path(tempfile.mkdtemp(prefix="courier-mission-chip-"))
    home.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    checks = []
    
    ctrl = Controller(home, verifier=_chip_verifier).boot()
    try:
        # -------------------------------------------------------------
        # Stufe 1: Eingabe & Budget-Gate
        # -------------------------------------------------------------
        task_payload = {
            "adapter": "synthetic",
            "params": {
                "mission_name": "Erste grüne Mission",
                "goal": "Deterministische 3-Stufen-Pruefung",
                "estimated_cost_eur": 0.0,
                "write": "mission_result.txt",
                "content": "COURIER-V139-MISSION-CHIP-VERIFIED",
            },
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 30,
        }
        status_code, task_record = ctrl.create_task(task_payload)
        task_id = task_record["task_id"]
        
        checks.append({
            "step": 1,
            "name": "Eingabe & Budget-Gate",
            "passed": status_code == 201,
            "status": "PASS" if status_code == 201 else "FAIL",
            "detail": f"Task {task_id[:16]}... registriert (Kosten: 0,00 EUR, Status: QUEUED)",
            "timestamp": time.time(),
        })

        # -------------------------------------------------------------
        # Stufe 2: Deterministische Ausführung & Artefakt-Hashing
        # -------------------------------------------------------------
        claim_info = ctrl.claim({"worker_id": "worker-local-engine"})
        if not claim_info:
            raise RuntimeError("Lease claim failed")
        
        dispatch_id = claim_info["dispatch_id"]
        ctrl.start({"dispatch_id": dispatch_id, "worker_id": "worker-local-engine"})
        
        artifact_bytes = b"COURIER-V139-MISSION-CHIP-VERIFIED"
        artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
        (home / "mission_result.txt").write_bytes(artifact_bytes)
        
        result_code, result_resp = ctrl.result({
            "dispatch_id": dispatch_id,
            "result_id": "res-chip-v139-01",
            "outcome": "success",
            "artifacts": [{
                "path": "mission_result.txt",
                "sha256": artifact_sha,
                "size_bytes": len(artifact_bytes),
            }],
        })
        
        checks.append({
            "step": 2,
            "name": "Deterministische Ausführung",
            "passed": result_code == 200,
            "status": "PASS" if result_code == 200 else "FAIL",
            "detail": f"Artefakt erzeugt, SHA-256: {artifact_sha[:16]}... (Lease: {dispatch_id[:16]}...)",
            "timestamp": time.time(),
        })

        # -------------------------------------------------------------
        # Stufe 3: Unabhängige Verifikation & Ledger-Eintrag
        # -------------------------------------------------------------
        ctrl.drain()
        final_view = ctrl.task_view(task_id)
        
        is_verified = (
            final_view.get("status") == "COMPLETE" 
            and final_view.get("resolution") == "verified"
            and final_view.get("accepted_result_id") == "res-chip-v139-01"
        )
        
        checks.append({
            "step": 3,
            "name": "Unabhängige Verifikation & Journal-Beleg",
            "passed": is_verified,
            "status": "PASS" if is_verified else "FAIL",
            "detail": f"Status: {final_view.get('status')} | Resolution: {final_view.get('resolution')} (festgeschrieben im Journal)",
            "timestamp": time.time(),
        })

        # Ereignis-Historie für Live-Replay auslesen
        journal_events = []
        for ev in ctrl.journal.events():
            journal_events.append({
                "seq": ev.seq,
                "type": ev.type.value,
                "task_id": ev.task_id,
                "attempt": ev.attempt,
                "dispatch_id": ev.dispatch_id,
                "timestamp": getattr(ev, "created_at", None),
                "payload": ev.payload,
            })

        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        return {
            "mode": "DEMO / LOKAL DETERMINISTISCH",
            "product_ready": False,
            "demo_notice": "Isolierter Prototyp-Lauf. Kein produktiver Multi-Agenten-Betrieb.",
            "mission_name": "Erste grüne Mission",
            "task_id": task_id,
            "overall_status": "COMPLETE" if is_verified else "FAILED",
            "cost_eur": 0.00,
            "duration_ms": duration_ms,
            "checks": checks,
            "verifier_result": {
                "accepted": is_verified,
                "resolution": final_view.get("resolution"),
                "accepted_result_id": final_view.get("accepted_result_id"),
                "artifact_sha256": artifact_sha,
                "artifact_content": "COURIER-V139-MISSION-CHIP-VERIFIED",
            },
            "ledger_receipt": {
                "events_count": len(journal_events),
                "head_seq": journal_events[-1]["seq"] if journal_events else 0,
                "journal_file": str(ctrl.db_path.name),
                "hash": hashlib.sha256(f"{task_id}:{artifact_sha}".encode()).hexdigest(),
            },
            "events_replay": journal_events,
        }
    finally:
        ctrl.stop()


def main(argv: list[str] | None = None) -> int:
    """CLI runner for Mission Chip."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(prog="python -m courier_hub.mission_chip", description="Courier Mission Chip (V139)")
    parser.add_argument("--json", action="store_true", help="Print result as raw JSON")
    parser.add_argument("--home", type=Path, default=None, help="Target directory for courier.db")
    args = parser.parse_args(argv)

    result = run_mission_chip(target_home=args.home)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result.get("overall_status") == "COMPLETE" else 1

    print("=" * 60)
    print("👑 COURIER MISSION CHIP — V139 ERSTE GRÜNE MISSION")
    print(f"Status: {result['overall_status']} | Mode: {result['mode']}")
    print(f"Dauer: {result['duration_ms']} ms | Kosten: {result['cost_eur']:.2f} EUR")
    print("-" * 60)
    for chk in result["checks"]:
        mark = "✓" if chk["passed"] else "✗"
        print(f"[{mark}] Stufe {chk['step']}: {chk['name']}")
        print(f"    Detail: {chk['detail']}")
    print("-" * 60)
    vr = result["verifier_result"]
    print(f"Verifier Resolution: {vr['resolution']}")
    print(f"Artefakt SHA-256:    {vr['artifact_sha256']}")
    lr = result["ledger_receipt"]
    print(f"Ledger Quittung:     {lr['head_seq']} Events in {lr['journal_file']} ({lr['hash'][:16]}...)")
    print("=" * 60)
    return 0 if result.get("overall_status") == "COMPLETE" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

