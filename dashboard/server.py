#!/usr/bin/env python3
"""Lightweight zero-dependency HTTP server for the AI Agent Command Center MVP (092).

Serves the dashboard UI and provides a read-only /api/status endpoint
reflecting the canonical repository state from 2026-project-memory and 2026-courier.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import socketserver
import sys
from pathlib import Path

PORT = int(os.environ.get("PORT", 8080))
DASHBOARD_DIR = Path(__file__).resolve().parent
COURIER_DIR = DASHBOARD_DIR.parent
MEMORY_DIR = Path("/Users/user/Downloads/2026-project-memory")


class CommandCenterHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/api/status", "/api/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Read Memory commit
            mem_commit = "UNKNOWN"
            try:
                head_file = MEMORY_DIR / ".git/HEAD"
                if head_file.exists():
                    ref = head_file.read_text().strip()
                    if ref.startswith("ref:"):
                        ref_path = MEMORY_DIR / ".git" / ref[4:].strip()
                        if ref_path.exists():
                            mem_commit = ref_path.read_text().strip()[:7]
                    else:
                        mem_commit = ref[:7]
            except Exception:
                pass

            # Read Courier commit
            courier_commit = "UNKNOWN"
            try:
                head_file = COURIER_DIR / ".git/HEAD"
                if head_file.exists():
                    ref = head_file.read_text().strip()
                    if ref.startswith("ref:"):
                        ref_path = COURIER_DIR / ".git" / ref[4:].strip()
                        if ref_path.exists():
                            courier_commit = ref_path.read_text().strip()[:7]
                    else:
                        courier_commit = ref[:7]
            except Exception:
                pass

            status_payload = {
                "status": "ONLINE",
                "version": "1.0-mvp092",
                "courier_head": courier_commit,
                "memory_head": mem_commit,
                "roles_count": 17,
                "active_cost_policy": "ZERO_COST_ONLY",
                "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
                "real_vs_simulated": {
                    "courier_relay_protocol": "VERIFIED_REAL",
                    "autonomous_088_policy": "VERIFIED_REAL",
                    "087_memory_write_handler": "VERIFIED_REAL",
                    "video_rendering_pipeline": "DEMO_SIMULATED",
                    "social_publishing": "HUMAN_GATE_LOCKED"
                }
            }
            self.wfile.write(json.dumps(status_payload, indent=2).encode("utf-8"))
            return

        return super().do_GET()


def create_server(port: int = PORT):
    handler_factory = functools.partial(CommandCenterHandler, directory=str(DASHBOARD_DIR))
    return socketserver.TCPServer(("", port), handler_factory)


def main() -> None:
    port = PORT
    for attempt in range(5):
        try:
            handler_factory = functools.partial(CommandCenterHandler, directory=str(DASHBOARD_DIR))
            with socketserver.TCPServer(("", port), handler_factory) as httpd:
                print(f"AI Agent Command Center MVP running at: http://localhost:{port}")
                print("Press Ctrl+C to stop.")
                httpd.serve_forever()
                break
        except OSError as e:
            if "Address already in use" in str(e):
                port += 1
            else:
                raise


if __name__ == "__main__":
    main()
