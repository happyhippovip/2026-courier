"""
queue_coalescer.py - P0 Queue Collapse & Stale 'weiter' Suppression Engine
Part of WINDOWS COURIER P0 QUEUE COLLAPSE / STALE weiter SUPPRESSION.

Invariants:
1. 1 or 100 identical 'weiter' messages represent at most 1 logical continuation intent.
2. Stale queued continuations from older state generations are dropped without replaying verified work.
3. Genuine new human goals are preserved and never discarded as duplicate noise.
4. Monotonic state generation sequence: STATE_GENERATION = N -> N + 1.
5. Coalescing never stalls autonomous forward progression.
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

WORKSPACE_ROOT = os.environ.get("COURIER_WORKSPACE_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
DEFAULT_DB_PATH = os.environ.get("COURIER_DB_PATH") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "chief_control_plane.db")
)
DEFAULT_RUNTIME_DIR = os.environ.get("COURIER_RUNTIME_DIR") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "runtime")
)
DEFAULT_COALESCER_STATE_FILE = os.path.join(DEFAULT_RUNTIME_DIR, "queue_coalescer_state.json")

BARE_CONTINUATION_KEYWORDS = {
    "weiter", "continue", "go", "weiter.", "weiter!", "weiter...",
    "weiter bitte", "bitte weiter", "weiter machen", "mach weiter"
}

class QueueCoalescer:
    def __init__(self, db_path: str = DEFAULT_DB_PATH, state_file: str = DEFAULT_COALESCER_STATE_FILE):
        self.db_path = os.path.abspath(db_path)
        self.state_file = os.path.abspath(state_file)
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS queue_coalescer_metrics (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                current_state_generation INTEGER NOT NULL,
                active_logical_intent_id TEXT,
                intent_status TEXT NOT NULL,
                intent_generation INTEGER NOT NULL,
                raw_continuation_events_received INTEGER NOT NULL,
                continuations_coalesced INTEGER NOT NULL,
                stale_continuations_dropped INTEGER NOT NULL,
                logical_continuation_intents INTEGER NOT NULL,
                duplicate_tasks_prevented INTEGER NOT NULL,
                verified_tasks_replayed INTEGER NOT NULL,
                last_event_timestamp TEXT NOT NULL
            );
            """)
            cur.execute("""
            INSERT OR IGNORE INTO queue_coalescer_metrics (
                singleton_id, current_state_generation, active_logical_intent_id,
                intent_status, intent_generation, raw_continuation_events_received,
                continuations_coalesced, stale_continuations_dropped, logical_continuation_intents,
                duplicate_tasks_prevented, verified_tasks_replayed, last_event_timestamp
            ) VALUES (
                1, 1, NULL, 'NONE', 1, 0, 0, 0, 0, 0, 0, ?
            );
            """, (datetime.now(timezone.utc).isoformat(),))
            conn.commit()

    def get_metrics(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM queue_coalescer_metrics WHERE singleton_id = 1;")
            row = cur.fetchone()
            if row:
                return dict(row)
            return {}

    def _save_metrics(self, data: Dict[str, Any]):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE queue_coalescer_metrics SET
                current_state_generation = ?,
                active_logical_intent_id = ?,
                intent_status = ?,
                intent_generation = ?,
                raw_continuation_events_received = ?,
                continuations_coalesced = ?,
                stale_continuations_dropped = ?,
                logical_continuation_intents = ?,
                duplicate_tasks_prevented = ?,
                verified_tasks_replayed = ?,
                last_event_timestamp = ?
            WHERE singleton_id = 1;
            """, (
                data["current_state_generation"],
                data["active_logical_intent_id"],
                data["intent_status"],
                data["intent_generation"],
                data["raw_continuation_events_received"],
                data["continuations_coalesced"],
                data["stale_continuations_dropped"],
                data["logical_continuation_intents"],
                data["duplicate_tasks_prevented"],
                data["verified_tasks_replayed"],
                now_iso
            ))
            conn.commit()

        # Write-ahead JSON persistence
        tmp = self.state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.state_file)

    @staticmethod
    def is_bare_continuation(text: str) -> bool:
        """Determines if text is a bare continuation versus genuine new instructions."""
        norm = text.strip().lower()
        if norm in BARE_CONTINUATION_KEYWORDS:
            return True
        # Check repetitive words like "weiter weiter weiter"
        words = norm.split()
        if words and all(w in ("weiter", "continue", "go") for w in words):
            return True
        return False

    def process_raw_input(
        self,
        raw_text: str,
        active_task_status: str = "IDLE",
        active_task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingests a message from the queue and applies semantic coalescing:
        - If new human goal: preserves it immediately.
        - If bare continuation: coalesces duplicates and drops stale generation signals.
        """
        metrics = self.get_metrics()
        gen = metrics["current_state_generation"]

        # 1. Distinguish genuine new human instructions
        if not self.is_bare_continuation(raw_text):
            return {
                "decision": "PRESERVE_NEW_GOAL",
                "is_new_goal": True,
                "extracted_goal": raw_text.strip(),
                "action": "INSPECT_AND_INCORPORATE_GOAL",
                "duplicate_tasks_created": 0
            }

        # 2. Bare continuation: track receipt
        metrics["raw_continuation_events_received"] += 1

        # Check if an in-flight task is actively running
        if active_task_status == "RUNNING":
            metrics["continuations_coalesced"] += 1
            metrics["duplicate_tasks_prevented"] += 1
            self._save_metrics(metrics)
            return {
                "decision": "COALESCED_IN_FLIGHT",
                "reason": f"Task {active_task_id} is already RUNNING. Duplicate continuation coalesced.",
                "state_generation": gen,
                "duplicate_tasks_created": 0,
                "verified_tasks_replayed": 0,
                "action": "MONITOR_IN_FLIGHT"
            }

        # Check if there is already an outstanding logical intent for this generation
        if metrics["intent_status"] in ("PENDING", "ACTIVE") and metrics["intent_generation"] == gen:
            metrics["continuations_coalesced"] += 1
            metrics["duplicate_tasks_prevented"] += 1
            self._save_metrics(metrics)
            return {
                "decision": "COALESCED_EXISTING_INTENT",
                "reason": f"Logical continuation intent {metrics['active_logical_intent_id']} is already active for generation {gen}.",
                "state_generation": gen,
                "duplicate_tasks_created": 0,
                "verified_tasks_replayed": 0,
                "action": "WAIT_FOR_ACTIVE_INTENT"
            }

        # First continuation in this generation: materialize ONE logical intent
        metrics["logical_continuation_intents"] += 1
        intent_id = f"INTENT-GEN{gen}-{int(time.time() * 1000)}"
        metrics["active_logical_intent_id"] = intent_id
        metrics["intent_status"] = "PENDING"
        metrics["intent_generation"] = gen
        self._save_metrics(metrics)

        return {
            "decision": "LOGICAL_INTENT_MATERIALIZED",
            "intent_id": intent_id,
            "state_generation": gen,
            "duplicate_tasks_created": 0,
            "verified_tasks_replayed": 0,
            "action": "EXECUTE_RECONCILIATION"
        }

    def process_queue_burst(
        self,
        messages: List[str],
        active_task_status: str = "IDLE",
        active_task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Processes a burst of messages (e.g. 50-250 queued messages) in one pass."""
        results = []
        for msg in messages:
            res = self.process_raw_input(msg, active_task_status, active_task_id)
            results.append(res)
            # If the first message created an intent, subsequent bare continuations see PENDING
            if res.get("decision") == "LOGICAL_INTENT_MATERIALIZED":
                active_task_status = "RUNNING"

        metrics = self.get_metrics()
        logical_created = sum(1 for r in results if r.get("decision") == "LOGICAL_INTENT_MATERIALIZED")
        coalesced = sum(1 for r in results if "COALESCED" in r.get("decision", ""))
        new_goals = sum(1 for r in results if r.get("is_new_goal"))

        return {
            "total_messages_processed": len(messages),
            "logical_continuation_intents_created": logical_created,
            "continuations_coalesced": coalesced,
            "new_goals_preserved": new_goals,
            "duplicate_tasks_created": 0,
            "verified_tasks_replayed": 0,
            "state_generation": metrics["current_state_generation"]
        }

    def advance_state_generation(self, completed_task_id: str) -> int:
        """
        Advances the monotonic state generation upon task verification/completion.
        Marks any active intent as SATISFIED.
        """
        metrics = self.get_metrics()
        metrics["current_state_generation"] += 1
        metrics["intent_status"] = "SATISFIED"
        metrics["active_logical_intent_id"] = None
        self._save_metrics(metrics)
        return metrics["current_state_generation"]

    def handle_stale_continuation_check(self, incoming_generation: int) -> bool:
        """Checks if an incoming continuation refers to a superseded state generation."""
        metrics = self.get_metrics()
        if incoming_generation < metrics["current_state_generation"]:
            metrics["stale_continuations_dropped"] += 1
            metrics["duplicate_tasks_prevented"] += 1
            self._save_metrics(metrics)
            return True # Is stale
        return False

    def get_observability_report(
        self,
        current_task: Optional[str] = None,
        current_goal: str = "GOAL-05"
    ) -> Dict[str, Any]:
        """Provides full observability report required by the prompt."""
        m = self.get_metrics()
        return {
            "RAW_CONTINUATION_EVENTS_RECEIVED": m["raw_continuation_events_received"],
            "CONTINUATIONS_COALESCED": m["continuations_coalesced"],
            "STALE_CONTINUATIONS_DROPPED": m["stale_continuations_dropped"],
            "LOGICAL_CONTINUATION_INTENTS": m["logical_continuation_intents"],
            "DUPLICATE_TASKS_PREVENTED": m["duplicate_tasks_prevented"],
            "VERIFIED_TASKS_REPLAYED": m["verified_tasks_replayed"],
            "CURRENT_STATE_GENERATION": m["current_state_generation"],
            "CURRENT_TASK": current_task or m.get("active_logical_intent_id") or "TASK-WIN-64",
            "CURRENT_GOAL": current_goal
        }
