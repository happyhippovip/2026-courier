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


def advance(result, tasks, journal, leases, providers, clock, ttl_s=30):
    """Apply one result. ``clock`` is accepted so the caller shares the lease clock."""
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
    ready = [item for item in tasks.values() if item["status"] == "READY"]
    steps.append("eligibility")
    steps.append("select")
    steps.append("dispatch")
    dispatched, waiting = _dispatch(ready, leases, providers, ttl_s)
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


def _dispatch(ready, leases, providers, ttl_s):
    dispatched, waiting = [], []
    for task in sorted(ready, key=lambda item: item["id"]):
        try:
            if not _provider_up(providers, task["provider"]):
                waiting.append({"id": task["id"], "reason": "PROVIDER_DOWN"})
                continue
            leases.acquire(task["scope"], task["holder"], task["id"], ttl_s)
        except LeaseConflict:
            waiting.append({"id": task["id"], "reason": "SCOPE_HELD"})
            continue
        except Exception:
            waiting.append({"id": task["id"], "reason": "PROVIDER_DOWN"})
            continue
        task["status"] = "RUNNING"
        dispatched.append(task["id"])
    return dispatched, waiting
