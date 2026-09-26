# Demo Storyboard (proof-gated: shoot only after Gate 3 PASS)

## Purpose

A 3–5 minute video + captioned stills for `/approach#demo` that turns the physical A→B proof into the site's centerpiece. Storyboard is ready now; recording waits for real evidence. A fixture-driven or narrated mock is FORBIDDEN as a stand-in (plan §8: fixtures may prepare, never prove; blueprint: no fake dashboards).

## Scenes

1. **Setup (30s):** real goal, real Goal Contract on screen (sensitive parts redacted), timestamp visible. Caption: goal + contract fingerprint.
2. **Task A runs (45s):** worker executes; status board shows RUNNING → result arrives. No human input on screen; clock visible to show unattended continuation.
3. **Automatic handoff (30s):** verification + reconciliation indicators, Task B becomes READY and dispatches — highlight the moment NO prompt is typed, NO worker is picked, NO result is pasted. On-screen counter: HUMAN_RELAY_COUNT = 0.
4. **Task B completes (45s):** DONE + proof card appears (goal, result, checks, evidence IDs, unknowns, interventions: 0).
5. **Restart kicker (30s, only after Gate 4 PASS):** kill/restart the process mid-scene, show deterministic resume — or cut this scene entirely.
6. **Close (15s):** "This ran once, on [date], on [source/runtime fingerprint]. Next runs may differ — that's what the evidence section tracks."

## Honesty rules for the video page

- Date + source/runtime fingerprint in the caption; "one recorded run, not a guarantee."
- No splicing that hides waiting time dishonestly (time-lapse must be labeled with real elapsed time).
- Redact personal/secret data; never show keys, passwords, or private pilot content.
- Stills double as the "product proof" screenshots (blueprint build order step 4) — only from this recording, never mockups.

# Download Page + Waitlist (file 07 note: download stays DRAFT)

## DOWNLOAD_PAGE_STRUCTURE — DRAFT, UNPUBLISHED (Gate 7 LOCKED)

Planned structure only: one page, `/download`, with: supported platforms (TBD — no claim now), version + source/build/runtime identity per release (plan §22), install steps, update/rollback notes, "last known good" pointer, checksum verification. Every line currently HOLD. Publishing requires: reproducible build + identities + single-instance + safe update/rollback + state compatibility (plan §22). Until then the route must not exist publicly.
