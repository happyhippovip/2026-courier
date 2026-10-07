# WAVE 2 — Lane 21: Gate provenance audit (READ_ONLY, PRIVATE — do not publish)

Status: PRIVATE. Critical path respected (candidate reconciliation first).
No source touched, no RUN, no Ledger, no gate re-review. Reuse-first; only new reads.

## Provenance table (FACT unless tagged)

| # | Gate claim | Traced source (fresh read) | Class |
|---|---|---|---|
| C1 | PRE_CODEX_STATE=VALIDATED_LOCAL_GREEN, AUTHORITATIVE_READY=YES, NEXT=AWAIT_MAC_CANARY | `ops/ai/GATE_STATE_CURRENT.md` — FILE GONE (glob 2026-09-28/29); survives only as citations in UA/MUSE9 docs | UNSUPPORTED |
| C2 | 57 passed / 1 skipped / 0 failed (targeted) | Same deleted file; NO transcript/log in repo; suite .py files exist | UNSUPPORTED + STALE (tree moved to 34b0a42) |
| C3a | FINAL_SHA=3c2aa51… | String in HANDOFF + PROOF_CARD (both exist); NO git ref (packed-refs grep clean); NO loose object (UNKNOWN: packed-or-absent) | LOCAL_ONLY string; commit UNSUPPORTED |
| C3b | BASE_SHA=4c1e24cc (candidate-b-1) | `packed-refs:10` heads + `:57` origin — same SHA both sides | DURABLE |
| C4 | SONNET BLOCKED on 34b0a42 (verifier defect) | WALL_02 worker report (accepted) + own re-anchor reads; review SHA == HEAD ref | LOCAL_ONLY (report + loose ref; no remote anchor) |
| C5 | 12/12 cases PROVEN | HANDOFF exists; evidence pointers → `c:\Users\lol\courier_work\…` (outside repo, never verified here) | LOCAL_ONLY doc; evidence UNSUPPORTED; STALE (old tree) |
| C6 | TRUE_IDLE, awaiting Mac canary | WALL_QUEUE_CURRENT.md exists; consistent with no-RUN-logs observation | LOCAL_ONLY |
| C7 | RUN prep complete | RUN_PREP doc exists; harness breaks known (M7/M8); script freshness UNKNOWN (not re-read) | LOCAL_ONLY |
| C8 | HEAD=fix-cb1-new@34b0a42 | `.git/HEAD` + loose ref (fresh); NO packed/remote ref; ref demonstrably mutable (just moved) | LOCAL_ONLY |
| C9 | Operator 28/1/1 | Transcript only, no artifact in repo | LOCAL_ONLY (unverifiable) |
| C10 | Proof level SYNTHETIC_PRE_CODEX | PROOF_CARD exists, self-declared | LOCAL_ONLY (consistent) |
| C11 | PILOT READY (pending authorization) | PILOT_READINESS_DECLARATION exists BUT contradicted by repo state (no dummy file, no RUNs ever) | LOCAL_ONLY + contradicted |

INFERENCE (not FACT): worktree tracks the ref move (verifier shape + dispatched_at + gate file all changed together) → real checkout, not bare ref edit. Mixed-tree residue remains UNKNOWN (needs git owner).
UNKNOWN (shell-less, each needs one git command): packed-ness of 3c2aa51/e5751783; `git status` (dirty?); ancestry 34b0a42↔4c1e24cc; any origin ref for fix-cb1-new.

## 5 highest-risk claims

1. C1 — Phase truth has no source file. WHY: every window/orchestrator citing gate state now cites a deleted file; citations rot silently. VERIFY: writer restores or formally supersedes the gate file (1 durable write).
2. C3a — FINAL_SHA floats. WHY: the candidate other lanes froze around has no commit anchor; nothing proves it ever existed here. VERIFY: `git cat-file -t 3c2aa51` + reachable ref, or formally retire the SHA.
3. C2 — 57/1/0 is orphaned counts. WHY: quoted as green while its source is gone and its tree is gone. VERIFY: datierte Primär-Reports an einen SHA binden (M3-S2), oder als STALE markieren.
4. C4 — BLOCKED is live but anchor-fragile. WHY: verdict now sits exactly on HEAD (good) via a loose ref + report only (fragile); ref moved once already. VERIFY: remote/packed anchor for the reviewed commit + writer fix for the re-anchored defect shape.
5. C5 — 12-case PROVEN rests on external paths. WHY: passes review-by-citation; pointers leave the repo and the tree. VERIFY: evidence bundle with hashes inside the repo (UA-G01), or downgrade to LOCAL_ONLY.

## Lane close
No other lane's verdict changed by this audit (provenance only, no re-review).
NEXT_OWNER: SOLE_WINDOWS_WRITER (C1 restore/supersede; C3a retire-or-anchor; C4 fix) + GIT_OWNER (UNKNOWNs, one command each).
