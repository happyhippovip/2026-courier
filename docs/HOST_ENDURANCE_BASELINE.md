# Host Guardian Endurance Baseline (Issue #76)

Role: independent resource-endurance engineer. The Guardian architecture
(`courier_worker/host.py`, `courier_worker/service.py`,
`scripts/resource_governor.py`, `scripts/host_capacity.py`) is **not**
modified by this package; every file below is additive.

## PR_TESTED

No remote Issue #76 implementation PR exists (verified 2026-10-02:
`gh pr list --search "76"` empty; no `origin/*issue*76*` /
`*host-capacity*` branch). The local slice under test is the untracked
`scripts/host_capacity.py` on branch `feature/issue-76-host-capacity`
at base `e3d785f7`, plus the committed Guardian lanes L2/L3.

## BASELINE_METRICS (Mac, 2026-10-02, observed)

| metric | value |
|---|---|
| owned process count (probe) | 1 + 0 descendants |
| FD count (probe) | 4 (`num_fds`) |
| probe RSS | 10736 KB |
| swap | 17.2/18.2 GB used (94.3%; loaded host) |
| load / cores | 3.5 / 16 |
| repo `logs` / `events` / `runtime` | 0 B / 1.2 MB (194 files) / 4 KB |
| Mac native | `vm_stat` pages-free 5429, `vm.swapusage` used 16412M |
| queue / schedulers / provider sessions | harness-simulated (see soak args) |
| cleanup latency (live probe) | ~1.0 s (1 s timeout + reap; envelope 30 s) |

Soak default run (5000 cycles, 64 slots, seed 76): heap-object slope
0.0 obj/cycle, FD delta 0, live probes TIMEOUT+reaped. Full numbers land in
the workflow artifacts (`summary.json` / `summary.md`).

## LEAKS_FOUND

None in the Guardian slice. Two measurement artifacts were found in the
harness itself during construction and fixed there (not in product code):
RSS-of-harness grows ~1 MB per 20 sampler runs while the pure admission
loop grows 0 KB (verified side-by-side); the harness retains only
first/last samples and scalar series now. A test-side arithmetic slip
(waiting `{2}` not `{4}`) and an over-strict UNKNOWN-health case were
corrected in the tests and the implemented load-norm contract was pinned
instead (`test_known_good_load_may_be_healthy_but_staged`).

## SOAK_HARNESS

- `scripts/soak/baseline_metrics.py` -- observed-only sampler (psutil +
  macOS `vm_stat`/`sysctl`, Windows handle counts; `n/a` where hidden).
- `scripts/soak/soak_host_guardian.py` -- manual/CI-dispatch soak:
  `--cycles` (cap 1M), `--slots`, `--seconds` (7-day ceiling),
  `--cycle-delay-ms` (coalesced, never busy-poll), `--live-probes`
  (bounded real timeout runs), `--seed`, `--out` (default: fresh temp
  dir, never the repo tree).
- `scripts/soak/failure_trend.py` -- per-platform trend report over
  `summary.json` files; Mac and Windows rows are never merged.
- `.github/workflows/host-endurance-soak.yml` -- `workflow_dispatch`
  only (no push/PR/schedule), macos+windows matrix, 20-min timeout,
  artifact upload + trend job. Not a permanent CI burner by construction.

## MAC_PROOF / WINDOWS_PROOF

- MAC_PROOF: local runs on macOS 26.6 (17/17 CI tests green;
  harness PASS=True, obj slope 0.0, fd delta 0).
- WINDOWS_PROOF: pending -- collect via the dispatch workflow
  (Job-Object/handle evidence is native to that run; this doc must not
  infer Windows behavior from the Mac numbers above).

## FILES_CHANGED (all additive)

- `tests/test_host_endurance.py` (17 CI-safe tests, ~4.5 s)
- `scripts/soak/baseline_metrics.py`
- `scripts/soak/soak_host_guardian.py`
- `scripts/soak/failure_trend.py`
- `.github/workflows/host-endurance-soak.yml`
- `docs/HOST_ENDURANCE_BASELINE.md` (this file)

## TESTS

`python3 -m pytest tests/test_host_endurance.py -q` -- 17 passed.
Neighbors: `tests/test_l3_worker_host.py` re-run (same product code).

## MAC01 slice (budgets + hibernation)

- `scripts/host_budgets.py` (new, owned): explicit per-resource budgets
  with emergency reserve; `MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE=1`
  imported from the governor, never redefined; checkpoint-first
  hibernation plan for IDLE/QUOTA_BLOCKED/WAITING_LONG lanes with
  poller-stop on quota exhaustion; mission-state mapping
  (NOMINAL/WATCH/RECOVERING) with fail-closed ValueError on unknown.
- `tests/test_host_budgets.py`: 10 RED-before-GREEN tests.
- `scripts/host_capacity.py` (pre-existing orphan slice) untouched.

## COMMIT / NEXT_RISK

Uncommitted (worktree `feature/issue-76-host-capacity`); commit on owner
request. NEXT_RISK: (1) Windows proof still requires a dispatch run;
(2) real 24h/7d wall-clock soak is owner-scheduled, not CI;
(3) `scripts/host_capacity.py` itself is still untracked -- merging it
needs the Guardian owner's review, not this package.
