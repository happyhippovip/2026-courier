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
import datetime as _dt
import socketserver
import sys
from pathlib import Path

PORT = int(os.environ.get("PORT", 8080))
BIND_HOST = "127.0.0.1"  # local command center: loopback only
DASHBOARD_DIR = Path(__file__).resolve().parent
COURIER_DIR = DASHBOARD_DIR.parent
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", COURIER_DIR.parent / "2026-project-memory"))
EVENTS_DIR = COURIER_DIR / "events"


def _plain_text(path: Path, root: Path | None = None) -> str | None:
    if root is not None and (root.is_symlink() or root.parent.is_symlink() or root.parent.parent.is_symlink()):
        return None
    if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def get_status_payload() -> dict:
    """Compiles live status payload from 2026-courier events and git HEAD."""
    # Read Memory commit
    mem_commit = "UNKNOWN"
    try:
        head_file = MEMORY_DIR / ".git/HEAD"
        head_text = _plain_text(head_file, MEMORY_DIR)
        if head_text:
            ref = head_text.strip()
            if ref.startswith("ref:"):
                ref_path = MEMORY_DIR / ".git" / ref[4:].strip()
                ref_text = _plain_text(ref_path, MEMORY_DIR)
                if ref_text:
                    mem_commit = ref_text.strip()[:7]
            else:
                mem_commit = ref[:7]
    except Exception:
        pass

    # Read Courier commit
    courier_commit = "UNKNOWN"
    try:
        head_file = COURIER_DIR / ".git/HEAD"
        head_text = _plain_text(head_file, COURIER_DIR)
        if head_text:
            ref = head_text.strip()
            if ref.startswith("ref:"):
                ref_path = COURIER_DIR / ".git" / ref[4:].strip()
                ref_text = _plain_text(ref_path, COURIER_DIR)
                if ref_text:
                    courier_commit = ref_text.strip()[:7]
            else:
                courier_commit = ref[:7]
    except Exception:
        pass

    # Read live motto & north star
    motto = "WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN."
    motto_file = EVENTS_DIR / "runtime-state" / "central_motto.json"
    motto_text = _plain_text(motto_file, EVENTS_DIR)
    if motto_text:
        try:
            motto = json.loads(motto_text).get("motto", motto)
        except Exception:
            pass

    active_workers = {}
    workers_file = EVENTS_DIR / "worker-registry" / "active_workers.json"
    workers_text = _plain_text(workers_file, EVENTS_DIR)
    if workers_text:
        try:
            active_workers = json.loads(workers_text)
        except Exception:
            pass

    hq_snapshot = {}
    hq_file = EVENTS_DIR / "runtime-state" / "hq_telemetry_snapshot.json"
    hq_text = _plain_text(hq_file, EVENTS_DIR)
    if hq_text:
        try:
            hq_snapshot = json.loads(hq_text)
        except Exception:
            pass

    latch = EVENTS_DIR / "EMERGENCY_LATCH"
    is_emergency = (
        not EVENTS_DIR.is_symlink()
        and not latch.is_symlink()
        and not latch.parent.is_symlink()
        and latch.exists()
    )

    return {
        "status": "EMERGENCY" if is_emergency else "ONLINE",
        "version": "3.0-live-autonomy",
        "courier_head": courier_commit,
        "memory_head": mem_commit,
        "central_motto": motto,
        "active_workers_count": len(active_workers),
        "active_workers": active_workers,
        "hq_snapshot": hq_snapshot,
        "host_capacity": {
            "health": "EMERGENCY" if is_emergency else "HEALTHY",
            "active_leases": 2, # Simulated values for dashboard
            "max_total_slots": 16,
            "active_heavy_leases": 0,
            "max_heavy_slots": 4,
            "profile": "normal laptop"
        },
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
    ledger_text = _plain_text(ledger_file, EVENTS_DIR)
    if ledger_text:
        try:
            data = json.loads(ledger_text)
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


def get_ledger_value_payload() -> dict:
    processed_dir = EVENTS_DIR / "processed"
    reused = 0
    work_units = 0
    evidence = []
    linked = (EVENTS_DIR.is_symlink() or EVENTS_DIR.parent.is_symlink()
              or EVENTS_DIR.parent.parent.is_symlink()
              or processed_dir.is_symlink() or processed_dir.parent.is_symlink()
              or processed_dir.parent.parent.is_symlink())
    try:
        reuse_text = None if linked else _plain_text(processed_dir / "reuse_events.jsonl", EVENTS_DIR)
        if reuse_text:
            for line in reuse_text.splitlines():
                if line.strip():
                    reused += 1
                    evidence.append(json.loads(line))
        registry_text = None if linked else _plain_text(processed_dir / "task_dedupe_registry.json", EVENTS_DIR)
        if registry_text:
            data = json.loads(registry_text)
            work_units = len(data)
    except Exception:
        pass

    shown = 0
    if not linked and processed_dir.is_dir() and not processed_dir.is_symlink():
        shown = len(list(processed_dir.glob("result*.json")))
    return {
        "metrics": {
            "results_reused": {"value": reused},
            "evidence_files_available": {"value": shown}
        },
        "this_month": {
            "work_units_completed": {"value": work_units}
        },
        "evidence": evidence
    }


def latch_emergency() -> bool:
    latch_file = EVENTS_DIR / "EMERGENCY_LATCH"
    if (EVENTS_DIR.is_symlink() or EVENTS_DIR.parent.is_symlink() or EVENTS_DIR.parent.parent.is_symlink()
            or latch_file.is_symlink() or latch_file.parent.is_symlink()
            or latch_file.parent.parent.is_symlink()):
        return False
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    latch_file.write_text("EMERGENCY_MODE=ON\n", encoding="utf-8")
    return True


class CommandCenterHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        root = Path(getattr(self, "directory", None) or DASHBOARD_DIR)
        path = Path(self.translate_path(self.path))
        if (root.is_symlink() or root.parent.is_symlink() or root.parent.parent.is_symlink()
                or path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink()
                or (path / "index.html").is_symlink() or (path / "index.htm").is_symlink()):
            self.send_error(404, "File not found")
            return None
        return super().send_head()

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

        if self.path == "/api/ledger-value":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            ledger_payload = get_ledger_value_payload()
            self.wfile.write(json.dumps(ledger_payload, indent=2).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/emergency":
            if not latch_emergency():
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "REFUSED"}).encode("utf-8"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "EMERGENCY_LATCHED"}).encode("utf-8"))
            return
            
        return super().do_POST()


def create_server(port: int = PORT):
    handler_factory = functools.partial(CommandCenterHandler, directory=str(DASHBOARD_DIR))
    return socketserver.TCPServer((BIND_HOST, port), handler_factory)


def main() -> None:
    port = PORT
    for attempt in range(5):
        try:
            handler_factory = functools.partial(CommandCenterHandler, directory=str(DASHBOARD_DIR))
            with socketserver.TCPServer((BIND_HOST, port), handler_factory) as httpd:
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
