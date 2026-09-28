# Hard No-Idle Operator Layer — 2026-09-28

The durable supervisor was fixed in scripts/run_autonomous_supervisor.py so --sleep persists across temporary empty queues.

Interactive/model workers:
- Mac Google: ops/ai/MAC_GOOGLE_HARD_NO_IDLE_FINISHER_PROMPT.txt
- Muse: ops/ai/MUSE_HARD_NO_IDLE_DAY_WALL_PROMPT.txt
- Mac agy relauncher: scripts/relaunch_agy_prompt_loop.sh

Mac example:
MAX_HOURS=8 bash scripts/relaunch_agy_prompt_loop.sh ops/ai/MAC_GOOGLE_HARD_NO_IDLE_FINISHER_PROMPT.txt

Prompt text alone cannot guarantee that an external CLI process remains alive after a model return. The relauncher closes that operational gap.

MAX_HEAVY_JOBS=1 remains required.
