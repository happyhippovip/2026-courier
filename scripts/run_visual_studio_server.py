#!/usr/bin/env python3
"""Visual Multi-Agent Operations Studio Server for 2026 Courier.

Serves the Studio Web UI and provides real-time state aggregation over the Courier Event Bus:
- /api/state: Aggregates agent visual states, event bus queues, and active locks.
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

# Add scripts directory to path for imports
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_autonomous_loop import AutonomousLevel6Loop
except ImportError:
    AutonomousLevel6Loop = None


def load_json_safe(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
        if self.path == "/api/trigger-workflow":
            self.handle_trigger_workflow()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_api_state(self):
        agents_data = {}
        states_dir = EVENTS_DIR / "agent-states"
        if states_dir.exists():
            for state_file in states_dir.glob("*.json"):
                data = load_json_safe(state_file)
                if data and "id" in data:
                    agents_data[data["id"]] = data

        dispatch_dir = EVENTS_DIR / "dispatch"
        processed_dir = EVENTS_DIR / "processed"
        decisions_dir = EVENTS_DIR / "chief-decisions"
        locks_dir = EVENTS_DIR / "locks"

        counts = {
            "dispatch": len(list(dispatch_dir.glob("*.json"))) if dispatch_dir.exists() else 0,
            "processed": len(list(processed_dir.glob("*.json"))) if processed_dir.exists() else 0,
            "decisions": len(list(decisions_dir.glob("*.json"))) if decisions_dir.exists() else 0,
        }

        active_locks = list(locks_dir.glob("*.lock")) if locks_dir.exists() else []
        is_locked = len(active_locks) > 0
        active_lock_name = active_locks[0].stem if is_locked else None

        last_decision = None
        if decisions_dir.exists():
            dec_files = sorted(decisions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if dec_files:
                last_dec_data = load_json_safe(dec_files[0])
                last_decision = last_dec_data.get("verdict", "ACCEPTED")

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
                "correlation_id": f"corr-live-{uuid.uuid4().hex[:6]}",
            }
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode("utf-8"))

    def handle_trigger_workflow(self):
        def run_async():
            if AutonomousLevel6Loop:
                engine = AutonomousLevel6Loop(repo_dir=COURIER_DIR, max_iterations=3)
                wf_id = f"WF-STUDIO-DEMO-{uuid.uuid4().hex[:4]}"
                plan = [
                    {
                        "task_id": f"{wf_id}-STEP-1-CODEX",
                        "target_agent": "codex",
                        "instruction": "Round 1: Codex checks configuration and schema validity.",
                        "allowed_scope": ["config/local_tools.json"],
                    },
                    {
                        "task_id": f"{wf_id}-STEP-2-ANTIGRAVITY",
                        "target_agent": "antigravity",
                        "instruction": "Round 2: Antigravity reviews media channels and render pipelines.",
                        "allowed_scope": ["config/social_channels.json"],
                    },
                    {
                        "task_id": f"{wf_id}-STEP-3-CODEX",
                        "target_agent": "codex",
                        "instruction": "Round 3: Codex verifies final policy adherence.",
                        "allowed_scope": ["config/teamwork_policy.json"],
                    },
                ]
                engine.run_multi_round_workflow(wf_id, plan)

        threading.Thread(target=run_async, daemon=True).start()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "TRIGGERED", "message": "Demo workflow started in background"}).encode("utf-8"))


def run_server(port: int = 8088):
    server_address = ("", port)
    # Enable address reuse to prevent port binding conflicts
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, StudioHTTPRequestHandler) as httpd:
        print(f"=== VISUAL MULTI-AGENT OPERATIONS STUDIO RUNNING ===")
        print(f"Serving at: http://localhost:{port}")
        print(f"Studio Root: {STUDIO_DIR}")
        print(f"Courier Bus: {EVENTS_DIR}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Operations Studio server.")


def main():
    parser = argparse.ArgumentParser(description="Run Visual Multi-Agent Operations Studio Server")
    parser.add_argument("--port", type=int, default=8088, help="Port to serve UI (default: 8088)")
    args = parser.parse_args()
    run_server(args.port)


if __name__ == "__main__":
    main()
