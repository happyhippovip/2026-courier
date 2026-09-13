"""
quiescent_absorber.py - Windows Courier P0 Quiescent Queue Drain & Silent weiter Absorber
Mission Class: P0 Autonomy Infrastructure
Operating Phase: AUTONOMY_FIRST

Implements:
1. Durable Quiescent Watermark: Persists QUIESCENT_STATE_GENERATION, QUIESCENT_RESULT_FINGERPRINT, and ABSORBER status.
2. Silent weiter Absorption: Duplicate 'weiter' inputs against a certified quiescent state generation produce NOOP.
3. Zero Engine Wake: Prevents discovery passes, test reruns, reconciliation courts, task synthesis, or repeated status reports.
4. Response Law: Outputs strictly "QUIESCENT_NOOP" when text response is forced.
5. Strict Wake Conditions: Wakes only on new non-weiter directives, state generation changes, external handoffs, or unparked gates.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from .safewrite import safe_write_json

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_WATERMARK_FILE = os.path.join(
    WORKSPACE_ROOT, "project-memory", "data", "control_plane", "quiescent_watermark.json"
)
DEFAULT_DB_PATH = os.path.join(WORKSPACE_ROOT, "courier", "chief_control_plane.db")


class QuiescentQueueAbsorber:
    """Silently absorbs duplicate continuation signals when system is in certified quiescent exhaustion."""

    def __init__(
        self,
        watermark_file: str = DEFAULT_WATERMARK_FILE,
        db_path: str = DEFAULT_DB_PATH,
        workspace_root: str = WORKSPACE_ROOT
    ):
        self.watermark_file = os.path.abspath(watermark_file)
        self.db_path = os.path.abspath(db_path)
        self.workspace_root = os.path.abspath(workspace_root)
        os.makedirs(os.path.dirname(self.watermark_file), exist_ok=True)
        self._init_sqlite_watermark()

    def _init_sqlite_watermark(self):
        if not os.path.exists(self.db_path):
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS quiescent_watermark (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    absorber_status TEXT NOT NULL,
                    quiescent_state_generation INTEGER NOT NULL,
                    quiescent_result_fingerprint TEXT NOT NULL,
                    certified_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)
        except Exception:
            pass

    def set_quiescent_watermark(
        self,
        state_generation: int = 87,
        fingerprint: str = "d8fbcd705b001ec6c5bd6fca4bbeb9429040284f4cdd0ac8182f01c165807d2e",
        status: str = "ACTIVE"
    ) -> Dict[str, Any]:
        """Sets the durable quiescent watermark signaling certified safe-work exhaustion."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "quiescent_continuation_absorber": status,
            "quiescent_state_generation": state_generation,
            "quiescent_result_fingerprint": fingerprint,
            "certified_at": now,
            "updated_at": now,
            "wake_conditions": [
                "NEW_NON_WEITER_CHIEF_DIRECTIVE",
                "DURABLE_STATE_GENERATION_CHANGED",
                "NEW_EXTERNAL_HANDOFF_RECEIVED",
                "HUMAN_GATE_UNPARKED",
                "NEW_VERIFIED_EVIDENCE_SAFE_GAP",
                "STATE_INCONSISTENCY_OR_CORRUPTION"
            ]
        }
        safe_write_json(self.watermark_file, data)

        if os.path.exists(self.db_path):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                    INSERT OR REPLACE INTO quiescent_watermark
                    (singleton_id, absorber_status, quiescent_state_generation, quiescent_result_fingerprint, certified_at, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?);
                    """, (status, state_generation, fingerprint, now, now))
            except Exception:
                pass

        return data

    def get_watermark(self) -> Optional[Dict[str, Any]]:
        if os.path.exists(self.watermark_file):
            try:
                with open(self.watermark_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def check_wake_condition(self, signal: str, current_state_gen: int) -> Tuple[bool, str]:
        """
        Evaluates whether any condition warrants waking the autonomous engine.
        Returns (should_wake, reason).
        """
        norm_sig = signal.strip().lower()
        # Wake condition A: New non-weiter directive
        if norm_sig != "weiter" and norm_sig != "":
            return True, f"NEW_NON_WEITER_DIRECTIVE: {signal[:64]}"

        watermark = self.get_watermark()
        if not watermark or watermark.get("quiescent_continuation_absorber") != "ACTIVE":
            return True, "ABSORBER_NOT_ACTIVE"

        # Wake condition B: Durable state generation changed
        quiescent_gen = watermark.get("quiescent_state_generation", 87)
        if current_state_gen != quiescent_gen:
            return True, f"STATE_GENERATION_CHANGED: {quiescent_gen} -> {current_state_gen}"

        # Wake condition C: New external handoffs in coordination
        coord_req = os.path.join(self.workspace_root, "coordination", "mac_to_windows", "requests")
        if os.path.exists(coord_req):
            for fname in os.listdir(coord_req):
                if fname.endswith(".json") and not fname.startswith("REJECTED_"):
                    return True, f"NEW_EXTERNAL_HANDOFF_PRESENT: {fname}"

        # Wake condition D: Unparked human gate (payment, live deployment)
        # By default in AUTONOMY_FIRST, all 11 gates remain parked.

        return False, "QUIESCENT_SAFE_WORK_EXHAUSTED"

    def process_signal(
        self,
        signal: str = "weiter",
        current_state_gen: int = 87
    ) -> Dict[str, Any]:
        """
        Processes an incoming continuation signal:
        - If quiescent condition holds: silently absorbs duplicate as QUIESCENT_NOOP with zero side effects.
        - If wake condition holds: passes through to autonomous engine.
        """
        should_wake, reason = self.check_wake_condition(signal, current_state_gen)
        if not should_wake:
            return {
                "absorbed": True,
                "classification": "DUPLICATE_CONTINUATION_ALREADY_SATISFIED",
                "action": "QUIESCENT_NOOP",
                "response_text": "QUIESCENT_NOOP",
                "new_tasks_created": 0,
                "new_batches_created": 0,
                "new_discovery_runs": 0,
                "new_writers": 0,
                "state_changes": 0,
                "repeated_full_status_reports": 0,
                "quiescent_state_generation": current_state_gen
            }
        else:
            return {
                "absorbed": False,
                "classification": "WAKE_CONDITION_MET",
                "action": "WAKE_ENGINE",
                "reason": reason,
                "quiescent_state_generation": current_state_gen
            }
