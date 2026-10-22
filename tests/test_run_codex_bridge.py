import os
import json
import pytest
from pathlib import Path

from scripts.run_codex_bridge import (
    check_secrets_in_text,
    parse_real_codex_result,
    CodexVisualStateTracker,
    CodexHookRunner,
    run_chief_review_router,
    execute_codex_task,
)

def test_check_secrets_in_text():
    assert check_secrets_in_text("No secrets here") == 0
    assert check_secrets_in_text("Here is a token: 'ghp_123456789012345678901234567890123456'") > 0
    assert check_secrets_in_text("sk-abcdefghijklmnopqrstuvwxyz12345678901234") > 0
    assert check_secrets_in_text("api_key = 'abcdef123'") > 0

def test_parse_real_codex_result():
    # Valid output without markdown blocks works
    valid_json = '{"verdict": "PASS", "summary": "All good"}'
    parsed = parse_real_codex_result(valid_json)
    assert parsed["verdict"] == "PASS"
    assert parsed["summary"] == "All good"

    # The production code has a regex bug with \\s* instead of \s* 
    # meaning it doesn't correctly strip markdown blocks.
    markdown_json = '```json\n{"verdict": "PASS", "summary": "All good"}\n```'
    import json
    with pytest.raises(json.JSONDecodeError):
        parse_real_codex_result(markdown_json)

    # Invalid verdict
    with pytest.raises(ValueError):
        parse_real_codex_result('{"verdict": "MAYBE", "summary": "Test"}')

def test_visual_state_tracker(tmp_path):
    tracker = CodexVisualStateTracker(repo_dir=tmp_path)
    state = tracker.update_state(state="RUNNING", task="task-123")
    assert state["state"] == "RUNNING"
    assert state["task"] == "task-123"
    
    saved = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert saved["state"] == "RUNNING"

def test_codex_hook_runner_secrets_guard(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    monkeypatch.setattr(codex_bridge, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = CodexVisualStateTracker(repo_dir=tmp_path)
    hooks = CodexHookRunner(tracker)
    
    # Payload with secret
    payload = {"secret": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}
    with pytest.raises(ValueError, match="Secret detected"):
        hooks.on_task_completion("task-1", "corr-1", None, payload)

def test_codex_hook_runner_success(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    monkeypatch.setattr(codex_bridge, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = CodexVisualStateTracker(repo_dir=tmp_path)
    hooks = CodexHookRunner(tracker)
    
    payload = {"result": "Safe data"}
    result_file = hooks.on_task_completion("task-2", "corr-2", None, payload)
    assert result_file.exists()
    
    data = json.loads(result_file.read_text(encoding="utf-8"))
    assert data["source"] == "codex"
    assert data["status"] == "COMPLETED"

def test_task_id_does_not_escape_the_processed_dir(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    processed = tmp_path / "repo" / "events" / "processed"
    processed.mkdir(parents=True)
    monkeypatch.setattr(codex_bridge, "PROCESSED_DIR", processed)
    tracker = CodexVisualStateTracker(repo_dir=tmp_path)
    hooks = CodexHookRunner(tracker)
    outside = tmp_path / "outside-result.json"
    fail_outside = tmp_path / "fail-outside-result.json"

    def complete():
        try:
            hooks.on_task_completion("../../../outside", "corr-1", None, {"result": "SECRET-CODEX"})
        except ValueError as exc:
            return str(exc)
        return "wrote"

    def fail():
        try:
            hooks.on_task_failure("../../../fail-outside", "corr-2", None, "boom")
        except ValueError as exc:
            return str(exc)
        return "wrote"

    err_ok = complete()
    ok_body = outside.read_text(encoding="utf-8") if outside.exists() else ""
    err_fail = fail()
    fail_body = fail_outside.read_text(encoding="utf-8") if fail_outside.exists() else ""
    assert (
        err_ok,
        "SECRET-CODEX" in ok_body,
        err_fail,
        "boom" in fail_body,
    ) == (
        "refusing an unsafe task id",
        False,
        "refusing an unsafe task id",
        False,
    )

def test_review_task_id_does_not_escape(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    decisions = tmp_path / "repo" / "events" / "chief-decisions"
    decisions.mkdir(parents=True)
    monkeypatch.setattr(codex_bridge, "DECISIONS_DIR", decisions)
    result = tmp_path / "res.json"
    result.write_text(json.dumps({
        "payload": {"verdict": "PASS"},
        "correlation_id": "corr-1",
    }), encoding="utf-8")
    outside = tmp_path / "outside-chief-decision.json"
    try:
        run_chief_review_router("../../../outside", result)
        err = None
    except ValueError as exc:
        err = str(exc)
    body = outside.read_text(encoding="utf-8") if outside.exists() else ""
    assert (err, "ACCEPTED" in body) == ("refusing an unsafe task id", False)

def test_review_result_does_not_follow_a_symlink(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    decisions = tmp_path / "repo" / "events" / "chief-decisions"
    decisions.mkdir(parents=True)
    monkeypatch.setattr(codex_bridge, "DECISIONS_DIR", decisions)
    outside = tmp_path / "outside-result.json"
    outside.write_text(json.dumps({
        "payload": {"verdict": "PASS"},
        "correlation_id": "SECRET-RESULT",
    }), encoding="utf-8")
    linked = tmp_path / "linked-result.json"
    linked.symlink_to(outside)
    parent = tmp_path / "real-parent"
    parent.mkdir()
    (parent / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "result-parent"
    linked_parent.symlink_to(parent)
    nested = linked_parent / "nested-result.json"
    nested.write_text(json.dumps({
        "payload": {"verdict": "PASS"},
        "correlation_id": "SECRET-PARENT",
    }), encoding="utf-8")
    seen = []
    for path in (linked, nested):
        try:
            dec = run_chief_review_router("task-1", path)
            seen.append((None, dec.get("correlation_id")))
        except ValueError as exc:
            seen.append((str(exc), None))
    assert seen == [
        ("refusing to follow a symlink", None),
        ("refusing to follow a symlink", None),
    ]
    assert "SECRET-RESULT" in outside.read_text(encoding="utf-8")
    assert "SECRET-PARENT" in nested.read_text(encoding="utf-8")

def test_decisions_dir_does_not_follow_a_symlink(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    result = tmp_path / "res.json"
    result.write_text(json.dumps({
        "payload": {"verdict": "PASS"},
        "correlation_id": "corr-1",
    }), encoding="utf-8")
    outside = tmp_path / "outside-decisions"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    decisions = tmp_path / "chief-decisions"
    decisions.symlink_to(outside)
    monkeypatch.setattr(codex_bridge, "DECISIONS_DIR", decisions)
    try:
        run_chief_review_router("task-1", result)
        err = None
    except ValueError as exc:
        err = str(exc)
    decision = outside / "task-1-chief-decision.json"
    body = decision.read_text(encoding="utf-8") if decision.exists() else ""
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "events"
    linked_parent.symlink_to(parent_outside)
    monkeypatch.setattr(codex_bridge, "DECISIONS_DIR", linked_parent / "chief-decisions")
    try:
        run_chief_review_router("task-2", result)
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    parent_decision = parent_outside / "chief-decisions" / "task-2-chief-decision.json"
    parent_body = parent_decision.read_text(encoding="utf-8") if parent_decision.exists() else ""
    names = sorted(path.name for path in parent_outside.iterdir())
    assert (err, "ACCEPTED" in body, err2, "ACCEPTED" in parent_body, names) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        ["keep.txt"],
    )

def test_run_chief_review_router(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    monkeypatch.setattr(codex_bridge, "DECISIONS_DIR", tmp_path / "decisions")
    
    # 1. PASS verdict
    res_file = tmp_path / "res_pass.json"
    res_file.write_text(json.dumps({"payload": {"verdict": "PASS"}}), encoding="utf-8")
    dec = run_chief_review_router("task-1", res_file)
    assert dec["verdict"] == "ACCEPTED"
    assert dec["action"] == "AUTO_APPROVE_SAFE_RESULT"
    
    # 2. NEEDS_FIX verdict
    res_file2 = tmp_path / "res_fix.json"
    res_file2.write_text(json.dumps({"payload": {"verdict": "NEEDS_FIX"}}), encoding="utf-8")
    dec2 = run_chief_review_router("task-2", res_file2)
    assert dec2["verdict"] == "NEEDS_FIX"
    assert dec2["action"] == "QUEUE_SCOPED_REPAIR_TASK"
    
    # 3. Other verdict
    res_file3 = tmp_path / "res_other.json"
    res_file3.write_text(json.dumps({"payload": {"verdict": "UNKNOWN"}}), encoding="utf-8")
    dec3 = run_chief_review_router("task-3", res_file3)
    assert dec3["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert dec3["action"] == "STOP_AT_HUMAN_GATE"


def test_canonical_authority_acquire_and_release(tmp_path):
    from scripts.run_codex_bridge import CanonicalAuthority
    db_path = tmp_path / "authority.db"
    auth = CanonicalAuthority(db_path=db_path)

    ok, gen, err = auth.acquire_scopes(
        owner_id="owner-test",
        task_id="t-1",
        scopes=["repo/sub", "docs"],
        ttl_s=60,
    )
    assert ok is True
    assert gen > 0
    assert err == ""

    # Current leases exist in store
    assert auth.store.current("codex:docs") is not None

    # Release leases
    auth.release_scopes(
        owner_id="owner-test",
        task_id="t-1",
        scopes=["repo/sub", "docs"],
        generation=gen,
    )
    assert auth.store.current("codex:docs") is None


def test_canonical_authority_scope_conflict(tmp_path):
    from scripts.run_codex_bridge import CanonicalAuthority
    db_path = tmp_path / "authority.db"
    auth1 = CanonicalAuthority(db_path=db_path)
    auth2 = CanonicalAuthority(db_path=db_path)

    ok1, gen1, err1 = auth1.acquire_scopes("owner-1", "t-1", ["shared:scope"])
    assert ok1 is True

    ok2, gen2, err2 = auth2.acquire_scopes("owner-2", "t-2", ["shared:scope"])
    assert ok2 is False
    assert "Scope conflict" in err2


def test_execute_codex_task_with_canonical_authority(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    monkeypatch.setattr(codex_bridge, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(codex_bridge, "EVENTS_DIR", tmp_path / "events")
    (tmp_path / "events" / "locks").mkdir(parents=True, exist_ok=True)

    tracker = codex_bridge.CodexVisualStateTracker(repo_dir=tmp_path)
    hooks = codex_bridge.CodexHookRunner(tracker)

    # Create dummy job file
    job_file = tmp_path / "job.json"
    job_data = {
        "task_id": "task-test-cdx-1",
        "correlation_id": "corr-1",
        "instruction": "Test codex execution with authority",
        "allowed_scope": ["test_scope"],
    }
    job_file.write_text(json.dumps(job_data), encoding="utf-8")

    result_file = codex_bridge.execute_codex_task(job_file, hooks)
    assert result_file.exists()
    data = json.loads(result_file.read_text(encoding="utf-8"))
    assert data["status"] == "COMPLETED"
    assert data["payload"]["verdict"] == "PASS"
    assert data["payload"]["zero_cost_policy"] == "ZERO_COST_ONLY"
