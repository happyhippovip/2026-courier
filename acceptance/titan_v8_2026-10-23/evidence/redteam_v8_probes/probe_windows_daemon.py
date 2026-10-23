"""Probe: windows_worker.run_task with a self-labelled free/local task and no estimate.
subprocess.Popen is replaced by a recorder; nothing is executed."""
import subprocess
from scripts.windows_worker import daemon

seen = []


class FakeProc:
    pid = 4242
    returncode = 0

    def __init__(self, cmd, **kw):
        seen.append((cmd[0], sorted(k for k in kw), "env" in kw))

    def communicate(self, timeout=None):
        return ("", "")


daemon.subprocess.Popen = FakeProc
cfg = {"WORKER_ID": "probe"}
for label, task in {
    "free_no_estimate": {"task_id": "t1", "cost_class": "free", "instruction": "codex exec hi"},
    "routing_local_no_estimate": {"task_id": "t2", "routing_decision": {"COST_CLASS": "local"},
                                  "instruction": "agy -p hi"},
    "no_class_no_estimate": {"task_id": "t3", "instruction": "claude -p hi"},
    "explicit_zero": {"task_id": "t4", "estimated_cost_eur": 0.0, "instruction": "gemini -p hi"},
}.items():
    before = len(seen)
    try:
        res = daemon.run_task(task, cfg)
        status = res.get("status"), (res.get("stderr") or "")[:40]
    except Exception as exc:
        status = ("EXC", type(exc).__name__)
    launched = len(seen) > before
    open("/tmp/claude-0/-home-user-2026-courier/4510bb24-32c0-5203-8ebf-43dd2db70f44/scratchpad/redteam_v8/win.out","a").write(f"{label}: powershell_launched={launched} result={status} env_passed={seen[-1][2] if launched else '-'}\n")
