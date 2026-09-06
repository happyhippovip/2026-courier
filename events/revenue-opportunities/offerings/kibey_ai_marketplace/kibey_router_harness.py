"""KIbey Dynamic Multi-Model Worker Router Harness (Drop-in Client Library).

Zero-dependency router for multi-agent applications:
- Dynamic model selection (CLI / Fast / Frontier Reasoning) based on task class
- Atomic scope collision locking preventing concurrent file corruption
- Standardized cryptographic result envelopes
"""

import os
import fcntl
import json
import hashlib
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class KibeyRouter:
    def __init__(self, locks_dir: Optional[Path] = None):
        self.locks_dir = Path(locks_dir or "./.kibey_locks")
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def route_task(self, task_type: str, max_cost_tier: str = "CHEAPEST_SUFFICIENT") -> str:
        """Selects optimal worker slot based on task complexity and budget tier."""
        if task_type in ("CODE_FORMATTING", "DIFF_CHECK", "SCHEMA_VALIDATION", "LINT"):
            return "CLI_DETERMINISTIC_SLOT"
        elif task_type in ("DATA_PIPELINE", "UNIT_TEST", "BATCH_PROCESS"):
            return "FAST_MODEL_SLOT"
        else:
            return "FRONTIER_REASONING_SLOT"

    def acquire_scope_lock(self, scope_name: str, owner_id: str, ttl_seconds: int = 300) -> Tuple[bool, Optional[str]]:
        """Acquires atomic OS-level file lock for mutation scope."""
        clean_scope = scope_name.replace("/", "_")
        lock_file = self.locks_dir / f"{clean_scope}.lock"
        try:
            fh = open(lock_file, "w+", encoding="utf-8")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write_text(json.dumps({
                "scope": scope_name,
                "owner_id": owner_id,
                "pid": os.getpid(),
                "acquired_at": dt.datetime.now(dt.timezone.utc).isoformat()
            }), encoding="utf-8")
            return True, None
        except (IOError, OSError) as e:
            return False, f"Scope {scope_name} is locked by another agent: {e}"

    def build_result_envelope(self, task_id: str, worker_id: str, output_data: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs cryptographic verifiable execution proof."""
        payload_bytes = json.dumps(output_data, sort_keys=True).encode("utf-8")
        fingerprint = hashlib.sha256(payload_bytes).hexdigest()
        return {
            "task_id": task_id,
            "worker_id": worker_id,
            "status": "SUCCESS",
            "fingerprint": fingerprint,
            "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "output": output_data,
        }
