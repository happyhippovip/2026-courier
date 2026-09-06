# KIbey Multi-Model Router & Scope Lock — Quickstart Guide
**Pilot Version:** 1.0.0  
**License:** Single Developer / Production Pilot (€49 License)  
**Verification Fingerprint:** `5098544c46e17e221585210b605ed3020ad3dfdce88d6b646c7ba35a8e480bdb`  

---

## 1. Installation (Zero Dependencies)
Simply place `kibey_router_harness.py` into your agent codebase:
```python
from kibey_router_harness import KibeyRouter

router = KibeyRouter()

# 1. Select optimal worker for subtask
slot = router.route_task("CODE_FORMATTING")  # -> 'CLI_DETERMINISTIC_SLOT'

# 2. Acquire atomic scope lock before file mutation
ok, err = router.acquire_scope_lock("src/core/models.py", owner_id="agent_worker_1")
if not ok:
    print("Locked by another subagent:", err)
else:
    # Safely perform file mutation
    print("Scope lock acquired cleanly.")

# 3. Build cryptographic result proof
proof = router.build_result_envelope(task_id="subtask-101", worker_id="agent_worker_1", output_data={"status": "DONE"})
print("Result Proof Fingerprint:", proof["fingerprint"])
```

---

## 2. Guaranteed Invariants
- Zero unhandled timeout hangs
- Atomic generation-fenced single-builder locks
- Standardized SHA-256 result envelopes
