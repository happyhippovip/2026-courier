#!/usr/bin/env python3
"""Real production router-dispatch path for Codex tasks.

Pipeline:
  1. Register/refresh CODEX worker in LiveWorkerRegistry
  2. Inject Opportunity into OpportunityQueue
  3. NextSafeWorkRouter.evaluate_next_safe_work() selects worker + host
  3b. Windows health check gate (route/TCP22/SSH/project) with bounded recovery
  4. Acquire authoritative scope lease via CanonicalAuthority
  5. Build validated envelope with provenance receipt + authority lease binding
  6. Drop envelope into events/dispatch/
  7. Invoke run_codex_bridge --auto-discover --real-codex
  8. Read result from events/processed/ and verify provenance/task_id
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))


from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState
from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.canonical_authority import CanonicalAuthority
from scripts.windows_health_gate import check_windows_health, checkpoint_task


def _stable_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main(task_id: str | None = None, description: str | None = None):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ── 1. Ensure CODEX worker registered and SAFE_IDLE ──
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    registry.register_worker(worker_id="CODEX", role="specialist architecture", provider="local")
    w = registry.get_worker("CODEX")
    if w:
        w.state = WorkerState.SAFE_IDLE.value
        registry._save_worker_record(w)
    print("[STEP 1] CODEX worker registered: SAFE_IDLE")

    # ── 2. Inject Opportunity ──
    if not task_id:
        ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        task_id = f"TASK_FOUNDATION_{ts}"
    if not description:
        description = "Inspect Windows-AI-OS project structure and report one harmless fact."

    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    # Try to load existing opportunity
    opp = queue.get_opportunity(task_id)
    if not opp:
        dedupe_hash = hashlib.sha256(task_id.encode()).hexdigest()[:16]
        opp = Opportunity(
    opportunity_id=task_id,
    source="ROUTER_DISPATCH",
    project="WINDOWS_AI_OS",
    description=description,
    objective_id="OBJ-FOUNDATION-1",
    priority=7,
    risk="SAFE",
    estimated_cost=0.0,
    heavy_job=False,
    status="READY",
    target_agent=None,  # Let router decide
    required_capabilities=["WINDOWS_EXECUTION"],
    allowed_scope=["C:\Dev\Windows-AI-OS"],
    allowed_actions=["READ"],
    dedupe_hash=dedupe_hash,
    )
        queue.add_opportunity(opp)
        print(f"[STEP 2] Opportunity injected: {task_id}")
    else:
        print(f"[STEP 2] Opportunity loaded: {task_id}")
        
    scope_str = opp.allowed_scope[0].strip().rstrip("/") if opp.allowed_scope else "C:\\Dev\\Windows-AI-OS"
    dedupe_hash = opp.dedupe_hash if opp.dedupe_hash else hashlib.sha256(task_id.encode()).hexdigest()[:16]

    # ── 3. Router selects worker + host ──
    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
    res = router.evaluate_next_safe_work()
    rec = res.get("recommendations", {}).get("CODEX")

    if not rec or not rec.get("recommended_action", "").startswith("DISPATCH_TASK_"):
        print(f"[FAIL] Router did not select CODEX. All recommendations: {json.dumps(res.get('recommendations', {}), indent=2)}")
        sys.exit(1)

    if rec.get("task_id") != task_id:
        print(f"[FAIL] Router selected wrong task: {rec.get('task_id')}")
        sys.exit(1)

    target_host = rec.get("target_host")
    print(f"[STEP 3] Router selected: CODEX → {target_host}")

    # ── 3b. Windows health check gate ──
    if target_host == "DESKTOP-JDPRUGR":
        print("[STEP 3b] Running Windows health check (route/TCP22/SSH/project) ...")
        healthy, health_report = check_windows_health(max_attempts=2, retry_delay_sec=5)
        if healthy:
            print(f"[STEP 3b] Windows link READY — route={health_report.get('NETWORK_ROUTE')}, "
                  f"TCP22={health_report.get('TCP22')}, SSH={health_report.get('SSH')}, "
                  f"project={health_report.get('REMOTE_PROJECT')}")
        else:
            failure_layer = health_report.get("FAILURE_LAYER", "UNKNOWN")
            print(f"[STEP 3b] Windows link UNHEALTHY — layer={failure_layer}")
            checkpoint_envelope = {
                "task_id": task_id,
                "target_host": target_host,
                "description": description,
                "dedupe_hash": dedupe_hash,
                "router_recommendation": rec,
            }
            checkpoint_task(task_id, checkpoint_envelope, health_report)
            print(f"[FAIL_CLOSED] Task {task_id} checkpointed. Windows link unhealthy.")
            sys.exit(2)

    # ── 4. Acquire authoritative scope lease via CanonicalAuthority ──
    authority = CanonicalAuthority()
    owner_id = "agent-codex-bridge"
    success, gen, err = authority.acquire_scopes(
        owner_id=owner_id,
        task_id=task_id,
        scopes=[scope_str],
        ttl_seconds=300,
    )
    if not success:
        print(f"[FAIL] CanonicalAuthority scope acquisition failed: {err}")
        checkpoint_envelope = {
            "task_id": task_id,
            "target_host": target_host,
            "description": description,
            "dedupe_hash": dedupe_hash,
            "router_recommendation": rec,
        }
        checkpoint_task(task_id, checkpoint_envelope, {"FAILURE_LAYER": "SCOPE_CONTENTION", "RESULT": "LEASE_DENIED"})
        
        # Mark as BLOCKED in the opportunity queue so router doesn't get stuck on it
        opp_file = COURIER_DIR / "events" / "opportunity-queue" / f"{task_id}.json"
        if opp_file.exists():
            opp_data = json.loads(opp_file.read_text())
            opp_data["status"] = "BLOCKED"
            opp_file.write_text(json.dumps(opp_data, indent=2))
            
        print(f"[FAIL_CLOSED] Task {task_id} checkpointed due to lease contention.")
        sys.exit(2)

    # Read back the authority record file to get its path and hash
    record_path = authority._scope_file_path(scope_str)
    record_data = json.loads(record_path.read_text(encoding="utf-8"))
    record_sha256 = _stable_hash(record_data)
    record_rel = str(record_path.relative_to(COURIER_DIR))

    print(f"[STEP 4] CanonicalAuthority scope lease acquired: gen={gen}, "
          f"owner={owner_id}, scope={scope_str}, record={record_rel}")

    # ── 5. Build validated envelope ──
    # 5a. Write source artifact receipt (binding provenance to envelope fields)
    receipt_body = {
        "task_id": task_id,
        "source_agent": "GOOGLE_ANTIGRAVITY",
        "target_agent": "CODEX",
        "target_host": target_host,
        "project_path": scope_str,
        "created_at": now_iso,
        "description": description,
    }
    receipt_hash = _stable_hash(receipt_body)
    receipt_body["artifact_sha256"] = receipt_hash
    receipts_dir = COURIER_DIR / "events" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{task_id}-receipt.json"
    receipt_path.write_text(json.dumps(receipt_body, indent=2) + "\n", encoding="utf-8")
    receipt_rel = str(receipt_path.relative_to(COURIER_DIR))

    provenance = {
        "origin": "GOOGLE_ANTIGRAVITY",
        "task_identity": task_id,
        "source_artifact": receipt_rel,
        "source_sha256": receipt_hash,
    }

    lease_block = {
        "authority": "CanonicalAuthority",
        "record_path": record_rel,
        "record_sha256": record_sha256,
        "task_id": task_id,
        "owner_id": owner_id,
        "scope": scope_str,
        "generation": gen,
        "lease_expires_at": record_data.get("lease_expires_at"),
    }

    task_envelope = {
        "task_id": task_id,
        "goal_id": "OBJ-FOUNDATION-1",
        "source_agent": "GOOGLE_ANTIGRAVITY",
        "target_agent": "CODEX",
        "target_host": target_host,
        "project_path": scope_str,
        "scope": opp.allowed_scope,
        "action": description,
        "acceptance_criteria": "Return a valid JSON result with preserved task identity.",
        "instruction": description,
        "status": "PENDING",
        "created_at": now_iso,
        "provenance": provenance,
        "lease": lease_block,
        "task_hash": dedupe_hash,
        "worker_id": "CODEX",
        "allowed_scope": opp.allowed_scope,
        "payload": {
            "prompt": description,
            "allowed_scope": opp.allowed_scope,
            "requires_write": False,
        },
    }
    print("[STEP 5] Envelope built with provenance receipt + authority lease binding")

    # ── 6. Drop to dispatch ──
    dispatch_dir = COURIER_DIR / "events" / "dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    out_path = dispatch_dir / f"{task_id}-worker-job.json"
    with open(out_path, "w") as f:
        json.dump(task_envelope, f, indent=2)
    print(f"[STEP 6] Dispatched to {out_path.name}")

    # ── 7. Invoke bridge ──
    print("[STEP 7] Invoking run_codex_bridge.py --auto-discover --real-codex ...")
    bridge_result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "run_codex_bridge.py"), "--auto-discover", "--real-codex"],
        capture_output=True, text=True, timeout=120,
    )
    print(bridge_result.stdout)
    if bridge_result.returncode != 0:
        print(f"[FAIL] Bridge exited with code {bridge_result.returncode}")
        if bridge_result.stderr:
            print(bridge_result.stderr)
        authority.release_scopes(owner_id=owner_id, task_id=task_id, scopes=[scope_str], generation=gen)
        # Check if rate limited from stderr
        if "rate limit" in str(bridge_result.stderr).lower():
            try:
                
                from pathlib import Path
                reg = LiveWorkerRegistry(Path('.'))
                w = reg.get_worker('CODEX')
                if w:
                    w.state = WorkerState.PROVIDER_ERROR.value
                    reg._save_worker_record(w)
            except: pass
            sys.exit(3)
        sys.exit(1)

    # ── 8. Read and verify result ──
    result_path = COURIER_DIR / "events" / "processed" / f"{task_id}-result.json"
    if not result_path.exists():
        print(f"[FAIL] Result file not found: {result_path}")
        sys.exit(1)

    result = json.loads(result_path.read_text())
    r_task_id = result.get("task_id")
    r_status = result.get("status")
    r_payload = result.get("payload", {})
    if r_payload.get("verdict") == "BLOCKED_RATE_LIMIT":
        print("[FAIL] Codex rate limited!")
        authority.release_scopes(owner_id=owner_id, task_id=task_id, scopes=[scope_str], generation=gen)
        print("[STEP 8] Released scope after rate limit.")
        
        # Mark Codex unavailable
        try:
            
            from pathlib import Path
            reg = LiveWorkerRegistry(Path('.'))
            w = reg.get_worker('CODEX')
            if w:
                w.state = WorkerState.PROVIDER_ERROR.value
                reg._save_worker_record(w)
                print("Marked CODEX unavailable (PROVIDER_ERROR).")
        except Exception as e:
            print(f"Failed to mark CODEX unavailable: {e}")
            
        sys.exit(3)
    r_provenance = result.get("provenance", {})
    r_prov_origin = r_provenance.get("origin")
    r_prov_task_id = r_provenance.get("task_identity")

    print()
    print("=" * 60)
    print("RESULT VERIFICATION")
    print("=" * 60)
    print(f"TASK_ID_MATCH={'YES' if r_task_id == task_id else 'NO'}")
    print(f"STATUS={r_status}")
    print(f"PROVENANCE_ORIGIN={r_prov_origin}")
    print(f"PROVENANCE_TASK_IDENTITY_MATCH={'YES' if r_prov_task_id == task_id else 'NO'}")
    print(f"HUMAN_TRANSPORT_REQUIRED=NO")

    if r_task_id == task_id and r_status == "COMPLETED" and r_prov_origin and r_prov_task_id == task_id:
        print("FINAL_STATUS=PASS")
        opp_file = COURIER_DIR / "events" / "opportunity-queue" / f"{task_id}.json"
        if opp_file.exists():
            opp_data = json.loads(opp_file.read_text())
            opp_data["status"] = "COMPLETED"
            opp_file.write_text(json.dumps(opp_data, indent=2))
    else:
        print("FINAL_STATUS=BLOCKED")
        sys.exit(1)

    # Release scope
    authority.release_scopes(owner_id=owner_id, task_id=task_id, scopes=[scope_str], generation=gen)


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else None
    desc = sys.argv[2] if len(sys.argv) > 2 else None
    main(task_id=tid, description=desc)
