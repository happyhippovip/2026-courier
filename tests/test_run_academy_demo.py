import json
import pytest
import sys
from unittest.mock import patch
from scripts.run_academy_demo import run_academy_demo

def _mocks():
    return (
        patch("scripts.run_academy_demo.AcademyTeacher"),
        patch("scripts.run_academy_demo.AcademyDirector"),
        patch("scripts.run_academy_demo.UpdateSteward"),
    )

def _wire(mock_teacher_cls, mock_director_cls, mock_steward_cls, snapshots=None):
    mock_teacher = mock_teacher_cls.return_value
    mock_director = mock_director_cls.return_value
    mock_steward = mock_steward_cls.return_value
    mock_teacher.propose_lesson.return_value = {
        "lesson_id": "test_lesson_123",
        "novelty_hash": "deadbeef12345678",
    }
    mock_director.review_lesson.return_value = {"status": "APPROVED_FOR_TEST"}
    mock_director.evaluate_lesson.return_value = {
        "verdict": "PASS",
        "metrics": {"measured_minutes_saved": 5.0},
    }
    mock_director.approve_adoption.return_value = {"adoption_id": "adopt_123"}
    if snapshots is None:
        mock_steward.get_latest_snapshot.return_value = {}
    else:
        mock_steward.get_latest_snapshot.side_effect = snapshots
    mock_teacher.queue_or_deliver_lesson.return_value = {
        "delivery_id": "del_123",
        "status": "QUEUED",
    }
    mock_director.record_worker_acknowledgement.return_value = {
        "adoption_status": "ACKNOWLEDGED",
    }
    return mock_teacher, mock_director, mock_steward

def _write_measurement(path, baseline_runtime=20.0, candidate_runtime=10.0, pass_rate=1.0):
    path.write_text(json.dumps({
        "baseline": {
            "method": "measured baseline",
            "runtime_seconds": baseline_runtime,
            "error_count": 0,
            "test_pass_rate": pass_rate,
        },
        "candidate": {
            "method": "measured candidate",
            "runtime_seconds": candidate_runtime,
            "error_count": 0,
            "test_pass_rate": pass_rate,
        },
    }), encoding="utf-8")

def test_run_academy_demo_literals_are_not_measured(capsys):
    teacher_p, director_p, steward_p = _mocks()
    with teacher_p as mock_teacher_cls, director_p as mock_director_cls, steward_p as mock_steward_cls:
        _teacher, mock_director, _steward = _wire(mock_teacher_cls, mock_director_cls, mock_steward_cls)
        res = run_academy_demo(reset=False)
        captured = capsys.readouterr().out
        assert "100% PASS" not in captured
        assert res["status"] != "COMPLETED"
        assert res["exit_code"] != 0
        mock_director.evaluate_lesson.assert_not_called()
        mock_director.approve_adoption.assert_not_called()

def test_run_academy_demo_literal_file_is_not_measured(tmp_path, capsys):
    measurement = tmp_path / "literals.json"
    _write_measurement(measurement, baseline_runtime=12.5, candidate_runtime=6.8)
    teacher_p, director_p, steward_p = _mocks()
    with teacher_p as mock_teacher_cls, director_p as mock_director_cls, steward_p as mock_steward_cls:
        _teacher, mock_director, _steward = _wire(mock_teacher_cls, mock_director_cls, mock_steward_cls)
        res = run_academy_demo(reset=False, measurement_path=str(measurement))
        assert "100% PASS" not in capsys.readouterr().out
        assert res["exit_code"] != 0
        mock_director.evaluate_lesson.assert_not_called()

def test_run_academy_demo_measured_pass_reads_back(tmp_path, capsys):
    measurement = tmp_path / "measured.json"
    _write_measurement(measurement)
    teacher_p, director_p, steward_p = _mocks()
    with teacher_p as mock_teacher_cls, director_p as mock_director_cls, steward_p as mock_steward_cls:
        mock_teacher, mock_director, mock_steward = _wire(
            mock_teacher_cls,
            mock_director_cls,
            mock_steward_cls,
            snapshots=[
                {"context_version": 42},
                {"context_version": 43, "snapshot_hash": "abcdef123"},
            ],
        )
        res = run_academy_demo(reset=False, measurement_path=str(measurement))
        captured = capsys.readouterr().out
        assert "100% PASS" in captured
        assert res["status"] == "COMPLETED"
        assert res["exit_code"] == 0
        assert res["lesson_id"] == "test_lesson_123"
        assert res["eval_verdict"] == "PASS"
        assert res["measured_minutes_saved"] == 5.0
        assert res["context_version_before"] == 42
        assert res["context_version_after"] == 43
        mock_director.evaluate_lesson.assert_called_once()
        baseline, candidate = mock_director.evaluate_lesson.call_args.args[1:]
        assert baseline["runtime_seconds"] == 20.0
        assert candidate["runtime_seconds"] == 10.0
        assert baseline["test_pass_rate"] == 1.0
        assert candidate["test_pass_rate"] == 1.0
        mock_director.approve_adoption.assert_called_once_with("test_lesson_123")
        assert mock_steward.get_latest_snapshot.call_count == 2
        mock_teacher.queue_or_deliver_lesson.assert_called_once_with(
            "test_lesson_123", target_agent="agent-antigravity-bridge",
        )

def test_run_academy_demo_partial_pass_rate_is_not_100(tmp_path, capsys):
    measurement = tmp_path / "partial.json"
    _write_measurement(measurement, pass_rate=0.5)
    teacher_p, director_p, steward_p = _mocks()
    with teacher_p as mock_teacher_cls, director_p as mock_director_cls, steward_p as mock_steward_cls:
        _wire(mock_teacher_cls, mock_director_cls, mock_steward_cls)
        res = run_academy_demo(reset=False, measurement_path=str(measurement))
        assert "100% PASS" not in capsys.readouterr().out
        assert res["exit_code"] != 0

def test_run_academy_demo_no_snapshot(tmp_path, capsys):
    measurement = tmp_path / "measured.json"
    _write_measurement(measurement)
    teacher_p, director_p, steward_p = _mocks()
    with teacher_p as mock_teacher_cls, director_p as mock_director_cls, steward_p as mock_steward_cls:
        _wire(mock_teacher_cls, mock_director_cls, mock_steward_cls)
        res = run_academy_demo(reset=True, measurement_path=str(measurement))
        assert "100% PASS" in capsys.readouterr().out
        assert res["status"] == "COMPLETED"
        assert res["context_version_before"] == 1
        assert res["context_version_after"] == 1

def test_main_literals_exit_nonzero(monkeypatch, capsys):
    import scripts.run_academy_demo as demo
    monkeypatch.setattr(sys, "argv", ["run_academy_demo.py"])
    teacher_p, director_p, steward_p = _mocks()
    with teacher_p as mock_teacher_cls, director_p as mock_director_cls, steward_p as mock_steward_cls:
        _wire(mock_teacher_cls, mock_director_cls, mock_steward_cls)
        with pytest.raises(SystemExit) as caught:
            demo.main()
    assert caught.value.code not in (0, None)
    assert "100% PASS" not in capsys.readouterr().out
