"""
test_loop_controller.py - Autonomous Test Loop Control (Court M Compliance)
Mission Class: P0 Autonomy Infrastructure

Invariants:
1. Same (test, code SHA, state generation, input fingerprint) with a valid PASS: DO_NOT_REPEAT.
2. No endless full-suite reruns.
3. Code change or state change invalidates prior pass and permits re-execution.
"""

import os
import sys
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

from .control_plane import ControlPlane


class TestLoopController:
    """Prevents redundant test loop reruns under Court M."""

    def __init__(self, cp: Optional[ControlPlane] = None):
        self.cp = cp or ControlPlane()
        self._init_db()

    def _init_db(self):
        with self.cp.get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS test_loop_cache (
                cache_key TEXT PRIMARY KEY,
                test_identifier TEXT NOT NULL,
                code_sha TEXT NOT NULL,
                state_generation INTEGER NOT NULL,
                input_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                evidence TEXT,
                verified_at TEXT NOT NULL
            );
            """)

    def _compute_key(
        self,
        test_identifier: str,
        code_sha: str,
        state_generation: int,
        input_fingerprint: str
    ) -> str:
        raw = f"{test_identifier}:{code_sha}:{state_generation}:{input_fingerprint}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def should_execute(
        self,
        test_identifier: str,
        code_sha: str,
        state_generation: int,
        input_fingerprint: str
    ) -> Tuple[bool, str]:
        """
        Returns (should_run, reason).
        If valid PASS exists for this exact tuple: returns (False, 'DO_NOT_REPEAT').
        """
        key = self._compute_key(test_identifier, code_sha, state_generation, input_fingerprint)
        with self.cp.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status, verified_at FROM test_loop_cache WHERE cache_key = ?;", (key,))
            row = cur.fetchone()
            if row and row["status"] == "PASS":
                return False, f"DO_NOT_REPEAT: Valid PASS verified at {row['verified_at']}"

        return True, "EXECUTION_REQUIRED"

    def record_pass(
        self,
        test_identifier: str,
        code_sha: str,
        state_generation: int,
        input_fingerprint: str,
        evidence: Optional[str] = None
    ) -> str:
        """Records a verified pass in test loop cache."""
        key = self._compute_key(test_identifier, code_sha, state_generation, input_fingerprint)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.cp.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO test_loop_cache
            (cache_key, test_identifier, code_sha, state_generation, input_fingerprint, status, evidence, verified_at)
            VALUES (?, ?, ?, ?, ?, 'PASS', ?, ?);
            """, (key, test_identifier, code_sha, state_generation, input_fingerprint, evidence or "", now_iso))
        return key

    def invalidate(self, test_identifier: Optional[str] = None):
        """Invalidates cache if code or scope changes."""
        with self.cp.get_connection() as conn:
            if test_identifier:
                conn.execute("DELETE FROM test_loop_cache WHERE test_identifier = ?;", (test_identifier,))
            else:
                conn.execute("DELETE FROM test_loop_cache;")
