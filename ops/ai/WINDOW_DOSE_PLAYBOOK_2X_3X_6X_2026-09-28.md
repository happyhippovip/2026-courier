# Window Dose Playbook — 2x / 3x / 6x — 2026-09-28

Use with:
ops/ai/TURBO_REPEATABLE_CLAIM_LOOP_PROMPT.txt

Principle:
- 2x = probe dose: confirm the pool is still yielding useful unique work.
- 3x = normal work dose.
- 6x = drain dose, only after the pool still reports NEXT_AVAILABLE and before POOL_EXHAUSTED.
- /clear only after the current claim/batch is durably completed or blocked.
- Never /clear mid-claim, mid-source-patch, or mid-physical-run.

Recommended cadence:
Muse Mac: 3x -> clear -> 3x if NEXT_AVAILABLE; then switch muse-mac -> muse when exhausted.
Generic Muse: 2x -> clear -> 2x -> clear -> 2x (6 total) if still productive.
Muse Windows: 2x -> clear -> 2x; add 2x only if NEXT_AVAILABLE.
Google Windows read-only windows: 2x -> clear -> 2x; add 1-2x if NEXT_AVAILABLE.
Google Windows sole writer: 1x at a time; clear only after patch/test/checkpoint/commit boundary.
Google Mac prep windows: 2x -> clear -> 1-2x if NEXT_AVAILABLE.
Mac physical owner: no queued repeat doses during RUN_1/RUN_2; one controlled run prompt at a time.

Stop conditions:
POOL_EXHAUSTED / NO_TASK -> stop that pool.
FAMILY_COMPLETE -> do not repeat.
BLOCKED_OTHER_OWNER -> route away.
Claude/Codex phase change -> stop generic prep and follow the new phase.
Actual RUN evidence exists -> stop template analysis and inspect actual instance.

Dose escalation:
1. start with 2x on a fresh or uncertain pool;
2. if both invocations yield unique useful work, use 3x;
3. only use 6x when the pool is known to have substantial remaining work and claims are deduplicating correctly.

Do not use quota availability as a reason to repeat completed work.
