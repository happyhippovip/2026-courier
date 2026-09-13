"""
SELF_TEST.py - Autonomous Standalone Self-Test for Courier Symphony V1.0.0-RC1
Can be executed in any clean-room environment with standard Python >= 3.10.
Zero external dependencies, zero pre-configured database required.
"""

import os
import sys
import json
import sqlite3
import tempfile
import hashlib
from datetime import datetime, timezone

# Ensure parent directory is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)


def test_step(name: str):
    print(f"[*] [SELF-TEST] Running: {name} ...", end=" ", flush=True)


def pass_step():
    print("PASS")


def main():
    print("=================================================================")
    print("  COURIER SYMPHONY WINDOWS V1.0.0-RC1 — AUTONOMOUS SELF-TEST")
    print("=================================================================")

    # 1. Version & Metadata
    test_step("1. Version Introspection & Parity")
    from courier.chief.version import (
        __version__, PRODUCT_NAME, RELEASE_TAG, SCHEMA_VERSION, get_version_info
    )
    assert __version__ == "1.0.0-rc1", f"Unexpected version: {__version__}"
    assert RELEASE_TAG == "v1.0.0-rc1"
    vinfo = get_version_info()
    assert vinfo["version"] == "1.0.0-rc1"
    assert vinfo["schema_version"] == 1
    pass_step()

    # 2. Constitution Discovery & Verification
    test_step("2. Operating Constitution Verification")
    from courier.chief.constitution import ConstitutionLoader
    c_ok, c_data, c_path, c_hash = ConstitutionLoader.discover_and_load()
    assert c_ok, f"Constitution could not be discovered/loaded. Searched paths: {c_path}"
    assert c_data.get("status") == "ACTIVE", f"Constitution status not ACTIVE: {c_data.get('status')}"
    articles = c_data.get("articles", {})
    assert len(articles) >= 30, f"Expected >= 30 articles, found {len(articles)}"
    pass_step()

    # 3. Health Engine in Isolated Clean Room
    test_step("3. Health Diagnostic Engine")
    with tempfile.TemporaryDirectory() as td:
        from courier.chief.health import run_health_check
        test_db = os.path.join(td, "test_health.db")
        report = run_health_check(db_path=test_db)
        assert report["healthy"], f"Health check failed: {report}"
        assert report["status"] == "HEALTHY"
        assert report["checks"]["constitution"]["valid"]
        assert report["checks"]["runtime"]["writable"]
        assert report["checks"]["schema"]["compatible"]
    pass_step()

    # 4. Fenced Mutex Isolation
    test_step("4. Fenced Mutex Acquisition & Safety")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        from courier.chief.fenced_mutex import FencedMutexManager
        db_path = os.path.join(td, "mutex_test.db")
        fmm = FencedMutexManager(db_path=db_path)
        lease = fmm.acquire(resource_id="RES-TEST-1", holder_id="WINDOWS_CLI_1", holder_host="WINDOWS", ttl_seconds=60)
        assert lease.get("acquired"), f"Failed to acquire mutex: {lease}"
        token = lease["lease_token"]
        # Verify mutual exclusion
        lease2 = fmm.acquire(resource_id="RES-TEST-1", holder_id="CODEX", holder_host="WINDOWS", ttl_seconds=60)
        assert not lease2.get("acquired"), "Mutual exclusion violated! Second acquisition succeeded."
        # Release lock
        rel = fmm.release(resource_id="RES-TEST-1", holder_id="WINDOWS_CLI_1", lease_token=token)
        assert rel.get("released"), f"Failed to release mutex: {rel}"
        del fmm
        import gc; gc.collect()
    pass_step()

    # 5. Zero-Copy Ingestion & Delta Engine Lifecycle
    test_step("5. End-to-End Control Plane Ingest & Delta Cycle")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        from courier.chief.control_plane import ControlPlane
        from courier.chief.ingestor import ChiefIngestor
        from courier.chief.delta_engine import ChiefDeltaEngine
        from courier.chief.types import Lane, Host, TaskStatus, FindingStatus, FindingSeverity
        
        db_path = os.path.join(td, "e2e_chief.db")
        handoffs_dir = os.path.join(td, "handoffs")
        os.makedirs(handoffs_dir, exist_ok=True)
        
        cp = ControlPlane(db_path=db_path)
        ingestor = ChiefIngestor(cp=cp, handoffs_dir=handoffs_dir)
        
        # Write sample handoff envelope with complete required fields
        envelope = {
            "version": "1.0.0",
            "handoff_id": "HANDOFF-TEST-001",
            "assignment_id": "REQ-V1-SELFTEST",
            "origin": "WINDOWS_CLI_1",
            "role": "WINDOWS_TESTER",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "host_os": "WINDOWS",
            "mac_host_access": False,
            "production_write_authority": False,
            "two_level_done": {
                "company_local_step_erledigt": True,
                "company_gesamtaufgabe_erledigt": False,
                "active_blockers": []
            },
            "confirmed_findings": ["FIND-TEST-1"],
            "patch_batches": []
        }
        handoff_path = os.path.join(handoffs_dir, "handoff_001.json")
        with open(handoff_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
            
        ing_res = ingestor.scan_and_ingest(handoffs_dir)
        assert ing_res["ingested_count"] == 1, f"Ingest count mismatch: {ing_res}"
        
        delta_engine = ChiefDeltaEngine(control_plane=cp)
        delta = delta_engine.compute_delta()
        assert delta["summary"]["confirmed_count"] == 1
        assert delta["summary"]["total_findings"] == 1
        assert delta["two_level_done"]["company_local_step_erledigt"]
        del cp, ingestor, delta_engine
        import gc; gc.collect()
    pass_step()

    # 6. CLI Parser & Command Verification
    test_step("6. CLI Subcommand Registration")
    from courier.chief.cli import build_parser
    parser = build_parser()
    ver_args = parser.parse_args(["version"])
    assert ver_args.command == "version"
    health_args = parser.parse_args(["health"])
    assert health_args.command == "health"
    pass_step()

    print("=================================================================")
    print("  RESULT: ALL 6/6 CORE SUBSYSTEM VERIFICATIONS PASSED")
    print("  STATUS: V1_SELF_TEST_SUCCESSFUL")
    print("=================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
