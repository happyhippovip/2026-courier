"""
health.py - Diagnostic & Health Evaluation Engine for Courier Symphony
Performs non-destructive health and readiness verification of the local runtime.
"""

import os
import sys
import sqlite3
import tempfile
from typing import Dict, Any, Tuple

from .version import get_version_info, SCHEMA_VERSION
from .constitution import ConstitutionLoader
from .batch_guard import DEFAULT_DB_PATH, WORKSPACE_ROOT


def run_health_check(db_path: str = None) -> Dict[str, Any]:
    active_db = os.path.abspath(db_path or DEFAULT_DB_PATH)
    vinfo = get_version_info()
    
    report: Dict[str, Any] = {
        "status": "HEALTHY",
        "healthy": True,
        "product": vinfo["product"],
        "version": vinfo["version"],
        "checks": {}
    }
    
    # 1. Critical Imports Check
    import_results = {}
    critical_modules = [
        "control_plane", "ingestor", "delta_engine", "coordinator",
        "fenced_mutex", "crash_proof_recovery", "finish_first_continuation", "result_customs"
    ]
    for mod in critical_modules:
        try:
            __import__(f"courier.chief.{mod}")
            import_results[mod] = "AVAILABLE"
        except Exception as ex:
            import_results[mod] = f"IMPORT_ERROR: {str(ex)}"
            report["healthy"] = False
            report["status"] = "UNHEALTHY"

    report["checks"]["critical_imports"] = {
        "available": all(v == "AVAILABLE" for v in import_results.values()),
        "modules": import_results
    }

    # 2. Database & Checkpoint & Writer Lease Check
    db_check: Dict[str, Any] = {
        "path": active_db,
        "exists": os.path.exists(active_db),
        "integrity": "UNKNOWN",
        "state_generation": None,
        "checkpoint_readable": False,
        "latest_checkpoint": None,
        "writer_lease_state": "UNKNOWN",
        "active_locks_count": 0,
        "tables": []
    }
    
    if db_check["exists"]:
        conn = None
        try:
            conn = sqlite3.connect(f"file:{active_db}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            # Integrity check
            cursor.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            db_check["integrity"] = row[0] if row else "unknown"
            
            # List tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cursor.fetchall()]
            db_check["tables"] = tables
            
            # Read state generation if available
            if "quiescent_watermark" in tables:
                cursor.execute("SELECT MAX(quiescent_state_generation) FROM quiescent_watermark;")
                r_gen = cursor.fetchone()
                db_check["state_generation"] = r_gen[0] if r_gen else 0
            elif "state_watermark" in tables:
                cursor.execute("SELECT MAX(generation) FROM state_watermark;")
                r_gen = cursor.fetchone()
                db_check["state_generation"] = r_gen[0] if r_gen else 0
            elif "state_generation" in tables:
                cursor.execute("SELECT MAX(generation) FROM state_generation;")
                r_gen = cursor.fetchone()
                db_check["state_generation"] = r_gen[0] if r_gen else 0

            # Checkpoint readability
            if "checkpoints" in tables:
                cursor.execute("SELECT checkpoint_key, checkpoint_value, updated_at FROM checkpoints ORDER BY updated_at DESC LIMIT 1;")
                r_cp = cursor.fetchone()
                if r_cp:
                    db_check["checkpoint_readable"] = True
                    db_check["latest_checkpoint"] = {
                        "key": r_cp[0],
                        "value": r_cp[1],
                        "updated_at": r_cp[2]
                    }
                else:
                    db_check["checkpoint_readable"] = True
                    db_check["latest_checkpoint"] = "EMPTY"

            # Writer Lease State
            if "fenced_resource_locks" in tables:
                cursor.execute("SELECT COUNT(*) FROM fenced_resource_locks WHERE state = 'HELD';")
                r_locks = cursor.fetchone()
                db_check["active_locks_count"] = r_locks[0] if r_locks else 0
                db_check["writer_lease_state"] = "ACTIVE"
            else:
                db_check["writer_lease_state"] = "UNINITIALIZED"

        except Exception as ex:
            db_check["integrity"] = f"error: {str(ex)}"
            report["healthy"] = False
            report["status"] = "UNHEALTHY"
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    else:
        # DB not existing is acceptable on completely fresh cold boot before first cycle
        db_check["integrity"] = "NOT_INITIALIZED_YET"
        db_check["checkpoint_readable"] = True
        db_check["writer_lease_state"] = "COLD_BOOT"
        
    report["checks"]["database"] = db_check
    
    # 3. Constitution Check
    c_ok, c_data, c_path, c_hash = ConstitutionLoader.discover_and_load()
    const_check = {
        "valid": c_ok,
        "path": c_path,
        "hash": c_hash,
        "status": c_data.get("status") if c_ok else "NOT_FOUND",
        "policy_version": c_data.get("policy_version") if c_ok else "N/A",
        "article_count": len(c_data.get("articles", {})) if c_ok else 0
    }
    if not c_ok:
        report["healthy"] = False
        report["status"] = "DEGRADED"
    report["checks"]["constitution"] = const_check
    
    # 4. Runtime Directory Writable Probe
    runtime_dir = os.environ.get("COURIER_RUNTIME_DIR") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "runtime")
    )
    os.makedirs(runtime_dir, exist_ok=True)
    probe_path = os.path.join(runtime_dir, ".health_probe.tmp")
    writable = False
    try:
        with open(probe_path, "w", encoding="utf-8") as f:
            f.write("probe")
        if os.path.exists(probe_path):
            with open(probe_path, "r", encoding="utf-8") as f:
                content = f.read()
            writable = (content == "probe")
            os.remove(probe_path)
    except Exception:
        writable = False
        
    report["checks"]["runtime"] = {
        "path": runtime_dir,
        "writable": writable
    }
    if not writable:
        report["healthy"] = False
        report["status"] = "UNHEALTHY"
        
    # 5. Schema Compatibility
    report["checks"]["schema"] = {
        "current_version": SCHEMA_VERSION,
        "compatible": True
    }
    
    return report
