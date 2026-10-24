"""V43: bridge gate admits, controller F-C1 gate refuses -> what does the bridge do on the next passes?"""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "tests"))
from test_ledger_v1_bridge import _home, _seed, _ready, _run, _spec, TOKEN
from courier_core.controller import Controller, ApiError

tmp = Path(tempfile.mkdtemp())
ctrl = Controller(tmp / "ctrl").boot()
posts = []

def transport(method, url, headers, body, timeout):
    if method == "POST" and url.endswith("/v1/tasks"):
        posts.append(1)
        try:
            status, view = ctrl.create_task(json.loads(body))
            return status, json.dumps(view).encode()
        except ApiError as exc:
            return exc.status, json.dumps({"error": exc.code}).encode()
    if method == "GET" and "/v1/tasks/" in url:
        task = ctrl.journal.task(url.rstrip("/").rsplit("/", 1)[-1])
        return (404, b"{}") if task is None else (200, json.dumps({"task_id": task.task_id, "status": task.status.value,
                                                                    "attempt": task.attempt}).encode())
    raise AssertionError(url)

home = _home(tmp, {"A": _spec(adapter="telegram_delivery")})     # declared 0.0 EUR, adapter has no COST_CLASS
_seed(home, [_ready("A", "a-assign")])
for n in range(3):
    code, out, err, log, lines = _run(home, transport)
    state = json.loads((home / "ledger_bridge_state.json").read_text())["missions"]["A"]
    print(f"pass {n+1}: exit={code} posts_so_far={len(posts)} posted={state.get('posted')} status={state.get('status')} out={out.strip()[:90]}")
ctrl.stop()
