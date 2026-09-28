# MAC08 Resource Preflight — CPU/RAM/swap/disk/port/heavy-job + polling

Slot: MAC08_RESOURCES (unique C2 claim, resource admission).
Host: Mac, repo `/Users/user/Downloads/2026-courier`, HEAD `bd539f18`.
MAX_HEAVY_JOBS=1. No boot, no kills, no ledger writes.

## Evidence (observed)

- CPU: 16 cores; loadavg 8.36/13.09/11.78 → FAIL vs required <4.0. Physical boot NOT cleared.
- RAM: free+inactive+speculative = 5843 MB → PASS vs required 1500 MB.
- Swap: `vm.swapusage` total=0M/used=0M (encrypted, no swap file) — noted, not gated.
- Disk: /tmp avail 601165 MB → PASS vs required 5 GB (same volume as repo).
- Ports: :8080 occupied by foreign PID 606 (protected); :8081 free (precondition holds).
- Heavy job: `/tmp/courier_heavy_job.lock` absent, `/tmp/courier_run*` absent → lane free, nothing held.
- Polling/backoff: `scripts/run_physical.py:85-91` + `run_physical_restart.py:95-99` use
  `time.sleep(0.05)` — below the `sleep 1` minimum in `NO_TIGHT_POLLING_AUDIT.md`.
  Writer-owned finding, no patch (source freeze + foreign lane).

## Result block

TASK_ID=MAC08_RESOURCES
FAMILY=resource-admission
STATUS=PREP_DONE / BOOT_BLOCKED_ON_LOAD (8.36 > 4.0)
RESULTS_REUSED=RESOURCE_ADMISSION.md + NO_TIGHT_POLLING_AUDIT.md (read as contract)
FINDING=RAM/disk/ports/heavy all green; load red; 50ms-polling flagged to writer
MISSING_EVIDENCE=post-load-drop re-check (only valid at boot time)
NEXT_EXACT_ACTION=re-check `sysctl -n vm.loadavg` immediately before any RUN_1 boot; do not boot while >4.0
DO_NOT_REPEAT_FINGERPRINT=MAC08-resources-20260928-bd539f18
