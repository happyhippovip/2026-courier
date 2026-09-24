import json
import pytest
from pathlib import Path
from scripts.run_academy import AcademyTeacher, AcademyDirector, main


@pytest.fixture
def academy_env(tmp_path):
    repo_dir = tmp_path / "repo"
    memory_dir = tmp_path / "memory"
    repo_dir.mkdir(parents=True)
    memory_dir.mkdir(parents=True)

    # Initialize basic memory file if needed
    (memory_dir / "PROJECT_STATE.md").write_text("# Project State\nStatus: VERIFIED_CURRENT\n", encoding="utf-8")
    return repo_dir, memory_dir


def test_academy_initialization_isolation(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    assert teacher.lessons_dir.exists()
    assert teacher.deliveries_dir.exists()
    assert teacher.evals_dir.exists()
    assert teacher.adoptions_dir.exists()
    assert teacher.states_dir.exists()

    assert director.economics_file.exists()
    econ = json.loads(director.economics_file.read_text(encoding="utf-8"))
    assert econ["total_lessons_adopted"] == 0


def test_academy_teacher_propose_and_dedup(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)

    lesson1 = teacher.propose_lesson(
        topic="speed_optimization",
        title="Fast Cache Strategy",
        summary="Use in-memory LRU cache to reduce disk reads",
        source="Engineering docs",
        evidence="Observed 50% read reduction in local bench",
    )

    assert lesson1["status"] == "DISCOVERED"
    assert (teacher.lessons_dir / f"{lesson1['lesson_id']}.json").exists()

    # Propose duplicate lesson
    lesson2 = teacher.propose_lesson(
        topic="speed_optimization",
        title="Fast Cache Strategy",
        summary="Use in-memory LRU cache to reduce disk reads",
        source="Engineering docs",
        evidence="Observed 50% read reduction in local bench",
    )

    assert lesson2["lesson_id"] == lesson1["lesson_id"]
    # Teacher state file should indicate DEDUPED
    state_file = teacher.states_dir / "agent-academy-teacher.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["state"] == "DEDUPED"


def test_academy_teacher_deliver_and_defer(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)

    lesson = teacher.propose_lesson(
        topic="process",
        title="Safe Pipeline",
        summary="Always run sanity check first",
        source="Process handbook",
        evidence="Handled edge cases cleanly",
    )

    # 1. Idle agent receives immediate delivery
    idle_pkg = teacher.queue_or_deliver_lesson(
        lesson_id=lesson["lesson_id"],
        target_agent="worker-test-idle",
    )
    assert idle_pkg["status"] == "DELIVERED_TO_AGENT"
    assert (teacher.deliveries_dir / f"{idle_pkg['delivery_id']}.json").exists()

    # 2. Busy agent gets deferred delivery
    busy_state_file = teacher.states_dir / "worker-test-busy.json"
    busy_state_file.write_text(json.dumps({"state": "RUNNING", "task": "task-xyz"}), encoding="utf-8")

    defer_pkg = teacher.queue_or_deliver_lesson(
        lesson_id=lesson["lesson_id"],
        target_agent="worker-test-busy",
    )
    assert defer_pkg["status"] == "PENDING_LESSON"
    assert defer_pkg["defer_until_task_completed"] == "task-xyz"

    # 3. Busy agent with high risk security update gets urgent delivery
    sec_lesson = teacher.propose_lesson(
        topic="security",
        title="Critical Patch",
        summary="Patch buffer vulnerability immediately",
        source="Security advisory",
        evidence="CVE-2026-9999 validation",
        lesson_type="SECURITY_UPDATE",
        risk="HIGH",
    )
    urgent_pkg = teacher.queue_or_deliver_lesson(
        lesson_id=sec_lesson["lesson_id"],
        target_agent="worker-test-busy",
    )
    assert urgent_pkg["status"] == "URGENT_LESSON_REVIEW"


def test_academy_director_review_and_eval_gate(academy_env):
    repo_dir, memory_dir = academy_env
    teacher = AcademyTeacher(repo_dir=repo_dir, memory_dir=memory_dir)
    director = AcademyDirector(repo_dir=repo_dir, memory_dir=memory_dir)

    # Insufficient evidence rejected
    lesson_weak = teacher.propose_lesson(
        topic="speculation",
        title="Maybe Faster",
        summary="Some idea",
        source="Chat rumor",
        evidence="none",
    )
    reviewed_weak = director.review_lesson(lesson_weak["lesson_id"])
    assert reviewed_weak["status"] == "REJECTED"

    # Valid lesson approved for test
    lesson_good = teacher.propose_lesson(
        topic="indexing",
        title="B-Tree Indexing",
        summary="Index lookup column to accelerate scans",
        source="DB docs",
        evidence="Benchmark shows 4x faster lookup times",
    )
    reviewed_good = director.review_lesson(lesson_good["lesson_id"])
    assert reviewed_good["status"] == "APPROVED_FOR_TEST"

    # Adoption without evaluation fails
    with pytest.raises(PermissionError):
        director.approve_adoption(lesson_good["lesson_id"])

    # Failed evaluation prevents adoption
    director.evaluate_lesson(
        lesson_id=lesson_good["lesson_id"],
        baseline_metrics={"runtime_seconds": 10.0, "error_count": 0, "test_pass_rate": 1.0},
        candidate_metrics={"runtime_seconds": 12.0, "error_count": 1, "test_pass_rate": 0.8},
    )
    with pytest.raises(ValueError):
        director.approve_adoption(lesson_good["lesson_id"])

    # Passing evaluation allows adoption
    director.evaluate_lesson(
        lesson_id=lesson_good["lesson_id"],
        baseline_metrics={"runtime_seconds": 10.0, "error_count": 0, "test_pass_rate": 1.0},
        candidate_metrics={"runtime_seconds": 4.0, "error_count": 0, "test_pass_rate": 1.0},
    )
    adoption = director.approve_adoption(lesson_good["lesson_id"])
    assert adoption["adoption_id"] == f"adopt-{lesson_good['lesson_id']}"
    assert (director.adoptions_dir / f"adopt-{lesson_good['lesson_id']}.json").exists()

    # Economics updated
    assert director.economics["total_lessons_adopted"] == 1
    assert director.economics["measured_minutes_saved"] > 0

    # Worker acknowledgement
    ack = director.record_worker_acknowledgement(
        worker_agent_id="worker-agent-1",
        lesson_id=lesson_good["lesson_id"],
        context_version=1,
    )
    assert ack["adoption_status"] == "ACKNOWLEDGED"
    assert (director.deliveries_dir / f"ack-worker-agent-1-{lesson_good['lesson_id']}.json").exists()


def test_academy_cli(academy_env, capsys):
    repo_dir, memory_dir = academy_env

    # Run demo cycle
    code = main([
        "--repo-dir", str(repo_dir),
        "--memory-dir", str(memory_dir),
        "--demo",
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["lessons_count"] >= 1
    assert data["total_lessons_adopted"] >= 1
    assert "demo_lesson_id" in data
