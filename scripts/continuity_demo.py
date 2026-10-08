#!/usr/bin/env python3
"""One-command continuity demo: Goal -> A -> B -> DONE across a hard worker kill.

    python scripts/continuity_demo.py run --out DIR
    python scripts/continuity_demo.py verify DIR

``run`` starts one real V1 controller and one worker with the ledger idle tick
(courier_worker.ledger_tick) in an isolated COURIER_HOME under DIR. The ledger
holds one goal with two missions; B depends on A. After A is COMPLETE the
worker is killed hard (kill -9 / TerminateProcess) and started once more.
Nothing but the worker's own idle tick moves work from the ledger to the
controller. When A and B are both FINAL_DONE the demo stops every process it
started and writes DIR/receipt.json and DIR/receipt.md.

``verify`` recomputes the evidence part of the receipt from the files left in
DIR (journal hash chain, task events, ledger FINAL events, artifact digests)
and checks the receipt digest. It starts no process and writes nothing. Any
edit to the journal, the ledger or the receipt makes it fail.

The synthetic adapter is the contract proof, not a provider. The demo shows
that interrupted work resumes without duplicate work and leaves checkable
evidence. It does not show a production provider run.

Exit codes: 0 PASS, 1 FAIL (evidence does not hold), 2 usage or setup error.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA = "courier.continuity_receipt.v1"
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
GOAL_ID = "goal.demo.continuity"
GOAL_FP = hashlib.sha256(b"courier continuity demo: A then B").hexdigest()
UNITS = {"A": "unit-a", "B": "unit-b"}
# A pass runs at most once per interval. A finishes well inside one interval,
# so the hard kill lands after A and before the pass that posts B.
TICK_INTERVAL_S = 12.0
HEARTBEAT_S = 0.5
ADAPTER_NOTE = "synthetic adapter: contract proof, not a provider"


def _utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(receipt):
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


# -- evidence (shared by run and verify) --------------------------------------

def _journal_events(db_path):
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY seq")]


def _chain(db_path):
    """Verify the journal hash chain on a temporary copy; the original is not opened for writing."""
    from courier_core.journal import Journal

    with tempfile.TemporaryDirectory(prefix="courier-verify-") as tmp:
        copy = Path(tmp) / "copy.db"
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        with contextlib.closing(sqlite3.connect(uri, uri=True, timeout=5)) as src, \
                contextlib.closing(sqlite3.connect(str(copy))) as dst:
            src.backup(dst)
        journal = Journal(copy, readonly=True)
        journal.open()
        try:
            report = journal.verify_chain()
        finally:
            close = getattr(journal, "close", None)
            if close is not None:
                close()
    return report


def collect_evidence(home):
    """Everything a third party can recompute from the files in ``home``."""
    from scripts.coordination_ledger import EventType
    from scripts.coordination_resume import reduce_store
    from scripts.github_coordination import FileCoordinationStore

    home = Path(home)
    db = home / "courier.db"
    ledger = home / "coordination_ledger.jsonl"
    report = _chain(db)
    events = _journal_events(db)
    created = [e for e in events if e["type"] == "TASK_CREATED"]
    per_task = {e["task_id"]: Counter() for e in created}
    artifacts = {e["task_id"]: [] for e in created}
    for e in events:
        if e["task_id"] in per_task:
            per_task[e["task_id"]][e["type"]] += 1
            if e["type"] == "RESULT_READY":
                payload = json.loads(e["payload"])
                artifacts[e["task_id"]] += [a.get("sha256") for a in payload.get("artifacts", [])]
    workers = sorted({e["worker_id"] for e in events if e.get("worker_id")})

    finals = [e for e in reduce_store(FileCoordinationStore(ledger)).events
              if e.event_type == EventType.FINAL]
    state_path = home / "ledger_bridge_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"missions": {}}
    missions = {}
    for mission, unit in UNITS.items():
        m_state = state["missions"].get(mission, {})
        task_id = m_state.get("task_id")
        counts = per_task.get(task_id, Counter())
        m_finals = [f for f in finals if f.mission_id == mission]
        missions[mission] = {
            "task_id": task_id,
            "bridge_status": m_state.get("status"),
            "tasks_created": counts["TASK_CREATED"],
            "result_accepted": counts["RESULT_ACCEPTED"],
            "task_complete": counts["TASK_COMPLETE"],
            "ledger_final": len(m_finals),
            "final_bound_to_task": bool(m_finals) and all(
                f"task_id={task_id}" in f.evidence_ref and f"goal_id={GOAL_ID}" in f.evidence_ref
                and f.payload_hash == hashlib.sha256(f.evidence_ref.encode("utf-8")).hexdigest()
                for f in m_finals),
            "artifact_sha256_expected": hashlib.sha256(unit.encode("utf-8")).hexdigest(),
            "artifact_present": hashlib.sha256(unit.encode("utf-8")).hexdigest() in artifacts.get(task_id, []),
        }
    return {
        "goal_id": GOAL_ID,
        "goal_fingerprint": GOAL_FP,
        "journal": {"chain_ok": report.ok, "events": report.count, "head_seq": report.head_seq,
                    "head_hash": report.head_hash, "first_bad_seq": report.first_bad_seq,
                    "reason": report.reason},
        "journal_sha256": _sha256_file(db),
        "ledger_sha256": _sha256_file(ledger),
        "tasks_created_total": len(created),
        "distinct_worker_ids": len(workers),
        "missions": missions,
    }


def judge(evidence):
    """Return the list of failed checks (empty means PASS)."""
    fails = []
    if not evidence["journal"]["chain_ok"]:
        fails.append(f"journal hash chain broken: {evidence['journal']['reason']}")
    if evidence["tasks_created_total"] != len(UNITS):
        fails.append(f"expected {len(UNITS)} tasks, found {evidence['tasks_created_total']} (duplicate or missing work)")
    task_ids = [m["task_id"] for m in evidence["missions"].values()]
    if None in task_ids or len(set(task_ids)) != len(task_ids):
        fails.append("missions are not bound to distinct tasks")
    for name, m in evidence["missions"].items():
        for key in ("tasks_created", "result_accepted", "task_complete", "ledger_final"):
            if m[key] != 1:
                fails.append(f"mission {name}: {key}={m[key]}, expected exactly 1")
        if m["bridge_status"] != "FINAL_DONE":
            fails.append(f"mission {name}: bridge status {m['bridge_status']!r}, expected FINAL_DONE")
        if not m["final_bound_to_task"]:
            fails.append(f"mission {name}: ledger FINAL not bound to its task and goal")
        if not m["artifact_present"]:
            fails.append(f"mission {name}: expected artifact digest missing")
    return fails


# -- run ------------------------------------------------------------------------

class _Procs:
    def __init__(self, home, logs):
        self.home, self.logs = home, logs
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.procs, self._handles, self.worker_runs = [], [], 0

    def spawn(self, args, log_name, new_group=False):
        env = dict(os.environ)
        env["COURIER_HOME"] = str(self.home)
        env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
        log = open(self.logs / log_name, "ab")
        self._handles.append(log)
        kwargs = {}
        if new_group:
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
        proc = subprocess.Popen([sys.executable, "-m", *args], cwd=str(REPO_ROOT), env=env,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **kwargs)
        self.procs.append(proc)
        return proc

    def start_worker(self):
        self.worker_runs += 1
        return self.spawn(
            ["courier_worker.host", "--home", str(self.home), "--controller", self.base_url,
             "--max-tasks", "1", "--heartbeat", str(HEARTBEAT_S),
             "--ledger-agent-id", AGENT, "--ledger-host-id", HOST,
             "--ledger-tick-interval", str(TICK_INTERVAL_S), "--ledger-tick-timeout", "60"],
            f"worker-{self.worker_runs}.log", new_group=True)

    def close(self):
        """Stop only the processes this demo started (and their children)."""
        import psutil

        for proc in self.procs:
            if proc.poll() is None:
                with contextlib.suppress(psutil.Error):
                    for child in psutil.Process(proc.pid).children(recursive=True):
                        with contextlib.suppress(psutil.Error):
                            child.kill()
                proc.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=10)
        for handle in self._handles:
            handle.close()


def _wait(predicate, timeout, what, procs=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        if procs is not None and procs.procs and procs.procs[-1].poll() is not None:
            raise RuntimeError(f"{what}: a demo process exited early ({procs.procs[-1].returncode})")
        time.sleep(0.2)
    raise RuntimeError(f"timed out after {timeout}s waiting for {what}")


def _seed(home):
    from scripts.coordination_ledger import AgentID, CoordinationEvent, EventType, HostID, MissionStatus
    from scripts.github_coordination import FileCoordinationStore

    def event(eid, mid, ts, deps=None):
        return CoordinationEvent(
            event_id=eid, mission_id=mid, agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=deps or [],
            head="demo", evidence_ref="demo", created_at=ts, payload_hash="demo", ownership=AGENT)

    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    now = _utc()
    store.write_event(event("demo-a-assign", "A", now))
    store.write_event(event("demo-b-assign", "B", now, deps=["A"]))
    spec = lambda unit: {  # noqa: E731
        "adapter": "synthetic",
        "params": {"sleep_s": 0, "write": "out.txt", "content": unit, "hang": False,
                   "fail_transient_n": 0, "fault_attempts": [1]},
        "effect_class": "idempotent", "max_attempts": 2, "lease_ttl_s": 10,
        "goal_id": GOAL_ID, "goal_fingerprint": GOAL_FP,
    }
    (home / "ledger_tasks.json").write_text(
        json.dumps({m: spec(u) for m, u in UNITS.items()}, indent=2), encoding="utf-8")


def _say(msg):
    print(f"[{_utc()}] {msg}", flush=True)


def run(out, timeout_s=180.0):
    import requests

    out = Path(out)
    if out.exists() and any(out.iterdir()):
        print(f"--out {out} must be empty or new", file=sys.stderr)
        return 2
    home, logs = out / "home", out / "logs"
    home.mkdir(parents=True)
    logs.mkdir()
    started = _utc()
    t0 = time.monotonic()
    procs = _Procs(home, logs)
    timeline = []

    def mark(step):
        timeline.append({"t_s": round(time.monotonic() - t0, 1), "step": step})
        _say(step)

    def task_status(session, task_id):
        r = session.get(f"{procs.base_url}/v1/tasks/{task_id}", timeout=5)
        return r.json().get("status") if r.status_code == 200 else None

    def created():
        db = home / "courier.db"
        return [e for e in _journal_events(db) if e["type"] == "TASK_CREATED"] if db.exists() else []

    def bridge_state():
        p = home / "ledger_bridge_state.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"missions": {}}

    try:
        procs.spawn(["courier_core.serve", "--home", str(home), "--port", str(procs.port), "--print-port"],
                    "controller.log")
        token_file = home / "run" / "controller.token"
        session = requests.Session()

        def ready():
            if not token_file.exists():
                return False
            session.headers["X-Courier-Token"] = token_file.read_text(encoding="utf-8").strip()
            with contextlib.suppress(requests.RequestException):
                return session.get(procs.base_url + "/v1/health", timeout=2).status_code == 200
            return False

        _wait(ready, 30, "controller health", procs)
        mark("controller up (loopback, token file, never printed)")
        _seed(home)
        mark("goal seeded in ledger: mission A, mission B depends on A")

        procs.start_worker()
        mark("worker #1 started with ledger idle tick")
        first = _wait(created, 60, "A posted by the idle tick", procs)
        task_a = first[0]["task_id"]
        mark(f"A posted by the worker's own tick as task {task_a}")
        _wait(lambda: task_status(session, task_a) == "COMPLETE", 60, "A COMPLETE", procs)
        mark("A COMPLETE")

        worker = procs.procs[-1]
        import psutil
        with contextlib.suppress(psutil.Error):
            for child in psutil.Process(worker.pid).children(recursive=True):
                with contextlib.suppress(psutil.Error):
                    child.kill()
        worker.kill()
        worker.wait(timeout=10)
        if len(created()) != 1:
            raise RuntimeError("B was posted before the hard kill; the demo did not interrupt the hand-over")
        if (home / "coordination_ledger.jsonl").read_text(encoding="utf-8").count('"event_type": "FINAL"'):
            raise RuntimeError("A was fed back before the hard kill; the demo did not interrupt the hand-over")
        mark("worker #1 KILLED HARD (no shutdown, A not yet fed back to the ledger, B not posted)")

        procs.start_worker()
        mark("worker #2 started (restart); it must resume, not redo")

        def done():
            missions = bridge_state()["missions"]
            return all(missions.get(m, {}).get("status") == "FINAL_DONE" for m in UNITS)

        _wait(done, timeout_s, "A and B FINAL_DONE", procs)
        mark("A and B FINAL_DONE in the ledger")

        frozen = (home / "coordination_ledger.jsonl").read_bytes()
        tick_path = home / "run" / "ledger_tick.json"
        before = json.loads(tick_path.read_text(encoding="utf-8")).get("passes", 0)
        _wait(lambda: json.loads(tick_path.read_text(encoding="utf-8")).get("passes", 0) > before,
              TICK_INTERVAL_S * 3, "one more idle pass", procs)
        replay_noop = (home / "coordination_ledger.jsonl").read_bytes() == frozen and len(created()) == len(UNITS)
        mark(f"one more idle pass after DONE: ledger unchanged={replay_noop}")

        worker = procs.procs[-1]
        if os.name == "nt":
            import signal
            os.kill(worker.pid, signal.CTRL_BREAK_EVENT)
        else:
            worker.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            worker.wait(timeout=20)
        with contextlib.suppress(requests.RequestException):
            session.post(procs.base_url + "/v1/shutdown", timeout=5)
        with contextlib.suppress(subprocess.TimeoutExpired):
            procs.procs[0].wait(timeout=15)
        mark("all demo processes stopped; journal and ledger frozen")
    except Exception as exc:  # noqa: BLE001 - report and keep the evidence dir
        print(f"DEMO ERROR: {exc}", file=sys.stderr)
        for log in sorted(logs.iterdir()):
            tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
            print(f"--- {log.name}\n" + "\n".join(tail), file=sys.stderr)
        return 2
    finally:
        procs.close()

    evidence = collect_evidence(home)
    fails = judge(evidence)
    if not replay_noop:
        fails.append("ledger changed or a task was created after DONE")
    receipt = {
        "schema": SCHEMA,
        "scenario": "Goal -> A -> B -> DONE; worker hard-killed after A COMPLETE, restarted once",
        "adapter": ADAPTER_NOTE,
        "started_utc": started,
        "finished_utc": _utc(),
        "duration_s": round(time.monotonic() - t0, 1),
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "observed": {"worker_runs": procs.worker_runs, "hard_kills": 1, "replay_noop_after_done": replay_noop,
                     "timeline": timeline},
        "evidence": evidence,
        "verdict": "PASS" if not fails else "FAIL",
        "fails": fails,
    }
    receipt["receipt_sha256"] = _digest(receipt)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "receipt.md").write_text(render_md(receipt), encoding="utf-8")
    print(render_md(receipt))
    return 0 if not fails else 1


def render_md(r):
    ev = r["evidence"]
    lines = [
        f"# Courier continuity receipt: {r['verdict']}",
        "",
        f"- Scenario: {r['scenario']}",
        f"- Adapter: {r['adapter']}",
        f"- Run: {r['started_utc']} -> {r['finished_utc']} ({r['duration_s']} s, {r['platform']}, Python {r['python']})",
        f"- Worker runs: {r['observed']['worker_runs']}, hard kills: {r['observed']['hard_kills']}",
        f"- Tasks created: {ev['tasks_created_total']} for {len(ev['missions'])} missions (duplicates: {max(0, ev['tasks_created_total'] - len(ev['missions']))})",
        f"- Journal: {ev['journal']['events']} events, hash chain {'intact' if ev['journal']['chain_ok'] else 'BROKEN'}, head {ev['journal']['head_hash'][:16]}",
        f"- Ledger sha256: {ev['ledger_sha256'][:16]}  journal sha256: {ev['journal_sha256'][:16]}",
        f"- Replay after DONE changed nothing: {r['observed']['replay_noop_after_done']}",
        "",
        "| Mission | Task | Created | Accepted | Complete | Ledger FINAL | Bound | Artifact |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, m in ev["missions"].items():
        lines.append(f"| {name} | {m['task_id']} | {m['tasks_created']} | {m['result_accepted']} | {m['task_complete']} "
                     f"| {m['ledger_final']} | {'yes' if m['final_bound_to_task'] else 'NO'} | {'ok' if m['artifact_present'] else 'MISSING'} |")
    lines += ["", "## Timeline", ""] + [f"- +{s['t_s']} s: {s['step']}" for s in r["observed"]["timeline"]]
    if r["fails"]:
        lines += ["", "## Failed checks", ""] + [f"- {f}" for f in r["fails"]]
    lines += ["", f"Receipt sha256: `{r['receipt_sha256']}`",
              "Check it yourself: `python scripts/continuity_demo.py verify <dir>`", ""]
    return "\n".join(lines)


# -- verify ---------------------------------------------------------------------

def verify(out):
    out = Path(out)
    path = out / "receipt.json"
    if not path.exists() or not (out / "home" / "courier.db").exists():
        print(f"no receipt or journal under {out}", file=sys.stderr)
        return 2
    receipt = json.loads(path.read_text(encoding="utf-8"))
    fails = []
    if receipt.get("schema") != SCHEMA:
        fails.append(f"unknown schema {receipt.get('schema')!r}")
    if _digest(receipt) != receipt.get("receipt_sha256"):
        fails.append("receipt digest mismatch: receipt.json was edited")
    try:
        evidence = collect_evidence(out / "home")
    except Exception as exc:  # noqa: BLE001 - unreadable evidence fails closed
        evidence = None
        fails.append(f"evidence unreadable: {exc}")
    if evidence is not None:
        if evidence != receipt.get("evidence"):
            changed = sorted(k for k in set(evidence) | set(receipt.get("evidence", {}))
                             if evidence.get(k) != receipt.get("evidence", {}).get(k))
            fails.append(f"recomputed evidence differs from receipt: {', '.join(changed)}")
        fails += judge(evidence)
    if receipt.get("verdict") != "PASS":
        fails.append(f"receipt verdict is {receipt.get('verdict')!r}")
    if fails:
        print("VERIFY FAIL")
        for f in fails:
            print(f"- {f}")
        return 1
    ev = receipt["evidence"]
    print(f"VERIFY PASS: {ev['tasks_created_total']} tasks for {len(ev['missions'])} missions, "
          f"0 duplicates, journal chain intact ({ev['journal']['events']} events), "
          f"every mission exactly one FINAL; receipt {receipt['receipt_sha256'][:16]}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run the demo and write a receipt")
    p_run.add_argument("--out", default=None, help="empty output dir (default: a new temp dir)")
    p_run.add_argument("--timeout", type=float, default=180.0)
    p_verify = sub.add_parser("verify", help="recompute and check a receipt")
    p_verify.add_argument("dir")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        out = args.out or tempfile.mkdtemp(prefix="courier-continuity-")
        print(f"evidence dir: {out}", flush=True)
        return run(out, args.timeout)
    return verify(args.dir)


if __name__ == "__main__":
    sys.exit(main())
