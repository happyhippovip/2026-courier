# MAC-FINISH-12 — Next Ready Dispatch Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-12
- **Area**: NEXT_READY_DISPATCH_PACKET
- **Status**: COMPLETE

Defines automated dependency resolution, queue traversal, and task dispatching logic.

---

## 2. Dependency Resolution Algorithm
```python
def recompute_next_ready(tasks, reconciled_task_ids):
    ready_tasks = []
    for t in tasks:
        if t["status"] != "PENDING":
            continue
        deps = t.get("dependencies", [])
        if all(dep in reconciled_task_ids for dep in deps):
            ready_tasks.append(t)
    return sorted(ready_tasks, key=lambda x: x.get("priority", 999))
```

---

## 3. Dispatch Semantics
- Evaluated synchronously upon each reconciliation event.
- First matching task is marked `READY` and made claimable by worker daemons.
