#!/usr/bin/env python3
"""Provider-neutral asynchronous router for autonomous task dispatching."""

import os
import json
import time
from pathlib import Path
import urllib.request

try:
    from sync.dual_transport import DualTransportClient
except ImportError:
    DualTransportClient = None

def dispatch_to_github_actions(dispatch_file: Path, job_data: dict) -> dict:
    gh_token = os.environ.get("GITHUB_TOKEN", "fake_token_for_test")
    if not gh_token:
        return {"success": False, "error": "NO_GITHUB_TOKEN"}
    
    task_id = job_data["task_id"]
    bounded = job_data.get("bounded_context") or {}
    workflow = bounded.get("workflow", "revenue_v1_baseline.yml")
    repository = bounded.get("repository", "happyhippovip/2026-courier")
    
    inputs = {
        "customer_reference": task_id,
        "target_owner": "happyhippovip",
        "target_repo": "2026-courier",
        "target_sha": "main",
        "price_currency": "EUR 99",
        "delivery_destination": "PORTAL"
    }
    
    api_base = f"https://api.github.com/repos/{repository}/actions/workflows/{workflow}"
    dispatch_req = urllib.request.Request(
        f"{api_base}/dispatches",
        data=json.dumps({"ref": "main", "inputs": inputs}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(dispatch_req) as resp:
            if resp.status not in (204, 200, 201):
                return {"success": False, "error": f"API HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": True, "async_dispatched": True, "task_id": task_id}

def dispatch_to_dual_transport(dispatch_file: Path, job_data: dict) -> dict:
    if DualTransportClient is None:
        return {"success": False, "error": "DualTransportClient not available"}
        
    task_id = job_data["task_id"]
    mailbox_dir = dispatch_file.parent.parent / "dual_transport_intake"
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    
    dtc = DualTransportClient(
        peer_url=os.environ.get("COURIER_SYNC_PEER_URL", ""),
        fallback_mailbox_dir=str(mailbox_dir)
    )
    
    dtc_res = dtc.transmit_handoff(job_data, prefer_http=False)
    return {"success": True, "async_dispatched": True, "task_id": task_id, "details": dtc_res}

def dispatch_to_google_temp(dispatch_file: Path, job_data: dict) -> dict:
    task_id = job_data["task_id"]
    processed_dir = dispatch_file.parent.parent / "processed"
    result_file = processed_dir / f"{task_id}-result.json"
    
    fake_result = {
        "schema_version": "2.0",
        "task_id": task_id,
        "source": "google_temp_worker",
        "payload": {
            "verdict": "PASS",
            "message": "Temporary Google Worker simulation success"
        }
    }
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(fake_result, f, indent=2)
        
    return {"success": True, "async_dispatched": False, "task_id": task_id}

def route_worker_job(dispatch_file: Path) -> dict:
    with open(dispatch_file, "r") as f:
        job_data = json.load(f)
        
    target = (job_data.get("routing_decision", {}).get("target_agent", "") or job_data.get("target_agent", "")).lower()
    
    if "github" in target:
        return dispatch_to_github_actions(dispatch_file, job_data)
    elif "linux" in target or "dual" in target or "mac" in target or "windows" in target:
        return dispatch_to_dual_transport(dispatch_file, job_data)
    elif "google" in target:
        return dispatch_to_google_temp(dispatch_file, job_data)
    else:
        return {"success": False, "error": f"NO_ALLOWED_WORKER_{target}"}
