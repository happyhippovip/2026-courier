import pytest
from scripts.useful_work_selection_engine import UsefulWorkSelectionEngine, compute_canonical_work_fingerprint, WorkReadinessState

def test_planner_dedup(tmp_path):
    engine = UsefulWorkSelectionEngine(repo_dir=tmp_path)
    engine.completed_fps_file = tmp_path / "completed.json"
    
    # 1. Same opportunity discovered multiple times
    q = [
        {"objective": "Fix Bug", "scope": ["a.py", "b.py"], "task_type": "bugfix"},
        {"objective": "fix bug", "scope": ["b.py", "a.py"], "task_type": "BUGFIX"},
    ]
    # They should have the exact same fingerprint
    fp1 = compute_canonical_work_fingerprint(q[0]["objective"], q[0]["scope"], q[0]["task_type"])
    fp2 = compute_canonical_work_fingerprint(q[1]["objective"], q[1]["scope"], q[1]["task_type"])
    assert fp1 == fp2
    
    # 2. Mark as completed
    engine.record_completed_fingerprint(fp1)
    
    # 3. Simulate restart
    engine2 = UsefulWorkSelectionEngine(repo_dir=tmp_path)
    engine2.completed_fps_file = tmp_path / "completed.json"
    engine2._load_completed_fingerprints()
    
    # 4. Prove OLD IDENTICAL WORK -> suppressed
    state, reason = engine2.classify_opportunity(q[0])
    assert state == WorkReadinessState.COMPLETED
    assert "ALREADY_COMPLETED" in reason
    
    # 5. Prove GENUINELY CHANGED WORK -> eligible
    q_changed = {"objective": "Fix Bug", "scope": ["a.py", "c.py"], "task_type": "bugfix"}
    state_changed, _ = engine2.classify_opportunity(q_changed)
    assert state_changed != WorkReadinessState.COMPLETED

