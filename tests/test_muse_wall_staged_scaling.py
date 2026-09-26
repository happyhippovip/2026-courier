"""Tests for Muse Wall staged scaling, resource governor integration, and
the complete slot lifecycle: init → assign → run → done → stop.

Validates the 1→4→8→16 scaling policy and fail-closed gates.
"""
import json
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.windows_muse_wall.supervisor import MuseWallSupervisor
from scripts.windows_muse_wall.slot_state import (
    SLOT_STATES,
    SlotLock,
    StateCorruptionError,
    atomic_write,
    default_slot,
    read_json,
)


@pytest.fixture
def wall(tmp_path):
    """Create an isolated wall supervisor for testing."""
    config = {
        "desired_slots": 16,
        "active_limit": 4,
        "provider_launch_enabled": True,
        "staged_levels": [1, 4, 8, 16, 32, 64],
        "minimum_free_memory_mb": 2500,
        "real_jobs_enabled": False,
    }
    sup = MuseWallSupervisor(tmp_path, config)
    sup.initialize()
    return sup


class TestStagedScaling:
    """The wall must scale 1→4→8→16→32→64, each gate requiring previous PASS."""

    def test_admit_1_is_always_allowed(self, wall):
        """Stage 1 admission never requires a previous pass."""
        assert wall.admitted_count(1) == 1

    def test_admit_4_capped_by_active_limit(self, wall):
        """Active limit of 4 caps admission to 4."""
        assert wall.admitted_count(4) == 4

    def test_admit_8_capped_by_active_limit(self, wall):
        """Requesting 8 with active_limit=4 caps to 4."""
        assert wall.admitted_count(8) == 4

    def test_admit_16_capped_by_desired(self, wall):
        """Cannot exceed desired_slots."""
        wall.config["active_limit"] = 32
        assert wall.admitted_count(16) == 16

    def test_admit_rejects_non_staged_level(self, wall):
        """Non-staged levels (e.g. 3, 5, 7) are rejected."""
        with pytest.raises(ValueError, match="not an approved stage"):
            wall.admitted_count(3)


class TestSlotLifecycle:
    """Full slot lifecycle: READY → assign → run → DONE."""

    def test_assign_run_done_lifecycle(self, wall):
        """A test job goes through assign → run → done."""
        slot_id = "MUSE-01"
        job_id = "JOB-01"

        # Assign
        result = wall.assign_job(slot_id, job_id, kind="test")
        assert result["assigned"] is True

        # Run
        run_result = wall.run_job(slot_id)
        assert run_result["started"] is True

        # Wait for the test job to finish (it's just a print)
        time.sleep(2)

        # Check status — should be DONE
        status = wall.job_status(slot_id)
        assert status["job"]["status"] == "DONE"

    def test_assign_rejects_cross_slot_job(self, wall):
        """JOB-02 cannot be assigned to MUSE-01 (mismatch)."""
        result = wall.assign_job("MUSE-01", "JOB-02", kind="test")
        assert result["assigned"] is False
        assert result["reason"] == "slot_job_mismatch"

    def test_all_16_slots_unique_identity(self, wall):
        """Each slot has a unique owner_token and workdir."""
        tokens = set()
        workdirs = set()
        for i in range(1, 17):
            slot = wall.load_slot(f"MUSE-{i:02d}")
            tokens.add(slot["owner_token"])
            workdirs.add(slot["workdir"])
        assert len(tokens) == 16
        assert len(workdirs) == 16


class TestWallStatus:
    """Status reporting must reflect actual state."""

    def test_initial_all_ready(self, wall):
        """After init, all slots are READY."""
        status = wall.status()
        assert status["states"]["READY"] == 16

    def test_no_crashed_after_clean_init(self, wall):
        """No CRASHED slots after clean initialization."""
        status = wall.status()
        assert status["states"].get("CRASHED", 0) == 0

    def test_provider_launch_status_reported(self, wall):
        """Status reports whether provider launch is enabled."""
        status = wall.status()
        assert "provider_launch_enabled" in status


class TestConfigSafety:
    """Shipped config must be safe by default."""

    def test_shipped_config_has_provider_disabled(self):
        """config.json ships with provider_launch_enabled=false."""
        config_path = Path(__file__).parent.parent / "scripts" / "windows_muse_wall" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["provider_launch_enabled"] is False

    def test_shipped_config_has_valid_active_limit(self):
        """config.json active_limit must be 0 or a proven staged_level."""
        config_path = Path(__file__).parent.parent / "scripts" / "windows_muse_wall" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        valid = [0] + config["staged_levels"]
        assert config["active_limit"] in valid, (
            "active_limit=%d not in valid set %s" % (config["active_limit"], valid)
        )

    def test_shipped_config_has_correct_stages(self):
        """config.json has the canonical staged_levels."""
        config_path = Path(__file__).parent.parent / "scripts" / "windows_muse_wall" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["staged_levels"] == [1, 4, 8, 16, 32, 64]
