import json
import subprocess
import sys
from pathlib import Path
import pytest

from courier_core.genesis_engine import (
    CourierGenesisEngine,
    GenesisPolicy,
    TaskStatus,
    VerdictOutcome,
)


def test_goal_decomposition_creates_proper_dag(tmp_path):
    engine = CourierGenesisEngine(mission_id="M-DAG", state_dir=tmp_path)
    goal = {
        "type": "SEQUENTIAL_PIPELINE",
        "steps": [
            {"task_id": "T1", "action_type": "EXECUTE_UNIT"},
            {"task_id": "T2", "action_type": "EXECUTE_UNIT"},
            {"task_id": "T3", "action_type": "EXECUTE_UNIT"},
        ],
    }
    tasks = engine.decompose_mission_goal(goal)
    assert len(tasks) == 3
    assert tasks[0].task_id == "T1" and tasks[0].depends_on == []
    assert tasks[1].task_id == "T2" and tasks[1].depends_on == ["T1"]
    assert tasks[2].task_id == "T3" and tasks[2].depends_on == ["T2"]

    # Only T1 is initially ready
    ready = engine.detect_next_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "T1"


def test_single_writer_enforcement(tmp_path):
    engine = CourierGenesisEngine(
        mission_id="M-SW",
        policy=GenesisPolicy(single_writer=True),
        state_dir=tmp_path,
    )
    t1 = engine.register_task("T1", "wk-1", "EXECUTE_UNIT", {})
    t2 = engine.register_task("T2", "wk-2", "EXECUTE_UNIT", {})

    ok, token, msg = engine.claim_task("T1", "worker-alpha")
    assert ok is True
    assert token is not None

    # Worker beta cannot claim while worker alpha is the active writer
    ok2, token2, msg2 = engine.claim_task("T2", "worker-beta")
    assert ok2 is False
    assert "Single-Writer violation" in msg2


def test_spend_limit_fails_closed(tmp_path):
    engine = CourierGenesisEngine(
        mission_id="M-SPEND",
        policy=GenesisPolicy(spend_limit_eur=0.0),
        state_dir=tmp_path,
    )
    engine.register_task("T1", "wk-cost", "EXECUTE_UNIT", {"cost_eur": 5.0})
    ok, token, msg = engine.claim_task("T1", "worker-alpha")
    assert ok is False
    assert "Spend limit exceeded" in msg
    assert engine.tasks["T1"].status == TaskStatus.BLOCKED


def test_spider_verification_rejects_http_scheme(tmp_path):
    engine = CourierGenesisEngine(
        mission_id="M-HTTP",
        policy=GenesisPolicy(require_https=True, allowed_origins=("https://example.org",)),
        state_dir=tmp_path,
    )
    t = engine.register_task(
        "T-HTTP",
        "wk-http",
        "SPIDER_CLAIM_VERIFY",
        {"url": "http://example.org/path", "quote": "test", "approved_origin": "https://example.org"},
    )
    verdict = engine.verify_execution("T-HTTP", {"exit_code": 0})
    assert verdict["outcome"] == VerdictOutcome.BLOCKED
    assert "HTTPS required" in verdict["reason"]


def test_spider_verification_rejects_redirect_out_of_grant(tmp_path):
    engine = CourierGenesisEngine(
        mission_id="M-REDIRECT",
        policy=GenesisPolicy(allowed_origins=("https://example.org",)),
        state_dir=tmp_path,
    )
    engine.register_task(
        "T-REDIR",
        "wk-redir",
        "SPIDER_CLAIM_VERIFY",
        {"url": "https://example.org/start", "quote": "test", "approved_origin": "https://example.org"},
    )

    def out_of_grant_fetcher(url):
        return ("https://untrusted-redirect.com/login", b"test")

    verdict = engine.verify_execution("T-REDIR", {"exit_code": 0}, fetcher=out_of_grant_fetcher)
    assert verdict["outcome"] == VerdictOutcome.BLOCKED
    assert "Redirect left approved origin" in verdict["reason"]


def test_spider_verification_supported_with_byte_anchor(tmp_path):
    engine = CourierGenesisEngine(
        mission_id="M-ANCHOR",
        policy=GenesisPolicy(allowed_origins=("https://example.org",)),
        state_dir=tmp_path,
    )
    quote = "Genesis Engine byte anchor"
    body = f"<html><body>Verified fact: {quote} right here.</body></html>".encode("utf-8")
    engine.register_task(
        "T-OK",
        "wk-ok",
        "SPIDER_CLAIM_VERIFY",
        {"url": "https://example.org/page", "quote": quote, "approved_origin": "https://example.org", "body": body},
    )

    verdict = engine.verify_execution("T-OK", {"exit_code": 0})
    assert verdict["accepted"] is True
    assert verdict["outcome"] == VerdictOutcome.SUPPORTED
    assert verdict["anchor"]["offset"] == body.decode("utf-8").find(quote)
    assert len(verdict["anchor"]["sha256"]) == 64


def test_circuit_breaker_trips_on_fatal_security_breach(tmp_path):
    engine = CourierGenesisEngine(mission_id="M-CB", state_dir=tmp_path)
    engine.register_task(
        "T1",
        "wk-1",
        "SPIDER_CLAIM_VERIFY",
        {"url": "http://insecure.org", "quote": "q", "approved_origin": "https://insecure.org"},
    )
    engine.register_task(
        "T2",
        "wk-2",
        "SPIDER_CLAIM_VERIFY",
        {"url": "https://insecure.org/page", "quote": "q", "approved_origin": "https://insecure.org"},
    )

    # Execute T1 -> fails on scheme
    res = engine.run_cycle(executor=lambda t: {}, worker_id="w1")
    assert res["status"] == "FAILED_OR_BLOCKED"
    assert engine.breaker.is_tripped("SPIDER_CLAIM_VERIFY") is True

    # Next ready task detection blocks T2 because the circuit breaker is tripped
    ready = engine.detect_next_ready_tasks()
    assert len(ready) == 0
    assert engine.tasks["T2"].status == TaskStatus.BLOCKED


def test_end_to_end_autonomous_loop(tmp_path):
    engine = CourierGenesisEngine(
        mission_id="M-E2E",
        policy=GenesisPolicy(spend_limit_eur=0.0, single_writer=True),
        state_dir=tmp_path,
    )
    goal = {
        "type": "SEQUENTIAL_PIPELINE",
        "steps": [
            {"task_id": "Step-1", "action_type": "EXECUTE_UNIT", "payload": {"expected_output": "P1"}},
            {"task_id": "Step-2", "action_type": "EXECUTE_UNIT", "payload": {"expected_output": "P2"}},
        ],
    }
    engine.decompose_mission_goal(goal)

    def mock_executor(task):
        expected = task.payload.get("expected_output")
        return {"exit_code": 0, "outputs": {"result": expected}}

    summary = engine.run_autonomous_loop(executor=mock_executor, worker_id="worker-lead")
    assert summary["all_completed"] is True
    assert summary["completed_count"] == 2
    assert summary["spent_eur"] == 0.0

    # Verify durable checkpoint and facts files exist
    assert (tmp_path / "M-E2E_checkpoint.json").exists()
    assert (tmp_path / "M-E2E_facts.jsonl").exists()

    with open(tmp_path / "M-E2E_facts.jsonl", encoding="utf-8") as f:
        facts = [json.loads(line) for line in f if line.strip()]
    assert len(facts) == 2
    assert facts[0]["task_id"] == "Step-1"
    assert facts[1]["task_id"] == "Step-2"


def test_cli_runner(tmp_path):
    repo_root = str(Path(__file__).resolve().parent.parent)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/courier_genesis_engine.py",
            "--mission",
            "M-CLI-TEST",
            "--state-dir",
            str(tmp_path),
            "--run",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed["all_completed"] is True
    assert parsed["completed_count"] == 3
