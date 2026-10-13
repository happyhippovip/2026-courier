"""Gate 2 motor: one result walks the path, then the queue parks on a wakeup.

persist → validate → contract → reconcile → dependencies → ready →
eligibility → select → dispatch.

An empty queue waits on the injected wakeup once. It does not sleep and it
does not create work. A provider that raises or is down drops only its own
task. A scope keeps the lease of the first writer.
"""

import time

from courier_runtime.lease import LeaseConflict

PATH = (
    "persist",
    "validate",
    "contract",
    "reconcile",
    "dependencies",
    "ready",
    "eligibility",
    "select",
    "dispatch",
)


def idle(wait):
    """Block on one wakeup. ``wait`` is the only pause; sleep is not used."""
    wait()
    return {"state": "IDLE", "created": []}


def advance(result, tasks, journal, leases, providers, clock, ttl_s=30, max_dispatch=50, max_retries=3):
    """Apply one result. ``clock`` belongs to ``leases``; expiry is read from there."""
    del clock
    steps = ["persist"]
    journal.append(dict(result))
    steps.append("validate")
    if not _valid(result):
        return _report(steps, [], [])
    task = tasks.get(result["task_id"])
    steps.append("contract")
    if task is None or result["status"] != task.get("contract", {}).get("requires"):
        return _report(steps, [], [])
    steps.append("reconcile")
    task["status"] = "DONE"
    steps.append("dependencies")
    for other in tasks.values():
        if other["status"] != "BLOCKED":
            continue
        deps = other.get("depends_on") or []
        if deps and all(tasks.get(dep, {}).get("status") == "DONE" for dep in deps):
            other["status"] = "READY"
    steps.append("ready")
    _reconcile_expired(tasks, leases)
    ready = [item for item in tasks.values() if item["status"] == "READY"]
    steps.append("eligibility")
    steps.append("select")
    steps.append("dispatch")
    dispatched, waiting = _dispatch(ready, journal, leases, providers, ttl_s, max_dispatch, max_retries)
    return _report(steps, dispatched, waiting)


def _valid(result):
    if not isinstance(result, dict):
        return False
    if result.get("status") not in ("PASS", "FAIL"):
        return False
    return all(isinstance(result.get(key), str) and result.get(key) for key in ("result_id", "task_id", "status"))


def _report(steps, dispatched, waiting):
    return {"steps": steps, "dispatched": dispatched, "waiting": waiting}


def _provider_up(providers, name):
    value = providers.get(name, "down")
    if value == "down":
        return False
    if callable(value):
        value()
        return True
    return value == "up"


def _reconcile_expired(tasks, leases):
    """A RUNNING task whose lease is gone is UNKNOWN, not a second execution."""
    for task in tasks.values():
        if task.get("status") != "RUNNING" or "token" not in task:
            continue
        current = leases.current(task["scope"])
        if current is None or current.token != task["token"] or current.holder != task.get("holder"):
            task["status"] = "RECONCILED"
            task["execution"] = "UNKNOWN"


def _open_attempt(journal, task_id):
    opened = False
    for row in journal:
        if row.get("kind") == "dispatch" and row.get("task_id") == task_id:
            opened = True
        if row.get("result_id") and row.get("task_id") == task_id and row.get("status") == "PASS":
            opened = False
    return opened


def _dispatch(ready, journal, leases, providers, ttl_s, max_dispatch, max_retries):
    dispatched, waiting = [], []
    for task in sorted(ready, key=lambda item: item["id"]):
        if _open_attempt(journal, task["id"]):
            task["status"] = "RECONCILED"
            task["execution"] = "UNKNOWN"
            waiting.append({"id": task["id"], "reason": "ATTEMPT_OPEN"})
            continue
        if task.get("retries", 0) >= max_retries:
            waiting.append({"id": task["id"], "reason": "RETRIES_EXHAUSTED"})
            continue
        if len(dispatched) >= max_dispatch:
            waiting.append({"id": task["id"], "reason": "BACKPRESSURE"})
            continue
        try:
            if not _provider_up(providers, task["provider"]):
                task["retries"] = task.get("retries", 0) + 1
                waiting.append({"id": task["id"], "reason": "PROVIDER_DOWN"})
                continue
            lease = leases.acquire(task["scope"], task["holder"], task["id"], ttl_s)
        except LeaseConflict:
            waiting.append({"id": task["id"], "reason": "SCOPE_HELD"})
            continue
        except Exception:
            task["retries"] = task.get("retries", 0) + 1
            waiting.append({"id": task["id"], "reason": "PROVIDER_DOWN"})
            continue
        task["token"] = lease.token
        task["status"] = "RUNNING"
        journal.append({"kind": "dispatch", "task_id": task["id"], "attempt": task.get("retries", 0) + 1})
        dispatched.append(task["id"])
    return dispatched, waiting
