# Windows Sleep Autopilot — 2026-09-28

Purpose: let Windows Google CLI workers continue overnight without treating the current FINAL_SHA durability blocker as global idle.

Prompt:
ops/ai/GOOGLE_WINDOWS_SLEEP_AUTOPILOT_PROMPT.txt

Recommended logical slots:
- 6-10 conservative
- 10-16 good when unique READY claims exist
- 20+ only if the durable queue actually exposes that many unique tasks
- MAX_HEAVY_JOBS=1 on the Windows host

Current gate behavior:
WAIT_FOR_HUMAN_SHA_PUSH is a family-local parked blocker.
Only one Gate Durability owner.
Other slots continue unrelated legal work.
Do not repeatedly probe FINAL_SHA 34b0a4264bf763bc2a78f761ffba36e47706b2cf until invalidated by a new durable ref/state.

Wake human only for a real global gate or proven GLOBAL_TRUE_IDLE.
