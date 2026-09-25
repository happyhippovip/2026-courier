#!/usr/bin/env python3
"""Durable work-queue prototype (new file, isolated scope).

COURIER OWNS WORK. AGENTS BORROW TASKS. No LLM in the scheduling loop:
claim/reconcile/lease are local deterministic file operations.

State: <state_dir>/queue.json  (default /tmp/courier_work_queue)
Task statuses: WAITING READY CLAIMED RUNNING VERIFYING DONE BLOCKED HUMAN_GATE
Result stages (DoD): SPECIFIED IMPLEMENTED TESTED EVIDENCE_READY ACCEPTED
SPECIFIED IS NOT DONE: DONE requires the package Definition of Done.

CLI:
  init <package_id>            create package record
  add <json>                   add task record
  claim --worker W --caps a,b  claim highest-priority READY task (lease)
  complete <id> --result-json J [--stage S]   record result, reconcile deps
  block <id> --reason R        mark BLOCKED
  state                        dump queue snapshot
  reconcile --reclaim-stale N  return stale CLAIMED/RUNNING to READY

ONE WRITER PER MUTABLE SCOPE: a claim is refused when any write_scope of
the task overlaps a scope already held by another live claim.
"""
import argparse
import contextlib
import json
import time
from pathlib import Path

STATUSES = ("WAITING", "READY", "CLAIMED", "RUNNING",
            "VERIFYING", "DONE", "BLOCKED", "HUMAN_GATE")
STAGES = ("SPECIFIED", "IMPLEMENTED", "TESTED", "EVIDENCE_READY", "ACCEPTED")


def state_dir(args):
    d = Path(args.state_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def qfile(args):
    return state_dir(args) / "queue.json"


@contextlib.contextmanager
def _locked(path):
    """Cross-platform mutual exclusion (POSIX + Windows).

    Uses atomic directory creation: mkdir is atomic on both platforms,
    unlike fcntl.flock which does not exist on Windows.
    """
    import os
    lockdir = str(path) + ".lockdir"
    for _ in range(1000):
        try:
            os.mkdir(lockdir)
            break
        except FileExistsError:
            time.sleep(0.01)
    else:
        raise TimeoutError(f"queue lock busy: {path}")
    try:
        yield
    finally:
        try:
            os.rmdir(lockdir)
        except OSError:
            pass


def load(args):
    p = qfile(args)
    if not p.exists():
        return {"packages": {}, "tasks": {}, "leases": {}}
    with _locked(p):
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)


def save(args, data):
    p = qfile(args)
    tmp = p.with_suffix(".tmp")
    with _locked(p):
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
            fh.write("\n")
        tmp.replace(p)


def live_scopes(data, now, stale_after):
    held = {}
    for tid, lease in data.get("leases", {}).items():
        if now - lease.get("claimed_at", 0) <= stale_after:
            for scope in lease.get("write_scopes", []):
                held.setdefault(scope, []).append(tid)
    return held


def reconcile(data, now):
    """Dependency reconcile: dependents whose deps are all DONE become READY."""
    changed = []
    tasks = data["tasks"]
    for tid, task in tasks.items():
        if task.get("status") in ("WAITING", "BLOCKED"):
            if str(task.get("block_reason", "")).startswith("NOT_REQUIRED"):
                continue  # eliminated work never reactivates
            deps = task.get("dependencies", [])
            if deps and all(tasks.get(d, {}).get("status") == "DONE" for d in deps):
                task["status"] = "READY"
                changed.append(tid)
    return changed


def cmd_init(args, data):
    data["packages"][args.package_id] = {
        "package_id": args.package_id,
        "definition_of_done": args.dod,
        "created_at": time.time(),
    }
    return {"package": args.package_id}


def cmd_add(args, data):
    task = json.loads(args.json)
    for field in ("task_id", "package_id", "description", "dependencies",
                  "read_scopes", "write_scopes", "status"):
        if field not in task:
            return {"error": f"missing field {field}"}
    if task["status"] not in STATUSES:
        return {"error": "bad status"}
    data["tasks"][task["task_id"]] = task
    return {"added": task["task_id"], "status": task["status"]}


def cmd_claim(args, data, now):
    caps = set(args.caps.split(",")) if args.caps else set()
    held = live_scopes(data, now, args.lease_ttl)
    cands = [t for t in data["tasks"].values()
             if t.get("status") == "READY"
             and (not caps or caps >= set(t.get("required_capabilities", [])))
             and (not args.package or t.get("package_id") == args.package)]
    cands.sort(key=lambda t: (t.get("priority", 99), t["task_id"]))
    for task in cands:
        clash = [s for s in task.get("write_scopes", []) if s in held]
        if clash:
            continue
        task["status"] = "CLAIMED"
        task["owner"] = args.worker
        task["attempt_count"] = task.get("attempt_count", 0) + 1
        task["dispatch_count"] = task.get("dispatch_count", 0) + 1
        task["attempt_id"] = f"{task['task_id']}:attempt:{task['attempt_count']}"
        task["dispatch_id"] = f"{task['task_id']}:dispatch:{task['dispatch_count']}"
        data["leases"][task["task_id"]] = {
            "worker": args.worker,
            "write_scopes": task.get("write_scopes", []),
            "claimed_at": now,
        }
        return {"claimed": task["task_id"], "scopes": task.get("write_scopes", [])}
    return {"claimed": None, "reason": "no unblocked READY task"}


def cmd_complete(args, data, now):
    task = data["tasks"].get(args.task_id)
    if not task or task.get("status") not in ("CLAIMED", "RUNNING"):
        return {"error": "not claimed"}
    result = json.loads(args.result_json)
    task["result"] = result
    import hashlib
    if "attempt_id" in task and "dispatch_id" in task:
        _payload = {
            'task_id': task['task_id'],
            'attempt_id': task['attempt_id'],
            'dispatch_id': task['dispatch_id'],
            'executor_kind': task.get('executor_kind', 'LOCAL_FAKE')
        }
    else:
        # No dispatch identity (direct CLI use, pre-dispatch tasks):
        # bind the default id to the observed result content. Distinct
        # completions never share one static "<task_id>:r1" identity, while
        # an identical retry stays idempotent (same id marks the duplicate).
        _payload = {
            'task_id': task['task_id'],
            'result': result,
        }
    _payload_str = json.dumps(_payload, sort_keys=True, separators=(",", ":")).encode()
    default_rid = "result-" + hashlib.sha256(_payload_str).hexdigest()
    task["result_id"] = result.get("result_id", default_rid)
    task["result_stage"] = args.stage
    task["status"] = "DONE" if args.stage == "ACCEPTED" else "VERIFYING"
    data["leases"].pop(args.task_id, None)
    # Self-refill: package-defined dependents activate via reconcile.
    released = reconcile(data, now)
    return {"done": args.task_id, "stage": args.stage,
            "newly_ready": released}


def cmd_block(args, data, now):
    task = data["tasks"].get(args.task_id)
    if not task:
        return {"error": "unknown task"}
    task["status"] = "BLOCKED"
    task["block_reason"] = args.reason
    data["leases"].pop(args.task_id, None)
    return {"blocked": args.task_id}


def cmd_reconcile(args, data, now):
    # Restart recovery: stale CLAIMED/RUNNING leases are BLOCKED to prevent duplicate effects.
    reclaimed = []
    for tid, lease in list(data["leases"].items()):
        if now - lease.get("claimed_at", 0) > args.reclaim_stale:
            task = data["tasks"].get(tid)
            if task and task.get("status") in ("CLAIMED", "RUNNING"):
                if "result" not in task:  # may have crashed during execution
                    # STALE_WORKER_EFFECT_AMBIGUOUS: Replaying it risks a duplicate effect
                    task["status"] = "BLOCKED"
                    task["block_reason"] = "STALE_WORKER_EFFECT_AMBIGUOUS"
                    task.pop("owner", None)
                    reclaimed.append(tid)
            data["leases"].pop(tid, None)
    released = reconcile(data, now)
    return {"reclaimed": reclaimed, "newly_ready": released}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", default="/tmp/courier_work_queue")
    ap.add_argument("--lease-ttl", type=float, default=3600)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("package_id"); p.add_argument("--dod", default="")
    p = sub.add_parser("add"); p.add_argument("json")
    p = sub.add_parser("claim"); p.add_argument("--worker", required=True); p.add_argument("--caps", default=""); p.add_argument("--package", default="")
    p = sub.add_parser("complete"); p.add_argument("task_id"); p.add_argument("--result-json", required=True); p.add_argument("--stage", default="EVIDENCE_READY")
    p = sub.add_parser("block"); p.add_argument("task_id"); p.add_argument("--reason", required=True)
    p = sub.add_parser("reconcile"); p.add_argument("--reclaim-stale", type=float, default=3600)
    p = sub.add_parser("state")
    args = ap.parse_args(argv)
    data = load(args)
    now = time.time()
    if args.cmd == "init":
        out = cmd_init(args, data)
    elif args.cmd == "add":
        out = cmd_add(args, data)
    elif args.cmd == "claim":
        out = cmd_claim(args, data, now)
    elif args.cmd == "complete":
        out = cmd_complete(args, data, now)
    elif args.cmd == "block":
        out = cmd_block(args, data, now)
    elif args.cmd == "reconcile":
        out = cmd_reconcile(args, data, now)
    elif args.cmd == "state":
        out = {"tasks": {t: {"status": v.get("status"), "stage": v.get("result_stage")}
                         for t, v in data["tasks"].items()},
               "leases": list(data["leases"])}
    save(args, data)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
