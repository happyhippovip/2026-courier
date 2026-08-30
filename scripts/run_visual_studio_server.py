#!/usr/bin/env python3
"""Autonomous Chief Operations Cockpit Server for 2026 Courier.

Serves the Studio Web UI and provides real-time state aggregation over the Courier Event Bus:
- /api/state: Aggregates Chief, Antigravity, and Codex visual states, queues, and locks.
- /api/submit-idea: Ingests human ideas/goals and routes them through the Chief Commander.
- /api/human-gate: Persists explicit human approval or rejection events to resume/stop workflows.
- /api/trigger-workflow: Triggers a demonstration multi-round autonomous loop.
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import os
import socketserver
import sys
import threading
import time
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
STUDIO_DIR = COURIER_DIR / "studio"
EVENTS_DIR = COURIER_DIR / "events"

APPROVALS_DIR = EVENTS_DIR / "approvals"
APPROVALS_DIR.mkdir(parents=True, exist_ok=True)

# Add scripts directory to path for imports
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_chief_commander import ChiefCommander
except ImportError:
    from scripts.run_chief_commander import ChiefCommander


def load_json_safe(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json_safe(path: Path, data: dict) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        print(f"[SERVER] Error saving {path}: {e}")


class StudioHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STUDIO_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/state":
            self.handle_api_state()
        elif self.path == "/" or self.path == "/index.html":
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/submit-idea":
            self.handle_submit_idea()
        elif self.path == "/api/human-gate":
            self.handle_human_gate()
        elif self.path == "/api/trigger-workflow":
            self.handle_trigger_workflow()
        elif self.path == "/api/trigger-demo":
            self.handle_trigger_demo()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_api_state(self):
        agents_data = {}
        states_dir = EVENTS_DIR / "agent-states"
        if states_dir.exists():
            for state_file in states_dir.glob("*.json"):
                data = load_json_safe(state_file)
                if data and "id" in data:
                    # Ground execution_class strictly in evidence
                    if "execution_class" not in data:
                        data["execution_class"] = data.get("result_execution_class", "UNKNOWN")
                    agents_data[data["id"]] = data

        dispatch_dir = EVENTS_DIR / "dispatch"
        processed_dir = EVENTS_DIR / "processed"
        decisions_dir = EVENTS_DIR / "chief-decisions"
        locks_dir = EVENTS_DIR / "locks"
        approvals_dir = EVENTS_DIR / "approvals"

        counts = {
            "dispatch": len(list(dispatch_dir.glob("*.json"))) if dispatch_dir.exists() else 0,
            "processed": len(list(processed_dir.glob("*.json"))) if processed_dir.exists() else 0,
            "decisions": len(list(decisions_dir.glob("*.json"))) if decisions_dir.exists() else 0,
            "approvals": len(list(approvals_dir.glob("*.json"))) if approvals_dir.exists() else 0,
        }

        active_locks = list(locks_dir.glob("*.lock")) if locks_dir.exists() else []
        is_locked = len(active_locks) > 0
        active_lock_name = active_locks[0].stem if is_locked else None

        # Derive Last Decision Truth
        last_decision = "NO_DECISION"
        if decisions_dir.exists():
            dec_files = sorted(decisions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if dec_files:
                last_dec_data = load_json_safe(dec_files[0])
                last_decision = last_dec_data.get("verdict", "NO_DECISION")

        # Derive Correlation ID Truth (No Synthetic Random Generation, No Workflow Name Derivations)
        derived_correlation_id = "UNKNOWN"
        if is_locked and active_lock_name:
            lock_data = load_json_safe(active_locks[0])
            derived_correlation_id = lock_data.get("correlation_id", "UNKNOWN")
        else:
            recent_files = []
            if dispatch_dir.exists():
                recent_files.extend(dispatch_dir.glob("*.json"))
            if processed_dir.exists():
                recent_files.extend(processed_dir.glob("*.json"))
            if recent_files:
                sorted_events = sorted(recent_files, key=lambda p: p.stat().st_mtime, reverse=True)
                latest_evt = load_json_safe(sorted_events[0])
                derived_correlation_id = latest_evt.get("correlation_id", "UNKNOWN")

        # Check if Human Gate is pending
        human_gate_active = False
        for agent in agents_data.values():
            if agent.get("blocked") or agent.get("human_gate") or agent.get("state") in ["BLOCKED_HUMAN_GATE", "BLOCKED_POLICY_CONFLICT", "CONFLICT"]:
                human_gate_active = True
                break

        response_data = {
            "schema_version": "2.0",
            "server_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "agents": agents_data,
            "counts": counts,
            "bus": {
                "is_locked": is_locked,
                "active_lock": active_lock_name,
                "last_decision": last_decision,
                "active_workflow": active_lock_name or "IDLE_MONITORING",
                "correlation_id": derived_correlation_id,
                "human_gate": human_gate_active,
            }
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode("utf-8"))

    def handle_submit_idea(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8")
        try:
            req_data = json.loads(post_body)
            idea = req_data.get("idea", "").strip()
            idea_type = req_data.get("type", "IDEA")

            if not idea:
                self.send_error(400, "Empty idea provided")
                return

            def run_async_chief():
                chief = ChiefCommander(repo_dir=COURIER_DIR)
                chief.execute_human_idea(idea, idea_type)

            threading.Thread(target=run_async_chief, daemon=True).start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "INGESTED",
                "message": f"Human {idea_type} received by Chief Commander and workflow dispatched.",
                "idea": idea,
            }).encode("utf-8"))

        except Exception as exc:
            self.send_error(500, f"Failed to ingest idea: {exc}")

    def handle_human_gate(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8")
        try:
            req_data = json.loads(post_body)
            action = req_data.get("action", "").upper()  # "APPROVE" or "REJECT"
            workflow_id = req_data.get("workflow_id", "WF-GLOBAL")
            task_id = req_data.get("task_id", "TASK-GLOBAL")
            correlation_id = req_data.get("correlation_id", "corr-human-gate")
            reason = req_data.get("reason", "Operator decision from Visual Studio Cockpit")

            if action not in ["APPROVE", "REJECT"]:
                self.send_error(400, "Invalid action. Must be APPROVE or REJECT.")
                return

            approval_id = f"appr-{uuid.uuid4().hex[:8]}"
            approval_record = {
                "schema_version": "2.0",
                "approval_id": approval_id,
                "action": action,
                "decision": action,
                "workflow_id": workflow_id,
                "task_id": task_id,
                "correlation_id": correlation_id,
                "operator": "HUMAN_OPERATOR",
                "reason": reason,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

            approval_file = APPROVALS_DIR / f"{approval_id}.json"
            save_json_safe(approval_file, approval_record)
            print(f"\n[SERVER] Human Gate Event Persisted: {action} for {workflow_id} ({approval_id})")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "PERSISTED",
                "approval_id": approval_id,
                "action": action,
                "workflow_id": workflow_id,
            }).encode("utf-8"))

        except Exception as exc:
            self.send_error(500, f"Failed to persist human gate action: {exc}")

    def handle_trigger_workflow(self):
        def run_async():
            chief = ChiefCommander(repo_dir=COURIER_DIR)
            chief.execute_human_idea("Demo-Lauf: Optimiere Video-Pipeline und prüfe Channel-Konfigurationen", "GOAL")

        threading.Thread(target=run_async, daemon=True).start()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "TRIGGERED", "message": "Demo workflow started in background"}).encode("utf-8"))

    def handle_trigger_demo(self):
        def run_async_demo():
            from run_demo_workflow import DemoOrchestrator
            orchestrator = DemoOrchestrator(repo_dir=COURIER_DIR)
            orchestrator.reset_demo_environment()
            orchestrator.run_live_demo()

        threading.Thread(target=run_async_demo, daemon=True).start()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "TRIGGERED", "message": "Deterministic live demo workflow started in background"}).encode("utf-8"))


def run_server(port: int = 8088):
    server_address = ("", port)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, StudioHTTPRequestHandler) as httpd:
        print(f"=== AUTONOMOUS CHIEF OPERATIONS COCKPIT RUNNING ===")
        print(f"Serving at: http://localhost:{port}")
        print(f"Studio Root: {STUDIO_DIR}")
        print(f"Courier Bus: {EVENTS_DIR}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Operations Studio server.")


def main():
    parser = argparse.ArgumentParser(description="Run Autonomous Chief Operations Cockpit Server")
    parser.add_argument("--port", type=int, default=8088, help="Port to serve UI (default: 8088)")
    args = parser.parse_args()
    run_server(args.port)


if __name__ == "__main__":
    main()
