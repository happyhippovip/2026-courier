import pytest
import sys
from unittest.mock import patch, MagicMock
from scripts.run_academy_demo import run_academy_demo

def test_run_academy_demo_success():
    with patch("scripts.run_academy_demo.AcademyTeacher") as mock_teacher_cls, \
         patch("scripts.run_academy_demo.AcademyDirector") as mock_director_cls, \
         patch("scripts.run_academy_demo.UpdateSteward") as mock_steward_cls:
         
        mock_teacher = mock_teacher_cls.return_value
        mock_director = mock_director_cls.return_value
        mock_steward = mock_steward_cls.return_value
        
        mock_teacher.propose_lesson.return_value = {
            "lesson_id": "test_lesson_123",
            "novelty_hash": "deadbeef12345678"
        }
        
        mock_director.review_lesson.return_value = {
            "status": "APPROVED_FOR_TEST"
        }
        
        mock_director.evaluate_lesson.return_value = {
            "verdict": "PASS",
            "metrics": {"measured_minutes_saved": 5.0}
        }
        
        mock_director.approve_adoption.return_value = {
            "adoption_id": "adopt_123"
        }
        
        # steward get_latest_snapshot returns dict or None. It's called twice
        mock_steward.get_latest_snapshot.side_effect = [
            {"context_version": 42},
            {"context_version": 43, "snapshot_hash": "abcdef123"}
        ]
        
        mock_teacher.queue_or_deliver_lesson.return_value = {
            "delivery_id": "del_123",
            "status": "QUEUED"
        }
        
        mock_director.record_worker_acknowledgement.return_value = {
            "adoption_status": "ACKNOWLEDGED"
        }
        
        res = run_academy_demo(reset=False)
        
        assert res["status"] == "COMPLETED"
        assert res["lesson_id"] == "test_lesson_123"
        assert res["eval_verdict"] == "PASS"
        assert res["context_version_before"] == 42
        assert res["context_version_after"] == 43
        assert res["measured_minutes_saved"] == 5.0
        
        mock_director.check_attendance.assert_called_once()
        mock_teacher.propose_lesson.assert_called_once()
        mock_director.review_lesson.assert_called_once_with("test_lesson_123")
        mock_director.evaluate_lesson.assert_called_once()
        mock_director.approve_adoption.assert_called_once_with("test_lesson_123")
        assert mock_steward.get_latest_snapshot.call_count == 2
        mock_teacher.queue_or_deliver_lesson.assert_called_once_with("test_lesson_123", target_agent="agent-antigravity-bridge")
        mock_director.record_worker_acknowledgement.assert_called_once_with(
            worker_agent_id="agent-antigravity-bridge",
            lesson_id="test_lesson_123",
            context_version=43
        )

def test_run_academy_demo_no_snapshot():
    with patch("scripts.run_academy_demo.AcademyTeacher") as mock_teacher_cls, \
         patch("scripts.run_academy_demo.AcademyDirector") as mock_director_cls, \
         patch("scripts.run_academy_demo.UpdateSteward") as mock_steward_cls:
         
        mock_teacher = mock_teacher_cls.return_value
        mock_director = mock_director_cls.return_value
        mock_steward = mock_steward_cls.return_value
        
        mock_teacher.propose_lesson.return_value = {
            "lesson_id": "test_lesson_123",
            "novelty_hash": "deadbeef12345678"
        }
        mock_director.review_lesson.return_value = {"status": "APPROVED_FOR_TEST"}
        mock_director.evaluate_lesson.return_value = {"verdict": "PASS", "metrics": {"measured_minutes_saved": 5.0}}
        mock_director.approve_adoption.return_value = {"adoption_id": "adopt_123"}
        
        # get_latest_snapshot returns an empty dict to avoid AttributeError on snap_after.get
        mock_steward.get_latest_snapshot.return_value = {}
        
        mock_teacher.queue_or_deliver_lesson.return_value = {"delivery_id": "del_123", "status": "QUEUED"}
        mock_director.record_worker_acknowledgement.return_value = {"adoption_status": "ACKNOWLEDGED"}
        
        res = run_academy_demo(reset=True)
        
        assert res["status"] == "COMPLETED"
        assert res["context_version_before"] == 1
        assert res["context_version_after"] == 1
