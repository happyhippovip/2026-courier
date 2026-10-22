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

def test_lessons_dir_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    outside = repo_dir.parent / "outside-lessons"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = repo_dir.parent / "linked-lessons"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = repo_dir.parent / "lessons-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = repo_dir.parent / "lessons-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    teacher.curator = mock.MagicMock()

    def run(folder):
        monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", folder)
        try:
            teacher.propose_lesson(
                topic="secret-topic",
                title="SECRET-LESSON",
                summary="s",
                source="s",
            )
        except ValueError as exc:
            return str(exc)
        return "wrote"

    err_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    err_parent = run(linked_parent / "lessons")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = repo_dir / "events" / "academy" / "plain-lessons"
    err_plain = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []
    assert (
        err_link,
        leaked,
        err_parent,
        parent_names,
        err_plain,
        any(name.startswith("lesson-") and name.endswith(".json") for name in plain_names),
    ) == (
        "refusing to follow a symlink",
        ["keep.txt"],
        "refusing to follow a symlink",
        ["keep.txt"],
        "wrote",
        True,
    )


def test_delivery_does_not_follow_a_lesson_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    deliveries = repo_dir / "events" / "academy" / "deliveries"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries)
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    teacher.steward = mock.MagicMock()
    teacher.steward.get_latest_snapshot.return_value = {"context_version": 1}
    outside = repo_dir.parent / "outside-delivery-lesson.json"
    outside.write_text(json.dumps({
        "summary": "SECRET-SUMMARY",
        "topic": "secret-topic",
        "proposed_method": "keep",
        "lesson_type": "PROCESS_IMPROVEMENT",
        "risk": "LOW",
    }), encoding="utf-8")
    (lessons / "lesson-secret.json").symlink_to(outside)
    try:
        package = teacher.queue_or_deliver_lesson("lesson-secret", "target-agent")
        err = None
        summary = package.get("relevant_summary")
    except ValueError as exc:
        err = str(exc)
        summary = None
    assert (err, summary, "SECRET-SUMMARY" in outside.read_text(encoding="utf-8")) == (
        "refusing to follow a symlink",
        None,
        True,
    )


def test_bool_delivery_version_is_not_a_number(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    deliveries = repo_dir / "events" / "academy" / "deliveries"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries)
    (lessons / "lesson-1.json").write_text(json.dumps({
        "summary": "plain",
        "topic": "plain-topic",
        "proposed_method": "keep",
        "lesson_type": "PROCESS_IMPROVEMENT",
        "risk": "LOW",
    }), encoding="utf-8")
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    teacher.steward = mock.MagicMock()

    def run(version):
        teacher.steward.get_latest_snapshot.return_value = {"context_version": version}
        try:
            package = teacher.queue_or_deliver_lesson("lesson-1", "target-agent")
        except ValueError as exc:
            return ("err", str(exc))
        return ("ok", package.get("context_version"))

    assert (run(True), run(False), run(4)) == (
        ("err", "Bool is not a number."),
        ("err", "Bool is not a number."),
        ("ok", 4),
    )


def test_target_agent_does_not_escape_the_state_dir(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    deliveries = repo_dir / "events" / "academy" / "deliveries"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries)
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    (lessons / "lesson-1.json").write_text(json.dumps({
        "summary": "plain",
        "topic": "plain-topic",
        "proposed_method": "keep",
        "lesson_type": "PROCESS_IMPROVEMENT",
        "risk": "LOW",
    }), encoding="utf-8")
    outside = repo_dir.parent / "outside-agent.json"
    outside.write_text(json.dumps({"state": "RUNNING", "task": "SECRET-TASK"}), encoding="utf-8")
    try:
        package = teacher.queue_or_deliver_lesson("lesson-1", "../../../outside-agent")
        err = None
        leaked = package.get("defer_until_task_completed")
    except ValueError as exc:
        err = str(exc)
        leaked = None
    assert (err, leaked, "SECRET-TASK" in outside.read_text(encoding="utf-8")) == (
        "refusing an unsafe target agent",
        None,
        True,
    )


def test_deliveries_dir_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    (lessons / "lesson-1.json").write_text(json.dumps({
        "summary": "plain",
        "topic": "plain-topic",
        "proposed_method": "keep",
        "lesson_type": "PROCESS_IMPROVEMENT",
        "risk": "LOW",
    }), encoding="utf-8")
    (repo_dir / "events" / "agent-states" / "target-agent.json").write_text(
        json.dumps({"state": "RUNNING", "task": "task-1"}),
        encoding="utf-8",
    )
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)

    outside = repo_dir.parent / "outside-deliveries"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = repo_dir.parent / "linked-deliveries"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = repo_dir.parent / "deliveries-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = repo_dir.parent / "deliveries-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(folder):
        monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", folder)
        try:
            teacher.queue_or_deliver_lesson("lesson-1", "target-agent")
        except ValueError as exc:
            return str(exc)
        return "wrote"

    err_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    err_parent = run(linked_parent / "deliveries")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = repo_dir / "events" / "academy" / "plain-deliveries"
    err_plain = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []
    assert (
        err_link,
        leaked,
        err_parent,
        parent_names,
        err_plain,
        any(name.startswith("deliv-") and name.endswith(".json") for name in plain_names),
    ) == (
        "refusing to follow a symlink",
        ["keep.txt"],
        "refusing to follow a symlink",
        ["keep.txt"],
        "wrote",
        True,
    )


def test_economics_file_does_not_follow_a_symlink(academy_env):
    repo_dir, memory_dir = academy_env
    outside = repo_dir.parent / "outside-econ.json"
    outside.write_text(json.dumps({
        "secret": "SECRET-ECON",
        "measured_minutes_saved": 99,
    }), encoding="utf-8")
    (repo_dir / "events" / "academy" / "economics.json").symlink_to(outside)

    def start(repo):
        try:
            director = AcademyDirector(repo_dir=repo, memory_dir=memory_dir)
        except ValueError as exc:
            return str(exc), None
        return "loaded", director.economics.get("secret")

    err_file, secret_file = start(repo_dir)

    parent_outside = repo_dir.parent / "econ-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "economics.json").write_text(json.dumps({
        "secret": "SECRET-PARENT",
        "measured_minutes_saved": 7,
    }), encoding="utf-8")
    repo_parent = repo_dir.parent / "repo-econ-parent"
    (repo_parent / "events" / "agent-states").mkdir(parents=True)
    (repo_parent / "events" / "academy").symlink_to(parent_outside, target_is_directory=True)
    err_parent, secret_parent = start(repo_parent)

    repo_plain = repo_dir.parent / "repo-econ-plain"
    (repo_plain / "events" / "agent-states").mkdir(parents=True)
    (repo_plain / "events" / "academy").mkdir(parents=True)
    err_plain, secret_plain = start(repo_plain)
    plain_file = repo_plain / "events" / "academy" / "economics.json"
    assert (
        err_file,
        secret_file,
        "SECRET-ECON" in outside.read_text(encoding="utf-8"),
        err_parent,
        secret_parent,
        "SECRET-PARENT" in (parent_outside / "economics.json").read_text(encoding="utf-8"),
        err_plain,
        secret_plain,
        plain_file.exists() and not plain_file.is_symlink(),
    ) == (
        "refusing to follow a symlink",
        None,
        True,
        "refusing to follow a symlink",
        None,
        True,
        "loaded",
        None,
        True,
    )


def test_economics_save_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    adoptions = repo_dir / "events" / "academy" / "adoptions"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    monkeypatch.setattr("scripts.run_academy.ADOPTIONS_DIR", adoptions)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    director.steward = mock.MagicMock()
    (lessons / "lesson-1.json").write_text(json.dumps({
        "title": "t",
        "topic": "t",
        "affected_agents": ["a"],
    }), encoding="utf-8")
    (evals / "eval-lesson-1.json").write_text(json.dumps({
        "verdict": "PASS",
        "evaluation_id": "e1",
        "metrics": {"measured_minutes_saved": 5},
    }), encoding="utf-8")
    outside = repo_dir.parent / "outside-econ-save.json"
    outside.write_text(json.dumps({"marker": "SECRET-ECON"}), encoding="utf-8")
    econ = repo_dir / "events" / "academy" / "economics.json"
    econ.unlink()
    econ.symlink_to(outside)
    try:
        director.approve_adoption("lesson-1")
        err = None
    except ValueError as exc:
        err = str(exc)
    body = outside.read_text(encoding="utf-8")
    assert (err, "SECRET-ECON" in body) == ("refusing to follow a symlink", True)


def test_lesson_id_does_not_escape_the_lessons_dir(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    deliveries = repo_dir / "events" / "academy" / "deliveries"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries)
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    teacher.steward = mock.MagicMock()
    teacher.steward.get_latest_snapshot.return_value = {"context_version": 1}
    outside = repo_dir.parent / "outside-lesson.json"
    outside.write_text(json.dumps({
        "summary": "SECRET-SUMMARY",
        "topic": "secret-topic",
        "proposed_method": "keep",
        "lesson_type": "PROCESS_IMPROVEMENT",
        "risk": "LOW",
    }), encoding="utf-8")
    try:
        package = teacher.queue_or_deliver_lesson("../../../../outside-lesson", "target-agent")
        err = None
        summary = package.get("relevant_summary")
    except ValueError as exc:
        err = str(exc)
        summary = None
    assert (err, summary, "SECRET-SUMMARY" in outside.read_text(encoding="utf-8")) == (
        "refusing an unsafe lesson id",
        None,
        True,
    )


def test_review_lesson_id_does_not_escape(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    outside = repo_dir.parent / "outside-review.json"
    outside.write_text(json.dumps({"summary": "SECRET-SUMMARY"}), encoding="utf-8")
    try:
        lesson = director.review_lesson("../../../../outside-review")
        err = None
        status = lesson.get("status")
    except ValueError as exc:
        err = str(exc)
        status = None
    body = outside.read_text(encoding="utf-8")
    assert (err, status, "SECRET-SUMMARY" in body, "REJECTED" in body) == (
        "refusing an unsafe lesson id",
        None,
        True,
        False,
    )


def test_evaluate_lesson_id_does_not_escape(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    outside = repo_dir.parent / "outside-eval-id.json"
    outside.write_text(json.dumps({"summary": "SECRET-SUMMARY"}), encoding="utf-8")
    try:
        record = director.evaluate_lesson("../../../../outside-eval-id", {}, {})
        err = None
        verdict = record.get("verdict")
    except ValueError as exc:
        err = str(exc)
        verdict = None
    body = outside.read_text(encoding="utf-8")
    assert (err, verdict, "SECRET-SUMMARY" in body, "EVAL_PASS" in body) == (
        "refusing an unsafe lesson id",
        None,
        True,
        False,
    )


def test_evals_dir_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    (lessons / "lesson-1.json").write_text(json.dumps({"summary": "plain"}), encoding="utf-8")
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    outside = repo_dir.parent / "outside-evals"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = repo_dir.parent / "linked-evals"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = repo_dir.parent / "evals-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = repo_dir.parent / "evals-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(folder):
        monkeypatch.setattr("scripts.run_academy.EVALS_DIR", folder)
        try:
            director.evaluate_lesson("lesson-1", {}, {})
        except ValueError as exc:
            return str(exc)
        return "evaluated"

    err_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    err_parent = run(linked_parent / "evaluations")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = repo_dir / "events" / "academy" / "plain-evals"
    err_plain = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []
    assert (
        err_link,
        leaked,
        err_parent,
        parent_names,
        err_plain,
        any(name.startswith("eval-") and name.endswith(".json") for name in plain_names),
    ) == (
        "refusing to follow a symlink",
        ["keep.txt"],
        "refusing to follow a symlink",
        ["keep.txt"],
        "evaluated",
        True,
    )


def test_adopt_lesson_id_does_not_escape(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    adoptions = repo_dir / "events" / "academy" / "adoptions"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    monkeypatch.setattr("scripts.run_academy.ADOPTIONS_DIR", adoptions)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    director.steward = mock.MagicMock()
    outside = repo_dir.parent / "outside-adopt.json"
    outside.write_text(json.dumps({
        "summary": "SECRET-SUMMARY",
        "title": "secret-title",
        "topic": "secret-topic",
    }), encoding="utf-8")
    lesson_id = "../../../../outside-adopt"
    eval_file = evals / f"eval-{lesson_id}.json"
    eval_file.parent.mkdir(parents=True, exist_ok=True)
    eval_file.write_text(json.dumps({
        "verdict": "PASS",
        "evaluation_id": "eval-secret",
    }), encoding="utf-8")
    try:
        record = director.approve_adoption(lesson_id)
        err = None
        seen = record.get("lesson_id")
    except ValueError as exc:
        err = str(exc)
        seen = None
    body = outside.read_text(encoding="utf-8")
    assert (err, seen, "SECRET-SUMMARY" in body, "ADOPTED" in body) == (
        "refusing an unsafe lesson id",
        None,
        True,
        False,
    )


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

def test_review_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    outside = repo_dir.parent / "outside-lesson.json"
    outside.write_text(json.dumps({
        "evidence": "SECRET-LESSON-BODY",
        "affected_agents": ["a"],
        "novelty_hash": "1",
        "status": "DISCOVERED",
    }), encoding="utf-8")
    (lessons / "lesson-secret.json").symlink_to(outside)

    outside_dir = repo_dir.parent / "outside-review-lessons"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (outside_dir / "lesson-dir.json").write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    linked_dir = repo_dir.parent / "linked-review-lessons"
    linked_dir.symlink_to(outside_dir, target_is_directory=True)

    def run(folder, lesson_id):
        monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", folder)
        try:
            director.review_lesson(lesson_id)
        except ValueError as exc:
            return str(exc)
        return "reviewed"

    err_file = run(lessons, "lesson-secret")
    file_body = outside.read_text(encoding="utf-8")
    err_dir = run(linked_dir, "lesson-dir")
    dir_body = (outside_dir / "lesson-dir.json").read_text(encoding="utf-8")
    assert (err_file, "APPROVED_FOR_TEST" in file_body, err_dir, "APPROVED_FOR_TEST" in dir_body) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
    )


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

def test_evaluate_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    payload = json.dumps({
        "evidence": "SECRET-LESSON-BODY",
        "affected_agents": ["a"],
        "novelty_hash": "1",
        "status": "APPROVED_FOR_TEST",
    })
    outside = repo_dir.parent / "outside-eval-lesson.json"
    outside.write_text(payload, encoding="utf-8")
    (lessons / "lesson-secret.json").symlink_to(outside)

    outside_dir = repo_dir.parent / "outside-eval-lessons"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (outside_dir / "lesson-dir.json").write_text(payload, encoding="utf-8")
    linked_dir = repo_dir.parent / "linked-eval-lessons"
    linked_dir.symlink_to(outside_dir, target_is_directory=True)

    def run(folder, lesson_id):
        monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", folder)
        try:
            director.evaluate_lesson(lesson_id, {}, {})
        except ValueError as exc:
            return str(exc)
        return "evaluated"

    err_file = run(lessons, "lesson-secret")
    file_body = outside.read_text(encoding="utf-8")
    err_dir = run(linked_dir, "lesson-dir")
    dir_body = (outside_dir / "lesson-dir.json").read_text(encoding="utf-8")
    assert (err_file, "EVAL_PASS" in file_body, err_dir, "EVAL_PASS" in dir_body) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
    )


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

def test_bool_eval_metric_is_not_a_number(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    (lessons / "lesson-1.json").write_text(json.dumps({"status": "APPROVED_FOR_TEST"}), encoding="utf-8")
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    def run(baseline, candidate):
        try:
            result = director.evaluate_lesson("lesson-1", baseline, candidate)
        except ValueError as exc:
            return ("err", str(exc))
        return ("ok", result["verdict"], result["metrics"]["runtime_seconds_delta"], result["metrics"]["error_delta"])

    numbers = {"runtime_seconds": 10, "error_count": 0, "test_pass_rate": 1}
    assert (
        run({"runtime_seconds": True, "error_count": 0, "test_pass_rate": 1}, numbers),
        run({"runtime_seconds": 10, "error_count": True, "test_pass_rate": 1}, numbers),
        run(numbers, numbers),
    ) == (
        ("err", "Bool is not a number."),
        ("err", "Bool is not a number."),
        ("ok", "PASS", 0, 0),
    )


def test_bool_minutes_saved_is_not_a_number(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    adoptions = repo_dir / "events" / "academy" / "adoptions"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    monkeypatch.setattr("scripts.run_academy.ADOPTIONS_DIR", adoptions)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    director.steward = mock.MagicMock()

    def run(lesson_id, minutes):
        (lessons / f"{lesson_id}.json").write_text(json.dumps({
            "title": "t",
            "topic": "t",
            "affected_agents": ["a"],
        }), encoding="utf-8")
        (evals / f"eval-{lesson_id}.json").write_text(json.dumps({
            "verdict": "PASS",
            "evaluation_id": f"e-{lesson_id}",
            "metrics": {"measured_minutes_saved": minutes},
        }), encoding="utf-8")
        try:
            director.approve_adoption(lesson_id)
        except ValueError as exc:
            return ("err", str(exc), director.economics.get("measured_minutes_saved"))
        return ("ok", director.economics.get("measured_minutes_saved"))

    assert (
        run("lesson-true", True),
        run("lesson-false", False),
        run("lesson-int", 5),
    ) == (
        ("err", "Bool is not a number.", 0.0),
        ("err", "Bool is not a number.", 0.0),
        ("ok", 5.0),
    )


def test_adoptions_dir_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    (lessons / "lesson-1.json").write_text(json.dumps({
        "title": "t",
        "topic": "t",
        "affected_agents": ["a"],
    }), encoding="utf-8")
    (evals / "eval-lesson-1.json").write_text(json.dumps({
        "verdict": "PASS",
        "evaluation_id": "e1",
        "metrics": {"measured_minutes_saved": 1},
    }), encoding="utf-8")
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    director.steward = mock.MagicMock()

    outside = repo_dir.parent / "outside-adoptions"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = repo_dir.parent / "linked-adoptions"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = repo_dir.parent / "adoptions-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = repo_dir.parent / "adoptions-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(folder):
        monkeypatch.setattr("scripts.run_academy.ADOPTIONS_DIR", folder)
        (lessons / "lesson-1.json").write_text(json.dumps({
            "title": "t",
            "topic": "t",
            "affected_agents": ["a"],
        }), encoding="utf-8")
        try:
            director.approve_adoption("lesson-1")
        except ValueError as exc:
            return str(exc)
        return "adopted"

    err_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    err_parent = run(linked_parent / "adoptions")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = repo_dir / "events" / "academy" / "plain-adoptions"
    err_plain = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []
    assert (
        err_link,
        leaked,
        err_parent,
        parent_names,
        err_plain,
        any(name.startswith("adopt-") and name.endswith(".json") for name in plain_names),
    ) == (
        "refusing to follow a symlink",
        ["keep.txt"],
        "refusing to follow a symlink",
        ["keep.txt"],
        "adopted",
        True,
    )


def test_adopt_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    lessons = repo_dir / "events" / "academy" / "lessons"
    evals = repo_dir / "events" / "academy" / "evaluations"
    adoptions = repo_dir / "events" / "academy" / "adoptions"
    monkeypatch.setattr("scripts.run_academy.LESSONS_DIR", lessons)
    monkeypatch.setattr("scripts.run_academy.EVALS_DIR", evals)
    monkeypatch.setattr("scripts.run_academy.ADOPTIONS_DIR", adoptions)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    outside_lesson = repo_dir.parent / "outside-adopt-lesson.json"
    outside_lesson.write_text(json.dumps({
        "status": "EVAL_PASS",
        "title": "SECRET-LESSON",
        "topic": "t",
        "affected_agents": ["a"],
    }), encoding="utf-8")
    (lessons / "lesson-secret.json").symlink_to(outside_lesson)
    (evals / "eval-lesson-secret.json").write_text(
        json.dumps({"verdict": "PASS", "evaluation_id": "e-secret"}),
        encoding="utf-8",
    )

    (lessons / "lesson-plain.json").write_text(json.dumps({
        "status": "EVAL_PASS",
        "title": "plain",
        "topic": "t",
        "affected_agents": ["a"],
    }), encoding="utf-8")
    outside_eval = repo_dir.parent / "outside-eval.json"
    outside_eval.write_text(
        json.dumps({"verdict": "PASS", "evaluation_id": "SECRET-EVAL"}),
        encoding="utf-8",
    )
    (evals / "eval-lesson-plain.json").symlink_to(outside_eval)

    def run(lesson_id):
        try:
            director.approve_adoption(lesson_id)
        except ValueError as exc:
            return str(exc)
        return "adopted"

    err_lesson = run("lesson-secret")
    lesson_body = outside_lesson.read_text(encoding="utf-8")
    err_eval = run("lesson-plain")
    plain_body = (lessons / "lesson-plain.json").read_text(encoding="utf-8")
    assert (
        err_lesson,
        "ADOPTED" in lesson_body,
        err_eval,
        "ADOPTED" in plain_body,
        "SECRET-EVAL" in plain_body,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        False,
    )


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
    
def test_bool_context_version_is_not_a_number(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    deliveries = repo_dir / "events" / "academy" / "deliveries"
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    def run(version):
        try:
            ack = director.record_worker_acknowledgement("agent-1", "lesson-1", version)
        except ValueError as exc:
            return ("err", str(exc))
        return ("ok", ack["lesson_version_seen"])

    assert (run(True), run(False), run(2)) == (
        ("err", "Bool is not a number."),
        ("err", "Bool is not a number."),
        ("ok", 2),
    )


def test_ack_dir_does_not_follow_a_symlink(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    outside = repo_dir.parent / "outside-ack-dir"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = repo_dir.parent / "linked-ack-dir"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = repo_dir.parent / "ack-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = repo_dir.parent / "ack-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(folder):
        monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", folder)
        try:
            director.record_worker_acknowledgement("agent-1", "lesson-1", 1)
        except ValueError as exc:
            return str(exc)
        return "wrote"

    err_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    err_parent = run(linked_parent / "deliveries")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = repo_dir / "events" / "academy" / "plain-ack"
    err_plain = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []
    assert (
        err_link,
        leaked,
        err_parent,
        parent_names,
        err_plain,
        any(name.startswith("ack-") and name.endswith(".json") for name in plain_names),
    ) == (
        "refusing to follow a symlink",
        ["keep.txt"],
        "refusing to follow a symlink",
        ["keep.txt"],
        "wrote",
        True,
    )


def test_ack_ids_do_not_escape_the_deliveries_dir(academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    deliveries = repo_dir / "events" / "academy" / "deliveries"
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    def run(worker, lesson):
        try:
            director.record_worker_acknowledgement(worker, lesson, 1)
        except ValueError as exc:
            return str(exc)
        return "wrote"

    err_worker = run("../../../../../outside-worker", "lesson-1")
    worker_file = repo_dir / "outside-worker-lesson-1.json"
    worker_body = worker_file.read_text(encoding="utf-8") if worker_file.exists() else ""
    err_lesson = run("worker-1", "../../../../../outside-ack")
    lesson_file = repo_dir / "outside-ack.json"
    lesson_body = lesson_file.read_text(encoding="utf-8") if lesson_file.exists() else ""
    assert (
        err_worker,
        "ACKNOWLEDGED" in worker_body,
        err_lesson,
        "ACKNOWLEDGED" in lesson_body,
    ) == (
        "refusing an unsafe worker id",
        False,
        "refusing an unsafe lesson id",
        False,
    )


@mock.patch("scripts.run_academy.DELIVERIES_DIR")
def test_director_record_worker_acknowledgement(mock_deliveries_dir, academy_env, monkeypatch):
    repo_dir, memory_dir = academy_env
    deliveries_dir = repo_dir / "events/academy/deliveries"
    monkeypatch.setattr("scripts.run_academy.DELIVERIES_DIR", deliveries_dir)
    
    dir = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)
    ack = dir.record_worker_acknowledgement("agent-1", "lesson-1", 1)
    assert ack["adoption_status"] == "ACKNOWLEDGED"


