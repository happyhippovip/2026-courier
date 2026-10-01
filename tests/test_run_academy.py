import pytest
import os
import json
import datetime
from pathlib import Path
from unittest import mock

from scripts.run_academy import (
    AcademyTeacher,
    AcademyDirector,
    compute_novelty_hash,
    ALLOWED_LESSON_TYPES,
)

@pytest.fixture
def academy_env(tmp_path):
    repo_dir = tmp_path / "repo"
    memory_dir = tmp_path / "memory"
    repo_dir.mkdir()
    memory_dir.mkdir()
    
    events_dir = repo_dir / "events"
    events_dir.mkdir()
    states_dir = events_dir / "agent-states"
    states_dir.mkdir()
    academy_dir = events_dir / "academy"
    academy_dir.mkdir()
    (academy_dir / "lessons").mkdir()
    (academy_dir / "evaluations").mkdir()
    (academy_dir / "deliveries").mkdir()
    (academy_dir / "adoptions").mkdir()

    return repo_dir, memory_dir

def test_compute_novelty_hash():
    h1 = compute_novelty_hash(" Topic ", "TITLE ", " Summary ", " Source")
    h2 = compute_novelty_hash("topic", "title", "summary", "source")
    assert h1 == h2

def test_teacher_init(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    assert teacher.config["academy_enabled"] is True

def test_teacher_update_visual_state(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    state = teacher.update_visual_state(state="TESTING", current_topic="abc")
    assert state["state"] == "TESTING"
    assert state["current_topic"] == "abc"
    state_file = repo_dir / "events/agent-states/agent-academy-teacher.json"
    assert state_file.exists()

def test_propose_lesson_invalid_type(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    with pytest.raises(ValueError, match="Invalid lesson_type"):
        teacher.propose_lesson(
            topic="t", title="t", summary="s", source="s", lesson_type="INVALID_TYPE"
        )

@mock.patch("scripts.run_academy.LESSONS_DIR", new_callable=lambda: Path("."))
def test_propose_lesson_success(mock_lessons_dir, academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    # Patch LESSONS_DIR so it writes to the repo_dir
    lessons_dir = repo_dir / "events/academy/lessons"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons_dir)
    
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    
    # Mock curator
    teacher.curator = mock.MagicMock()
    teacher.curator.curate_idea.return_value = {"idea_id": "test-idea-123"}
    
    # Normal lesson
    lesson1 = teacher.propose_lesson(
        topic="t1", title="Title 1", summary="Sum 1", source="Src 1"
    )
    assert lesson1["status"] == "DISCOVERED"
    
    # Opportunity lesson
    lesson2 = teacher.propose_lesson(
        topic="t2", title="Title 2", summary="Sum 2", source="Src 2",
        lesson_type="OPPORTUNITY_CANDIDATE"
    )
    assert lesson2["status"] == "DISCOVERED"
    assert lesson2["idea_sync_id"] == "test-idea-123"
    
    # Duplicate lesson (same topic, title, sum, src)
    lesson3 = teacher.propose_lesson(
        topic="t1", title="Title 1", summary="Sum 1", source="Src 1"
    )
    assert lesson3["lesson_id"] == lesson1["lesson_id"]

def test_queue_or_deliver_lesson_missing(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    with pytest.raises(FileNotFoundError):
        teacher.queue_or_deliver_lesson("missing", "agent-1")

@mock.patch("scripts.run_academy.LESSONS_DIR")
@mock.patch("scripts.run_academy.DELIVERIES_DIR")
def test_queue_or_deliver_lesson(mock_deliveries_dir, mock_lessons_dir, academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons_dir = repo_dir / "events/academy/lessons"
    deliveries_dir = repo_dir / "events/academy/deliveries"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons_dir)
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries_dir)
    
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    teacher.steward = mock.MagicMock()
    teacher.steward.get_latest_snapshot.return_value = {"context_version": 5}
    
    lesson_file = lessons_dir / "lesson-1.json"
    lesson_file.write_text(json.dumps({
        "lesson_id": "lesson-1", "lesson_type": "PROCESS_IMPROVEMENT", "summary": "test", "topic": "test", "proposed_method": "test"
    }))
    
    # Target agent is running -> safe defer
    agent_state = repo_dir / "events/agent-states/target-agent.json"
    agent_state.write_text(json.dumps({"state": "RUNNING", "task": "task123"}))
    
    delivery1 = teacher.queue_or_deliver_lesson("lesson-1", "target-agent")
    assert delivery1["status"] == "PENDING_LESSON"
    
    # Target agent is idle -> direct delivery
    agent_state.write_text(json.dumps({"state": "IDLE"}))
    delivery2 = teacher.queue_or_deliver_lesson("lesson-1", "target-agent")
    assert delivery2["status"] == "DELIVERED_TO_AGENT"
    assert delivery2["context_version"] == 5

def test_director_init(academy_env):
    repo_dir, memory_dir = academy_env
    dir = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    assert dir.economics["schema_version"] == "2.0"

def test_director_check_attendance(academy_env):
    repo_dir, memory_dir = academy_env
    dir = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    assert not dir.check_attendance()
    
    (repo_dir / "events/agent-states/agent-academy-teacher.json").write_text("{}")
    assert dir.check_attendance()

@mock.patch("scripts.run_academy.LESSONS_DIR")
def test_director_review_lesson(mock_lessons_dir, academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons_dir = repo_dir / "events/academy/lessons"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons_dir)
    
    dir = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    
    # Missing lesson
    with pytest.raises(FileNotFoundError):
        dir.review_lesson("missing")
        
    # Bad evidence
    l1 = lessons_dir / "lesson-bad.json"
    l1.write_text(json.dumps({"evidence": "", "affected_agents": ["a"], "novelty_hash": "1"}))
    res1 = dir.review_lesson("lesson-bad")
    assert res1["status"] == "REJECTED"
    
    # Good evidence
    l2 = lessons_dir / "lesson-good.json"
    l2.write_text(json.dumps({"evidence": "good evidence", "affected_agents": ["a"], "novelty_hash": "1"}))
    res2 = dir.review_lesson("lesson-good")
    assert res2["status"] == "APPROVED_FOR_TEST"

@mock.patch("scripts.run_academy.LESSONS_DIR")
@mock.patch("scripts.run_academy.EVALS_DIR")
def test_director_evaluate_lesson(mock_evals_dir, mock_lessons_dir, academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons_dir = repo_dir / "events/academy/lessons"
    evals_dir = repo_dir / "events/academy/evaluations"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons_dir)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals_dir)
    
    dir = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    
    # Missing lesson
    with pytest.raises(FileNotFoundError):
        dir.evaluate_lesson("missing", {}, {})
        
    l1 = lessons_dir / "lesson-1.json"
    l1.write_text(json.dumps({"status": "APPROVED_FOR_TEST"}))
    
    # Evaluate Pass (no regression)
    res = dir.evaluate_lesson(
        "lesson-1",
        {"runtime_seconds": 10.0, "error_count": 1, "test_pass_rate": 0.9},
        {"runtime_seconds": 8.0, "error_count": 0, "test_pass_rate": 0.95}
    )
    assert res["verdict"] == "PASS"
    assert res["metrics"]["measured_minutes_saved"] > 0
    assert json.loads(l1.read_text())["status"] == "EVAL_PASS"
    
    # Evaluate Fail (regression)
    res2 = dir.evaluate_lesson(
        "lesson-1",
        {"runtime_seconds": 10.0, "error_count": 0, "test_pass_rate": 0.9},
        {"runtime_seconds": 8.0, "error_count": 1, "test_pass_rate": 0.9}
    )
    assert res2["verdict"] == "FAIL"
    assert json.loads(l1.read_text())["status"] == "EVAL_FAIL"

@mock.patch("scripts.run_academy.LESSONS_DIR")
@mock.patch("scripts.run_academy.EVALS_DIR")
@mock.patch("scripts.run_academy.ADOPTIONS_DIR")
def test_director_approve_adoption(mock_adoptions_dir, mock_evals_dir, mock_lessons_dir, academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons_dir = repo_dir / "events/academy/lessons"
    evals_dir = repo_dir / "events/academy/evaluations"
    adoptions_dir = repo_dir / "events/academy/adoptions"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons_dir)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals_dir)
    monkeypatch.setattr("scripts.run_academy.ADOPTIONS_DIR", adoptions_dir)
    
    dir = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    dir.steward = mock.MagicMock()
    
    # Missing lesson
    with pytest.raises(FileNotFoundError):
        dir.approve_adoption("missing")
        
    l1 = lessons_dir / "lesson-1.json"
    l1.write_text(json.dumps({"status": "EVAL_PASS"}))
    
    # Missing evaluation
    with pytest.raises(PermissionError):
        dir.approve_adoption("lesson-1")
        
    # Failed evaluation
    e1 = evals_dir / "eval-lesson-1.json"
    e1.write_text(json.dumps({"verdict": "FAIL"}))
    with pytest.raises(ValueError, match="Adoption blocked"):
        dir.approve_adoption("lesson-1")
        
    # Passed evaluation
    e1.write_text(json.dumps({"verdict": "PASS", "metrics": {"measured_minutes_saved": 5.0}}))
    adopt = dir.approve_adoption("lesson-1")
    assert adopt["lesson_id"] == "lesson-1"
    assert dir.economics["measured_minutes_saved"] == 5.0
    dir.steward.refresh_snapshot_after_event.assert_called_once()
    
@mock.patch("scripts.run_academy.DELIVERIES_DIR")
def test_director_record_worker_acknowledgement(mock_deliveries_dir, academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    deliveries_dir = repo_dir / "events/academy/deliveries"
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries_dir)
    
    dir = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    ack = dir.record_worker_acknowledgement("agent-1", "lesson-1", 1)
    assert ack["adoption_status"] == "ACKNOWLEDGED"


