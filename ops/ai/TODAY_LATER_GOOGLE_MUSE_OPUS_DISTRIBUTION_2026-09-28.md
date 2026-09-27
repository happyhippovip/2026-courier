# TODAY / LATER — Google + Muse + Opus Distribution Pack — 2026-09-28

## Google Windows normal
Recommended: 8-14 logical windows when enough READY work exists.
Use:
ops/ai/GOOGLE_WINDOWS_TODAY_REUSABLE_WORKER_PROMPT.txt

Good split:
- 3 Ledger/deterministic
- 2 non-candidate/cross-host
- 2 cache/proof-packet
- 1 claim/lease
- 1 persistence
- 1 motor/reconcile
- 1 human-gate/routing
Scale only with real unclaimed tasks.

## Google Mac normal
Recommended: 6-10 windows.
Use:
ops/ai/GOOGLE_MAC_TODAY_REUSABLE_WORKER_PROMPT.txt

Good split:
- 2 runtime/isolation
- 2 RUN prep
- 2 restart proof
- 1 Core Freeze
- 1 human-relay/autonomy
- 1 proof packet/cross-host
- 1 pilot metrics only when higher-priority work is exhausted

## Muse later
Recommended: 4-6 windows.
Up to 8 only with distinct C2 claims.
Use:
ops/ai/MUSE_LATER_REUSABLE_REVIEW_WORKER_PROMPT.txt

Good split:
- 2 Ledger adversarial
- 1 false-green
- 1 cross-provider
- 1 restart/core-freeze QA
- 1 carryover/general QA
- optional privacy/shared-capability only after critical proof work

## Opus 4.6 Windows
Recommended: 3-4 windows normally.
Short burst: 5-6 if distinct C4 claims remain.
Use:
ops/ai/OPUS46_WINDOWS_TODAY_REUSABLE_WORKER_PROMPT.txt

Priority:
Ledger convergence -> Elite decisions -> O49/O50/O52 -> O51/O53.

## Opus 4.6 Mac
Recommended: 2-3 windows.
Maximum 4-5 for a short burst with distinct MOP claims.
Use:
ops/ai/OPUS46_MAC_TODAY_REUSABLE_WORKER_PROMPT.txt

Priority:
MOP physical-proof convergence -> proof/user-trust/restart semantics.

## Global
MAX_HEAVY_JOBS=1 per host.
Do not derive window count from free accounts alone.
FAMILY_COMPLETE != GLOBAL_TRUE_IDLE.
Same durable fingerprint/result is never paid twice.
Provider limit is classified once; do not repeatedly probe.
