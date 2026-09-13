"""
campaign_manager.py - Courier Continuation Campaign Manager
Mission Class: P0 Autonomy Infrastructure
Operating Phase: AUTONOMY_FIRST

Implements:
1. Multi-Signal Autonomy Budget: 100x weiter absorbed as raw execution budget, NOT as 100 tasks.
2. Campaign State Persistence: Persists CONTINUATION_CAMPAIGN_ACTIVE, RAW_WEITER_BUDGET, LOGICAL_INTENTS.
3. Coalescing Engine: Every duplicate weiter while campaign is active is treated as COALESCED_NOOP.
4. Bounded Window Execution: Runs bounded batches of 5-10 tasks per window without human intervention.
5. Permanent Constitution Invariant: Article 33 - One active campaign maximum; campaign owns continuation.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from .types import Lane, Host, TaskStatus, TwoLevelDone
from .control_plane import ControlPlane
from .safewrite import safe_write_json


class ContinuationCampaignManager:
    """Manages the lifecycle, budget, and coalescing of continuation campaigns."""

    DEFAULT_STATE_FILE = os.path.join(
        os.path.dirname(__file__), "..", "..", "project-memory", "data", "control_plane", "continuation_campaign.json"
    )

    def __init__(
        self,
        cp: Optional[ControlPlane] = None,
        state_file: Optional[str] = None
    ):
        self.cp = cp or ControlPlane()
        self.state_file = os.path.abspath(state_file or self.DEFAULT_STATE_FILE)
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self._init_db_table()

    def _init_db_table(self):
        with self.cp.get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS continuation_campaigns (
                campaign_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL,
                raw_weiter_observed INTEGER NOT NULL,
                weiter_absorbed INTEGER NOT NULL,
                logical_continuation_intents INTEGER NOT NULL,
                tasks_executed INTEGER NOT NULL,
                tasks_verified INTEGER NOT NULL,
                duplicate_signals_suppressed INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                last_updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            """)

    def start_or_get_campaign(
        self,
        campaign_id: str = "CAMP-WIN-FINAL-100X",
        raw_budget: int = 100
    ) -> Dict[str, Any]:
        """Activates or retrieves the active continuation campaign."""
        now = datetime.now(timezone.utc).isoformat()
        with self.cp.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM continuation_campaigns WHERE campaign_id = ?", (campaign_id,))
            row = cur.fetchone()
            if row:
                state = {
                    "campaign_id": row["campaign_id"],
                    "active": bool(row["active"]),
                    "raw_weiter_observed": row["raw_weiter_observed"],
                    "weiter_absorbed": row["weiter_absorbed"],
                    "logical_continuation_intents": row["logical_continuation_intents"],
                    "tasks_executed": row["tasks_executed"],
                    "tasks_verified": row["tasks_verified"],
                    "duplicate_signals_suppressed": row["duplicate_signals_suppressed"],
                    "started_at": row["started_at"],
                    "last_updated_at": row["last_updated_at"],
                    "status": row["status"],
                    "metadata": json.loads(row["metadata_json"])
                }
            else:
                metadata = {
                    "rule": "WHEN MULTIPLE CONTINUATION SIGNALS EXIST: signals do not multiply work. They extend permission to continue useful work. ONE ACTIVE CAMPAIGN MAXIMUM.",
                    "window_size": 5
                }
                state = {
                    "campaign_id": campaign_id,
                    "active": True,
                    "raw_weiter_observed": raw_budget,
                    "weiter_absorbed": max(0, raw_budget - 1),
                    "logical_continuation_intents": 1,
                    "tasks_executed": 0,
                    "tasks_verified": 0,
                    "duplicate_signals_suppressed": max(0, raw_budget - 1),
                    "started_at": now,
                    "last_updated_at": now,
                    "status": "ACTIVE_AUTO_WORKING",
                    "metadata": metadata
                }
                cur.execute("""
                INSERT INTO continuation_campaigns
                (campaign_id, active, raw_weiter_observed, weiter_absorbed, logical_continuation_intents,
                 tasks_executed, tasks_verified, duplicate_signals_suppressed, started_at, last_updated_at, status, metadata_json)
                VALUES (?, 1, ?, ?, 1, 0, 0, ?, ?, ?, 'ACTIVE_AUTO_WORKING', ?)
                """, (
                    campaign_id,
                    raw_budget,
                    max(0, raw_budget - 1),
                    max(0, raw_budget - 1),
                    now,
                    now,
                    json.dumps(metadata)
                ))

        safe_write_json(self.state_file, state)
        return state

    def consume_signal(self, signal: str = "weiter", campaign_id: str = "CAMP-WIN-FINAL-100X") -> Dict[str, Any]:
        """Absorbs an incoming continuation signal into the active campaign."""
        now = datetime.now(timezone.utc).isoformat()
        with self.cp.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM continuation_campaigns WHERE campaign_id = ?", (campaign_id,))
            row = cur.fetchone()
            if not row or not row["active"]:
                return {"action": "NO_ACTIVE_CAMPAIGN", "coalesced": False}

            new_observed = row["raw_weiter_observed"] + 1
            new_absorbed = row["weiter_absorbed"] + 1
            new_suppressed = row["duplicate_signals_suppressed"] + 1

            cur.execute("""
            UPDATE continuation_campaigns
            SET raw_weiter_observed = ?,
                weiter_absorbed = ?,
                duplicate_signals_suppressed = ?,
                last_updated_at = ?
            WHERE campaign_id = ?
            """, (new_observed, new_absorbed, new_suppressed, now, campaign_id))

        state = self.get_campaign_state(campaign_id)
        if state:
            safe_write_json(self.state_file, state)
        return {"action": "COALESCED_NOOP", "coalesced": True, "state": state}

    def record_progress(
        self,
        campaign_id: str,
        tasks_executed: int,
        tasks_verified: int,
        status: Optional[str] = None
    ):
        """Records verified tasks executed under this campaign."""
        now = datetime.now(timezone.utc).isoformat()
        with self.cp.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM continuation_campaigns WHERE campaign_id = ?", (campaign_id,))
            row = cur.fetchone()
            if not row:
                return

            tot_exec = row["tasks_executed"] + tasks_executed
            tot_veri = row["tasks_verified"] + tasks_verified
            st = status or row["status"]

            cur.execute("""
            UPDATE continuation_campaigns
            SET tasks_executed = ?,
                tasks_verified = ?,
                status = ?,
                last_updated_at = ?
            WHERE campaign_id = ?
            """, (tot_exec, tot_veri, st, now, campaign_id))

        state = self.get_campaign_state(campaign_id)
        if state:
            safe_write_json(self.state_file, state)

    def close_campaign(
        self,
        campaign_id: str,
        final_status: str = "COMPLETE_SAFE_WORK_EXHAUSTED"
    ):
        """Closes the campaign upon certified completion or exhaustion."""
        now = datetime.now(timezone.utc).isoformat()
        with self.cp.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE continuation_campaigns
            SET active = 0,
                status = ?,
                last_updated_at = ?
            WHERE campaign_id = ?
            """, (final_status, now, campaign_id))

        state = self.get_campaign_state(campaign_id)
        if state:
            safe_write_json(self.state_file, state)

    def get_campaign_state(self, campaign_id: str = "CAMP-WIN-FINAL-100X") -> Optional[Dict[str, Any]]:
        with self.cp.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM continuation_campaigns WHERE campaign_id = ?", (campaign_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "campaign_id": row["campaign_id"],
                "active": bool(row["active"]),
                "raw_weiter_observed": row["raw_weiter_observed"],
                "weiter_absorbed": row["weiter_absorbed"],
                "logical_continuation_intents": row["logical_continuation_intents"],
                "tasks_executed": row["tasks_executed"],
                "tasks_verified": row["tasks_verified"],
                "duplicate_signals_suppressed": row["duplicate_signals_suppressed"],
                "started_at": row["started_at"],
                "last_updated_at": row["last_updated_at"],
                "status": row["status"],
                "metadata": json.loads(row["metadata_json"])
            }
