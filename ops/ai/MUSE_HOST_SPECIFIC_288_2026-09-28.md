# Muse Host-Specific 288 — 2026-09-28

Separate from Google.

- Muse Windows: 144 new read-only QA tasks in pool `muse-windows`
- Muse Mac: 144 new read-only QA tasks in pool `muse-mac`
- Total new host-specific Muse tasks: 288

Use exactly the same prompt in every Muse window:
`ops/ai/MUSE_HOST_SELF_DISTRIBUTING_PROMPT.txt`

The prompt detects Windows vs Mac and claims from the correct pool.

Do not paste the Google universal prompt into these Muse windows unless intentionally using the generic fallback pool.
