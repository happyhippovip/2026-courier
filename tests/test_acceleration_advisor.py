from scripts.acceleration_advisor import (
    analyze_capacity_and_recommend,
    RecommendationType,
    Severity
)

def test_no_blocked_tasks():
    rec = analyze_capacity_and_recommend([], [], [])
    assert rec.severity == Severity.GREEN
    assert rec.type == RecommendationType.NONE

def test_missing_capability():
    rec = analyze_capacity_and_recommend(
        active_tasks=[],
        blocked_tasks=[{"mission_id": "WK-42", "capability_required": "windows_desktop_worker"}],
        available_workers=[{"capabilities": ["github_repo_worker"], "busy": False}]
    )
    assert rec.severity == Severity.RED_ACCELERATION_OPPORTUNITY
    assert rec.type == RecommendationType.ADD_MODEL_CAPACITY
    assert rec.proposed_capability == "windows_desktop_worker"
    assert rec.human_approval_required is True

def test_all_workers_busy():
    rec = analyze_capacity_and_recommend(
        active_tasks=["WK-40"],
        blocked_tasks=[{"mission_id": "WK-42", "capability_required": "github_repo_worker"}],
        available_workers=[{"capabilities": ["github_repo_worker"], "busy": True}]
    )
    assert rec.severity == Severity.RED_ACCELERATION_OPPORTUNITY
    assert rec.type == RecommendationType.ADD_COMPUTE
    assert rec.human_approval_required is True

def test_idle_qualified_worker_exists():
    rec = analyze_capacity_and_recommend(
        active_tasks=[],
        blocked_tasks=[{"mission_id": "WK-42", "capability_required": "github_repo_worker"}],
        available_workers=[{"capabilities": ["github_repo_worker"], "busy": False}]
    )
    assert rec.severity == Severity.YELLOW
    assert rec.type == RecommendationType.USE_EXISTING_AGENT
    assert rec.human_approval_required is False
