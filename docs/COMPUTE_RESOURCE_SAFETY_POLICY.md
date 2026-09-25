# Compute Resource Safety Policy

## Purpose
Prevent Courier, Gemini, Codex, CLI1, tests, or subprocess-backed work from damaging availability of the host computer through runaway execution, uncontrolled concurrency, orphaned children, or sustained resource abuse.

This policy is a **hard safety invariant** and applies before normal production work continues.

## Priority rule
**Host safety outranks task throughput.**

If there is credible evidence that a Courier-controlled workload is overheating, freezing, or destabilizing the host, Courier must stop starting new heavy work and enter a safe bounded state until the cause is diagnosed.

Human approval to continue a task does **not** override this guard. Approval is necessary for human-gated actions, but it is not permission to run unbounded compute or risk the machine.

## Hard invariants

1. **MAX_HEAVY_JOBS = 1** across all Courier-controlled heavy work.
2. No unbounded loops, retries, redispatch, waits, polling, or subprocess execution.
3. Every heavy subprocess must have a real wall-clock timeout.
4. Every heavy subprocess must have explicit process ownership metadata: mission_id, task_hash, worker, PID, process group/session, command, start time, timeout, retry count.
5. Timeout/failure must terminate only the Courier-owned process tree, never unrelated user processes by broad name matching.
6. After completion/failure/timeout, Courier must verify that its owned child processes are gone.
7. If an owned orphan remains, no new heavy job may start. Enter `ORPHAN_PROCESS_DETECTED` / `RESOURCE_GUARD` or equivalent.
8. Retries must be finite and eventually reach a truthful terminal state such as `FAILED`, `BLOCKED`, `RESOURCE_GUARD`, `COOLDOWN_REQUIRED`, or `HUMAN_GATE`.
9. Full regression suites require explicit approval, must be bounded, and may not overlap another heavy job.
10. Prefer targeted tests and lightweight verification after small changes.
11. Do not alter fan control, macOS power management, firmware, kernel/security settings, or install monitoring software without explicit human approval.
12. Do not claim CPU temperature unless a real supported sensor reading was actually obtained.

## Preflight guard before heavy work
Before starting any heavy job, Courier should collect a lightweight host snapshot using built-in tools when available:
- timestamp
- load average / CPU summary
- memory pressure
- currently active Courier-owned heavy jobs
- known Courier-owned descendants/orphans

If another heavy job is active or an owned orphan exists, do not start the new job.

## Runtime guard
While a heavy job runs, sample resource state lightly. A brief CPU spike is not itself a failure. If sustained abnormal pressure or runaway behavior is detected, block new heavy jobs and keep the current execution bounded by its timeout. Use a clear state such as `RESOURCE_GUARD` or `COOLDOWN_REQUIRED`.

## Cleanup rule
Never use broad commands such as `pkill python`, `killall python`, `pkill node`, `killall agy`, or equivalent name-only termination logic for cleanup. Cleanup must be based on recorded ownership of the exact Courier-started process tree.

## Test requirements
Targeted tests must prove at minimum:
- long-running child times out
- parent + child tree is cleaned
- second heavy job cannot overlap first
- retries terminate after a finite number of attempts
- unrelated process is not killed
- short normal job still succeeds
- existing truth-first / task_hash / fail-closed invariants remain intact

## Incident lesson
A prior Courier-related test/redispatch path remained active for many hours and caused severe host heat. This class of failure is treated as a system safety defect, not merely a performance issue.

## Canonical decision rule

`HOST_RISK -> STOP_NEW_HEAVY_WORK -> DIAGNOSE -> CLEAN_OWNED_PROCESSES -> VERIFY_STABLE -> RESUME`

If exact process ownership or safety cannot be established:

`FAIL_CLOSED / NO NEW HEAVY JOB`
