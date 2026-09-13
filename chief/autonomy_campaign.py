"""
autonomy_campaign.py - Windows Courier Autonomy Completion Campaign State Manager
Section 17 Chief Directive Compliance:
Persists:
- AUTONOMY_COMPLETION_CAMPAIGN = ACTIVE
- MISSION_GOAL = "prove and complete Windows Courier zero-human-clock autonomous operation"
- CAMPAIGN_STATE_GENERATION
- CURRENT_AUTONOMY_GAP_MAP
- LAST_VERIFIED_AUTONOMY_COURT
- NEXT_AUTONOMOUS_ACTION
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from .safewrite import safe_write_json

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CAMPAIGN_FILE = os.path.join(
    WORKSPACE_ROOT, "project-memory", "data", "control_plane", "autonomy_campaign.json"
)

AUTONOMY_COURTS_DEFINITION = [
    ("COURT_A", "SINGLE_TRIGGER", "One human start signal runs >=3 tasks without external clocking"),
    ("COURT_B", "INTERNAL_SUCCESSOR_SELECTION", "Reconcile, inspect goal, discover gaps, rank value, select next safe task"),
    ("COURT_C", "DURABLE_STATE", "Mission, goal, task, lease, result, checkpoint survive restart without chat"),
    ("COURT_D", "FRESH_SESSION_RESUME", "Boot fresh session from disk, identify state, resume safely"),
    ("COURT_E", "EXACTLY_ONCE_EXECUTION", "Replay inputs produce no duplicate logical effect"),
    ("COURT_F", "CONCURRENT_DUPLICATE_INPUT", "Concurrent continuation requests yield single winner"),
    ("COURT_G", "WRITER_EXCLUSIVITY", "Strict 1-writer lease per domain; stale lease recoverable"),
    ("COURT_H", "CRASH_BEFORE_EFFECT", "Crash before effect recovered cleanly, no corruption"),
    ("COURT_I", "CRASH_AFTER_EFFECT", "Effect detected on restart, not repeated, verified and checkpointed"),
    ("COURT_J", "CHECKPOINT_INTEGRITY", "Authority based on 6-tuple (task_id, version, state_gen, result_fp, evidence, verified_at)"),
    ("COURT_K", "RESULT_CUSTOMS", "Worker self-certification disallowed; exit 0 alone insufficient; effect proven"),
    ("COURT_L", "FAILURE_LOOP_CONTROL", "Repeated identical failure triggers CRASH_LOOP_DETECTED and parks branch"),
    ("COURT_M", "TEST_LOOP_CONTROL", "Same test, code SHA, state generation, input fingerprint with PASS -> DO_NOT_REPEAT"),
    ("COURT_N", "QUEUE_REPLAY_CONTROL", "100 duplicate weiter signals collapse into active campaign"),
    ("COURT_O", "QUIESCENT_WAKEUP", "Duplicate weiter during quiescence is NOOP; new directive wakes exactly once"),
    ("COURT_P", "VALUE_GOVERNED_DISCOVERY", "Inspect real gaps with source evidence; reject busywork and filler"),
    ("COURT_Q", "BRANCH_LOCAL_BLOCKERS", "Local blocked task or human gate does not block independent safe work"),
    ("COURT_R", "RESOURCE_HYGIENE", "Zero duplicate writers, orphan subprocesses, stale leases, process storms"),
    ("COURT_S", "MAC_ISOLATION", "Mac scope and universuX untouched; zero conflicting writes"),
    ("COURT_T", "HUMAN_CLOCK_REMOVAL", "Decisive standard: HUMAN_CONTINUATION_REQUIRED = 0 across task succession"),
]


class AutonomyCampaignManager:
    """Tracks and persists the Full Autonomy Completion Campaign."""

    def __init__(self, campaign_file: str = DEFAULT_CAMPAIGN_FILE):
        self.campaign_file = os.path.abspath(campaign_file)
        os.makedirs(os.path.dirname(self.campaign_file), exist_ok=True)

    def initialize_campaign(
        self,
        state_generation: int = 88,
        active: bool = True
    ) -> Dict[str, Any]:
        """Initializes or resets the campaign state with all 20 courts."""
        now_iso = datetime.now(timezone.utc).isoformat()
        gap_map = {}
        for court_id, name, desc in AUTONOMY_COURTS_DEFINITION:
            gap_map[court_id] = {
                "court_id": court_id,
                "name": name,
                "description": desc,
                "classification": "UNPROVEN",
                "verified_at": None,
                "evidence": None
            }

        state = {
            "AUTONOMY_COMPLETION_CAMPAIGN": "ACTIVE" if active else "COMPLETE",
            "MISSION_GOAL": "prove and complete Windows Courier zero-human-clock autonomous operation",
            "CAMPAIGN_STATE_GENERATION": state_generation,
            "STARTED_AT": now_iso,
            "UPDATED_AT": now_iso,
            "CURRENT_AUTONOMY_GAP_MAP": gap_map,
            "LAST_VERIFIED_AUTONOMY_COURT": None,
            "NEXT_AUTONOMOUS_ACTION": "EXECUTE_20_COURT_ACCEPTANCE_SUITE",
            "STATISTICS": {
                "total_courts": 20,
                "proven_count": 0,
                "partial_count": 0,
                "unproven_count": 20,
                "defective_count": 0,
                "not_applicable_count": 0
            }
        }
        safe_write_json(self.campaign_file, state)
        return state

    def load_campaign(self) -> Dict[str, Any]:
        """Loads campaign state or initializes if missing."""
        if os.path.exists(self.campaign_file):
            try:
                with open(self.campaign_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self.initialize_campaign()

    def update_court(
        self,
        court_id: str,
        classification: str,
        evidence: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates the status and evidence of a specific autonomy court."""
        state = self.load_campaign()
        gap_map = state.setdefault("CURRENT_AUTONOMY_GAP_MAP", {})
        now_iso = datetime.now(timezone.utc).isoformat()

        if court_id in gap_map:
            gap_map[court_id]["classification"] = classification
            gap_map[court_id]["evidence"] = evidence
            gap_map[court_id]["verified_at"] = now_iso
            state["LAST_VERIFIED_AUTONOMY_COURT"] = court_id

        # Recount statistics
        proven = sum(1 for c in gap_map.values() if c.get("classification") == "PROVEN_CURRENT_VERSION")
        partial = sum(1 for c in gap_map.values() if c.get("classification") == "PARTIAL")
        unproven = sum(1 for c in gap_map.values() if c.get("classification") == "UNPROVEN")
        defective = sum(1 for c in gap_map.values() if c.get("classification") == "DEFECTIVE")
        na = sum(1 for c in gap_map.values() if c.get("classification") == "NOT_APPLICABLE")

        state["STATISTICS"] = {
            "total_courts": 20,
            "proven_count": proven,
            "partial_count": partial,
            "unproven_count": unproven,
            "defective_count": defective,
            "not_applicable_count": na
        }
        state["UPDATED_AT"] = now_iso

        if proven == 20:
            state["AUTONOMY_COMPLETION_CAMPAIGN"] = "COMPLETE"
            state["NEXT_AUTONOMOUS_ACTION"] = "NONE_AUTONOMY_PROVEN"
        else:
            state["AUTONOMY_COMPLETION_CAMPAIGN"] = "ACTIVE"

        safe_write_json(self.campaign_file, state)
        return state

    def complete_campaign(self) -> Dict[str, Any]:
        """Marks the campaign as complete upon 20/20 verification."""
        state = self.load_campaign()
        now_iso = datetime.now(timezone.utc).isoformat()
        state["AUTONOMY_COMPLETION_CAMPAIGN"] = "COMPLETE"
        state["UPDATED_AT"] = now_iso
        state["NEXT_AUTONOMOUS_ACTION"] = "NONE_AUTONOMY_PROVEN"
        safe_write_json(self.campaign_file, state)
        return state
