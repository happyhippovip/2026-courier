import json
import tempfile
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from scripts.build_antigravity_worker_job import build_worker_job, canonical_hash
from scripts.run_antigravity_bridge import (
    AntigravityVisualStateTracker,
    AntigravityHookRunner,
    execute_bridge_task,
    run_chief_review_router,
)
import scripts.run_antigravity_bridge as rab


def test_phase3_isolated_antigravity_bridge_e2e():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cmd_file = tmp / "cmd.json"
        payload = {
            "target_agent": "ANTIGRAVITY",
            "one_next_command": "echo test-verification-v16",
            "allowed_scope": ["2026-courier"],
            "cost_policy": "ZERO_COST_ONLY",
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        }
        cmd_data = {
            "schema_version": "2.0",
            "message_id": "msg-test-16",
            "task_id": "task-recovery-v16-echo",
            "correlation_id": "corr-v16-001",
            "parent_id": None,
            "source": "chief",
            "destination": "antigravity",
            "type": "COMMAND",
            "status": "NEW",
            "created_at": "2026-10-09T13:45:00Z",
            "payload": payload,
            "payload_hash": canonical_hash(payload),
            "max_iterations": 1,
        }
        cmd_file.write_text(json.dumps(cmd_data, indent=2), encoding="utf-8")

        dispatch_dir = tmp / "dispatch"
        job = build_worker_job(cmd_file, dispatch_dir)
        task_id = job["task_id"]

        job_path = dispatch_dir / f"{task_id}-worker-job.json"
        assert job_path.exists(), "Job file was not created"

        # Redirect paths to tmp for isolated test claim
        rab.PROCESSED_DIR = tmp / "processed"
        rab.DECISIONS_DIR = tmp / "chief-decisions"
        rab.COURIER_DIR = tmp

        tracker = AntigravityVisualStateTracker(repo_dir=tmp)
        hooks = AntigravityHookRunner(tracker)

        # Execute bridge task
        result_path = execute_bridge_task(job_path, hooks)
        assert result_path.exists(), "Result file missing"

        res_data = json.loads(result_path.read_text(encoding="utf-8"))
        res_hash = res_data.get("payload_hash", "")
        verdict = res_data.get("payload", {}).get("verdict", "")
        assert res_data["status"] == "COMPLETED"
        assert verdict == "PASS"
        assert len(res_hash) == 64

        # Run Chief Review Router
        decision = run_chief_review_router(task_id, result_path)
        assert decision.get("verdict") == "ACCEPTED"
        assert decision.get("action") == "AUTO_APPROVE_SAFE_RESULT"
