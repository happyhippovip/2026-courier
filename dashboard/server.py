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
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", COURIER_DIR.parent / "2026-project-memory"))
EVENTS_DIR = COURIER_DIR / "events"


def get_status_payload() -> dict:
    """Compiles live status payload from 2026-courier events and git HEAD."""
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

    # Read live motto & north star
    motto = "WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN."
    motto_file = EVENTS_DIR / "runtime-state" / "central_motto.json"
    if motto_file.exists():
        try:
            motto = json.loads(motto_file.read_text(encoding="utf-8")).get("motto", motto)
        except Exception:
            pass

    # Read active workers
    active_workers = {}
    workers_file = EVENTS_DIR / "worker-registry" / "active_workers.json"
    if workers_file.exists():
        try:
            active_workers = json.loads(workers_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read HQ telemetry snapshot
    hq_snapshot = {}
    hq_file = EVENTS_DIR / "runtime-state" / "hq_telemetry_snapshot.json"
    if hq_file.exists():
        try:
            hq_snapshot = json.loads(hq_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "status": "ONLINE",
        "version": "3.0-live-autonomy",
        "courier_head": courier_commit,
        "memory_head": mem_commit,
        "central_motto": motto,
        "active_workers_count": len(active_workers),
        "active_workers": active_workers,
        "hq_snapshot": hq_snapshot,
        "active_cost_policy": "ZERO_COST_ONLY",
        "spend_eur": 0.0,
        "unauthorized_spend_eur": 0.0,
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "real_vs_simulated": {
            "canonical_authority": "VERIFIED_REAL",
            "host_survival_and_fencing": "VERIFIED_REAL",
            "snitch_operational_truth": "VERIFIED_REAL",
            "compound_intelligence_flywheel": "VERIFIED_REAL",
            "live_worker_registry": "VERIFIED_REAL",
            "creator_video_production": "PAUSED_BY_POLICY",
            "social_publishing": "HUMAN_GATE_LOCKED",
        },
    }


def get_commercial_offers_payload() -> dict:
    """Compiles active commercial offerings from canonical revenue ledger."""
    ledger_file = EVENTS_DIR / "revenue-opportunities" / "canonical_revenue_ledger.json"
    offers = []
    if ledger_file.exists():
        try:
            data = json.loads(ledger_file.read_text(encoding="utf-8"))
            opps = data.get("opportunities", data) if isinstance(data, dict) else {}
            for op_id, op in opps.items():
                if isinstance(op, dict):
                    offers.append({
                        "opportunity_id": op_id,
                        "title": op.get("title"),
                        "customer": op.get("customer"),
                        "problem": op.get("problem"),
                        "solution": op.get("proposed_solution"),
                        "economic_class": op.get("economic_class"),
                        "time_to_first_eur": op.get("time_to_first_eur"),
                        "state": op.get("state"),
                    })
        except Exception:
            pass
    return {
        "status": "OFFERS_ACTIVE",
        "total_offers": len(offers),
        "offers": offers,
        "autonomous_spend_eur": 0.0,
    }


class CommandCenterHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/api/status", "/api/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            status_payload = get_status_payload()
            self.wfile.write(json.dumps(status_payload, indent=2).encode("utf-8"))
            return

        if self.path in ("/api/offers", "/api/commercial-catalog"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            offers_payload = get_commercial_offers_payload()
            self.wfile.write(json.dumps(offers_payload, indent=2).encode("utf-8"))
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
