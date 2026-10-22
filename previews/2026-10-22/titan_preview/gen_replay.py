"""REPLAY snapshot from a real local controller run (synthetic adapter, no provider, no network).
Usage: python3 gen_replay.py <worktree> <out.json>"""
import json, sys, tempfile
from pathlib import Path
W = Path(sys.argv[1]); sys.path[:0] = [str(W), str(W / "tests" / "controller")]
from ctrl_helpers import FakeClock, Verifiers, accept_all, make_controller, run_attempt, task_body
from courier_hub import model
from courier_hub.kolibri_data import read_ledger

ctl = make_controller(Path(tempfile.mkdtemp()) / "home", clock=FakeClock(), verifier=Verifiers(synthetic=accept_all))
ok = ctl.create_task(task_body(adapter="synthetic", idempotency_key="replay-ok"))[1]["task_id"]
run_attempt(ctl); ctl.drain()
bad = ctl.create_task(task_body(adapter="synthetic", max_attempts=1, idempotency_key="replay-bad"))[1]["task_id"]
run_attempt(ctl, outcome="failure", result_id="r2"); ctl.drain()
ctl.create_task(task_body(adapter="synthetic", idempotency_key="replay-q"))
tasks = [ctl.journal.task(t) for t in ctl.journal.task_ids()] if hasattr(ctl.journal, "task_ids") else None
events = ctl.events_after(0, limit=500)
by = {}
for e in events:
    if e.task_id: by.setdefault(e.task_id, []).append(e)
tasks = [ctl.journal.task(t) for t in by]
view = model.home(tasks, by); view.update({"truth": "ok", "read_at": "2026-10-22T07:30:00Z"})
snap = {"observed_at": "2026-10-22T07:30:00Z", "mode_note": "REPLAY: echter lokaler Controller-Lauf, synthetischer Adapter",
        "ledger": read_ledger(view, "2026-10-22T07:30:00Z"),
        "muse_wall": {"available": False, "stations": []}, "ledger_bridge": {"available": False, "missions": []}}
Path(sys.argv[2]).write_text(json.dumps(snap, indent=1))
print({i["title"]: (i["pile"], i.get("verified"), bool(i.get("evidence"))) for i in snap["ledger"]["items"]})
