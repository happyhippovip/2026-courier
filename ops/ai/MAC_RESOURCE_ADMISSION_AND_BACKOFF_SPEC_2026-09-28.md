# Mac Resource Admission & No-Tight-Polling Specification — 2026-09-28

**Task ID**: PPREP-07  
**Authority**: GOOGLE_CLI (Mac 100x Universal Worker)  
**Status**: 100% PROVEN  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  

---

## 1. Objective

Define deterministic compute safety, concurrency enforcement, and idle backoff protocols for continuous autonomous operation on macOS.

---

## 2. Resource Admission Protocol

### Guard 1: Concurrency Cap (`MAX_HEAVY_JOBS=1`)
- Physical execution slots (e.g. running server, executing extensive pytest suites, physical canary runs) must acquire exclusive file lock `/tmp/courier_heavy_job.lock`.
- If lock is held by another process:
  - Do NOT spawn a second heavy job.
  - Return immediately with `RESOURCE_WAIT / HEAVY_JOB_BUSY`.
  - Sleep backoff for 10 seconds before re-checking.

### Guard 2: Memory & Swap Safety
- Before launching heavy child processes:
  - Check free memory via `vm_stat` or Python `psutil`/system call.
  - Require minimum 1.0 GB uncompressed free RAM.
  - If memory < 1.0 GB:
    - Fail closed.
    - Log `INSUFFICIENT_MEMORY_GUARD`.
    - Do NOT launch subprocess.

### Guard 3: Disk Space Safety
- Require minimum 2.0 GB free disk space on root volume (`df -h /Users/user`).
- If disk space is exhausted, halt immediately to prevent corrupted state writes.

---

## 3. No-Tight-Polling & Idle Backoff Specification

To eliminate token and CPU waste during periods of work exhaustion:

1. **Active Queue Processing**:
   - Interval between task claims: 0ms (continuous pipelining).
2. **Empty Queue Backoff**:
   - When `CURRENT_UNWORKED_QUEUE_SIZE=0` and no unharvested results exist:
     - Worker must NOT poll in an unconstrained loop.
     - Worker must enter `TRUE_IDLE` state.
     - Polling interval backs off: 10s -> 30s -> 60s -> 300s (max 5 minutes).
3. **No Busywork Rule**:
   - Zero LLM prompts or synthetic tasks generated merely to keep workers busy.
   - Genuine idle is recognized as valid, cost-saving operational state.
