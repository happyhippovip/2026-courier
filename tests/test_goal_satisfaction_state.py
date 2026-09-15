import json
from unittest.mock import patch

import pytest

from scripts.courier_goal_satisfaction_engine import (
    GoalSatisfactionEngine,
    GoalSatisfactionStateIntegrityError,
)


def test_generic_goal_without_verified_effect_cannot_complete(tmp_path):
    engine = GoalSatisfactionEngine(tmp_path)
    assert engine.recompute("Improve this codebase", []) == "CONTINUE_SAFE_WORK"


def test_corrupt_state_fails_closed_without_overwrite(tmp_path):
    engine = GoalSatisfactionEngine(tmp_path)
    engine.db_file.write_text('{"broken":', encoding="utf-8")
    before = engine.db_file.read_bytes()

    with pytest.raises(GoalSatisfactionStateIntegrityError, match="CORRUPT_FAIL_CLOSED"):
        engine.recompute("Improve this codebase", [])

    assert engine.db_file.read_bytes() == before


def test_atomic_publish_failure_preserves_previous_goal_state(tmp_path):
    engine = GoalSatisfactionEngine(tmp_path)
    previous = {"goal": {"satisfaction_state": "CONTINUE_SAFE_WORK"}}
    engine.db_file.write_text(json.dumps(previous), encoding="utf-8")

    with patch(
        "scripts.courier_goal_satisfaction_engine.os.replace",
        side_effect=OSError("injected publish failure"),
    ):
        with pytest.raises(OSError, match="injected publish failure"):
            engine._write_all({"goal": {"satisfaction_state": "VERIFIED_COMPLETE"}})

    assert json.loads(engine.db_file.read_text(encoding="utf-8")) == previous
    assert list(engine.db_dir.glob(f".{engine.db_file.name}.tmp.*")) == []
