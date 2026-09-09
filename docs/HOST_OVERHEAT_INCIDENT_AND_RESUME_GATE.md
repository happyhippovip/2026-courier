# Host Overheat Incident and Courier Resume Gate

## Status

**COURIER PRODUCTION WORK IS BLOCKED UNTIL THIS GATE IS SATISFIED.**

This document is a permanent operational memory for the Courier project. It records the host-overheating/runaway-process incident, the known technical gaps, the required permanent controls, and the exact proof required before normal Courier production work may resume.

## Why this is a hard blocker

A Courier/AI workload must never be allowed to destabilize or endanger the host computer through unbounded runtime, uncontrolled concurrency, orphaned subprocesses, or repeated heavy redispatch.

**Host safety outranks task throughput and ordinary approval flow.** Human approval to run work is not permission to run unbounded compute or ignore resource risk.

Canonical rule:

`HOST_RISK -> STOP_NEW_HEAVY_WORK -> DIAGNOSE -> FIX -> PROVE -> VERIFY_STABLE -> RESUME`

If proof is incomplete:

`FAIL_CLOSED / NO COURIER PRODUCTION RESUME`

## Incident facts already established

- Host: MacBook Pro 16-inch, 2019, Intel Core i9, 8 cores, 16 GB RAM.
- The Mac became abnormally hot during recent Courier/Gemini/CLI development work despite very large free disk space.
- A prior Courier test/redispatch path was verified to have remained active for many hours because of an infinite-loop class of bug.
- A bounded real-worker canary later proved the truth-first verifier could reject a falsely claimed filesystem effect and fail closed without recursive redispatch.
- A later live process inspection found stale/long-running Courier/Antigravity-related processes, including an `agy` process and stale debugger/log-following tasks. After proven leftovers were terminated, the stuck Antigravity task indicators cleared and host load fell.
- This makes runaway/stale software work a credible cause of the severe heat incident, but the permanent protection must be proven before declaring the system safe to resume.

## Current code-audit findings that must be resolved

The latest independent code audit identified these remaining risks:

1. `FounderModeMVP.run_autonomous_loop()` contains an unbounded `while True` path without a global step or wall-clock budget.
2. Worker-unavailable recovery can be revived repeatedly by changing evidence and lacks a total cooldown/retry ceiling.
3. Discovery and verification can be accidentally marked heavy because duplicate `is_heavy` keys allow the later value to win.
4. CLI1 may unexpectedly fall back to broad/full test discovery.
5. Native AGY has configurable timeout but no hard maximum ceiling.
6. Native AGY stdin is not consistently closed despite comments implying it is.
7. Post-timeout `proc.wait()` needs its own bounded secondary wait.
8. CLI1 and Codex heavy subprocesses lack uniform process-session/process-group isolation.
9. Some lightweight git inspection subprocesses lack timeouts.
10. Gemini adapter must pass exact `mission_id`, `task_hash`, and retry number into the heavy-process supervisor.
11. The heavy-job guard must not exist only as an in-process counter; it must prevent concurrent heavy jobs across separate Courier/CLI processes.
12. Heavy-process ownership metadata must survive Courier crashes/restarts sufficiently to detect stale owned work.
13. Cleanup must prove owned descendants are gone after TERM/KILL escalation; a single scan is insufficient.
14. Popen/spawn failure must release any acquired heavy-job lock/lease safely.
15. Runtime resource sampling must have an actual policy response; merely sampling and doing `pass` is not protection.
16. Heavy-job forensic logs must live in a durable Courier-owned path, not a temporary Antigravity session path.
17. Undefined or stale references such as `proc.returncode` after supervisor refactoring must be eliminated.
18. Full-suite and broad-test execution must never be an implicit fallback after a small change.

## Permanent architecture requirements

### A. One durable heavy-process supervisor

There must be one canonical supervisor used by all Courier-controlled heavy work:

- Gemini / AGY
- CLI1 heavy jobs
- Codex-through-Courier
- large Python/unit test runs
- full regression suites
- any subprocess-backed engineering work classified heavy

The supervisor must enforce:

`MAX_HEAVY_JOBS = 1`

This invariant must hold across separate Courier/CLI processes, not only inside one Python interpreter.

### B. Durable ownership record

Before spawn, record at minimum:

- mission_id
- task_hash
- worker
- PID when available
- PGID/session
- command fingerprint
- start time
- hard deadline
- retry number
- ownership/lease identity
- terminal cleanup state

The durable record must support safe stale-owner recovery after crash/restart.

### C. Process isolation and timeout

Every heavy child must use:

- `stdin=DEVNULL`
- `start_new_session=True` or equivalent safe process-group isolation
- finite timeout
- enforced maximum timeout ceiling

Timeout sequence:

1. Record `TIMEOUT`.
2. Send `SIGTERM` only to the exact Courier-owned PGID.
3. Wait a short bounded grace period.
4. If still alive, send `SIGKILL` only to that owned PGID.
5. Re-scan the owned tree.
6. Record `CLEAN` or `ORPHANS_REMAIN`.
7. If an owned orphan remains, block new heavy work.

Never use broad cleanup commands such as `pkill python`, `killall python`, `pkill node`, or `killall agy`.

### D. Bounded autonomous execution

No production loop may remain unbounded.

The founder/autonomy loop must have both:

- a maximum step/dispatch budget, and
- a total wall-clock budget

Repeated-state fingerprints must prevent identical planner/availability states from reviving the same work forever.

Failure/retry paths must eventually become a truthful terminal state such as:

- `FAILED`
- `BLOCKED`
- `RESOURCE_GUARD`
- `COOLDOWN_REQUIRED`
- `HUMAN_GATE`

### E. Resource-pressure policy

Before heavy work, take a lightweight host snapshot.

During heavy work, sample lightly.

A short CPU spike is not itself failure. Sustained abnormal pressure or known runaway behavior must block **new** heavy work and keep current execution bounded by timeout.

Do not claim CPU temperature without a real supported sensor reading.

### F. Test policy

Targeted tests first. Full regression only with explicit approval, a hard timeout, and no concurrent heavy job.

Implicit fallback from a targeted test to full-suite discovery is forbidden.

## Exact targeted proof required

Before Courier production resumes, all of the following must pass:

1. **Timeout child**: a long-running owned child exceeds timeout and is gone afterward.
2. **Process-tree cleanup**: an owned parent that spawns a child is fully cleaned by PGID ownership.
3. **Global concurrency**: Heavy Job A active -> Heavy Job B is rejected before spawn, including when attempted from a separate process.
4. **Finite retry**: repeated failure reaches a finite cap and cannot redispatch forever.
5. **Unrelated-process safety**: an unrelated external process survives cleanup unchanged.
6. **Normal success**: a short normal heavy job succeeds and records `CLEAN`.
7. **Identity propagation**: exact mission ID, task hash, worker, and retry number reach the durable supervisor record.
8. **Crash/stale record recovery**: stale ownership after simulated crash does not permit unsafe concurrency and can be resolved fail-closed.
9. **Spawn-failure cleanup**: failed `Popen`/spawn does not leave the heavy-job lease stuck.
10. **TERM -> KILL escalation**: graceful termination is attempted first and bounded hard kill is used only when needed.
11. **Founder-loop budget**: maximum step/wall-clock budget stops an otherwise repeatable loop.
12. **Repeated-state guard**: unchanged planner/availability state cannot revive work indefinitely.
13. **No broad-suite fallback**: CLI1 targeted execution cannot silently become full test discovery.
14. **Existing truth-first invariants**: task_hash, canonical verification, and fail-closed behavior remain intact.

## Dual-agent coordination while blocker is active

### Google/Antigravity on Mac

Role: live host/process validation and implementation review on the actual Mac.

Must inspect:
- current CPU/process state
- stale Courier-owned descendants
- process ownership
- host load after cleanup
- whether resource protection behaves as implemented

Must not start unrelated Courier production work before the gate passes.

### Codex

Role: independent code audit, patch review, bounded test design, and verification of the permanent supervisor architecture.

Must independently verify:
- all heavy execution entry points
- all timeout/retry gaps
- durable global concurrency
- ownership/cleanup correctness
- bounded founder loop
- no implicit broad-test fallback

The two results must be reconciled before resume. One agent declaring "fixed" is insufficient without proof against this document.

## Resume gate

Courier production may resume only when there is concrete evidence for all of the following:

- no current runaway or stale Courier-owned heavy process
- global `MAX_HEAVY_JOBS = 1` proven across processes
- every heavy execution path uses the same durable supervisor or an explicitly proven equivalent
- finite timeout ceilings
- bounded retries and autonomous loops
- exact process-tree ownership
- TERM/KILL cleanup proof
- no owned orphans after completion/timeout
- unrelated processes are never killed
- targeted tests all pass
- existing truth-first verification still passes
- Mac remains stable at low load for an observation period after the fix

If the Mac remains abnormally hot at low software load after software cleanup, stop Courier work and move to host/hardware diagnostics rather than continuing to stress the machine.

## Operational memory rule

Any future agent working on Courier must read this document and `docs/COMPUTE_RESOURCE_SAFETY_POLICY.md` before changing heavy execution, retries, worker routing, subprocess handling, or autonomous loops.

This incident is a **system-safety precedent**. Throughput, convenience, and ordinary approval never override the host-protection gate.