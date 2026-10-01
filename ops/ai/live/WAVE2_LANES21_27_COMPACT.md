# WAVE2 lanes 21-27 — compact evidence (parent-persisted, READ_ONLY)

SOURCE=Workflow fan-out "Wave2 Core lanes 21-27 fan-out", completed 2026-09-28.
8 children, all error=null. NOTE: full lane texts were NOT delivered in the
reconciled summary — only compact structured evidence below. Refs are
workflow-internal ("resolved result N"); script for resume held by parent session.
STATUS: 5 lanes complete=true (22,23,25,26,27); 2 partial (21,24).

## Cross-cutting (multi-lane, parent-verified where marked [V])
- HEAD MOVED: fix-cb1-new @ 9dba1505, not e5751783 (lanes 21,22,23,24,25,27) [V: loose ref read]
- GATE_STATE_CURRENT.md ABSENT on disk (lane 21) [V: read failed os-error-2]
- origin/fix-cb1-new = e5751783 → remote-head diverged from local 9dba1505 (21,22,23)
- origin/candidate-b-1 = 34b0a42, moved off BASE; packed-refs stale 4c1e24cc (22)
- origin/evidence/pre-codex-final-34b0a42 remotely pinned (21)
- PRE_CODEX_HANDOFF.md rewritten to 11 lines, FINAL=90dd3956 competing with PROOF_CARD FINAL=3c2aa516 (21,22)
- .git/logs/HEAD: 3c2aa516 was a real local commit (22)
- MAC_RUN_1_BINDINGS.json binds dead 3c2aa516 (21); run_1_mac.sh: no checkout, no SHA check (22)
- EVIDENCE_FINGERPRINT_REPORT.md: 369-valid off-tree paths (21)
- verifier :62-63 unguarded set() pattern persists (21,23,25); per-task catch :145-147 wedges silently (23)
- resume-retry keeps stale result (26: app.py:534-545) [NEW, needs owner look]
- mac daemon run_id = random uuid, unbound (26: mac daemon.py:547) [NEW, needs owner look]
- central_state step-vs-task mirror divergence confirmed (26)
- failure_history: zero hits, contradicts FAILURE_PRESERVATION doc (27)
- sibling files appeared mid-session: ops/ai/live/WAVE2_LANE21_GATE_PROVENANCE.md, ops/ai/live/W4_STALE_DOC_REPORT.md (23)

## LANE_21 Gate provenance audit (complete=false)
EVIDENCE: .git/refs/heads/fix-cb1-new:1 HEAD=9dba1505 | origin/evidence/pre-codex-final-34b0a42:1 review SHA pinned | origin/fix-cb1-new:1 =e5751783 diverged | verifier.py:62-63 unguarded set() | app.py:110-118 plan stored opaquely | PRE_CODEX_HANDOFF.md:1-11 rewrite FINAL 90dd3956 | tests/test_courier_verifier.py ABSENT, HANDOFF cmd ungrounded | GATE_STATE_CURRENT.md ABSENT, 57/1/0 sourceless | PROOF_CARD.md:8 FINAL=3c2aa516 no git ref | MAC_RUN_1_BINDINGS.json:11 dead 3c2aa516 | EVIDENCE_FINGERPRINT:6-14 369-valid off-tree | packed-refs:10,57 BASE 4c1e24cc durable
UNRESOLVED: ancestry 9dba1505 vs 34b0a42/4c1e24cc | git status/dirty + 9dba1505 provenance | Sonnet verdict primary text (transcript-only) | object existence 3c2aa516/90dd3956 | status of be2a394e/3f36fe40 pins

## LANE_22 Candidate convergence (complete=true)
EVIDENCE: HEAD+loose-ref LOCAL=9dba1505 | remotes/origin/fix-cb1-new:1 REMOTE=e5751783 | FETCH_HEAD:1,22,47 corroborates | remotes/origin/candidate-b-1:1 =34b0a42 | packed-refs stale 4c1e24cc | logs/HEAD:195-196 3c2aa516 real local commit | PROOF_CARD:8 FINAL=3c2aa516 | HANDOFF:2 Final=90dd3956 competing | run_1_mac.sh:1-42 no checkout/SHA check | COMMAND_SHEET:12-14 checkout mac-handoff | BINDINGS.json:10-14 FINAL expected vs PENDING | COST_SAFE_POLICY:45-50 durable-source rule
UNRESOLVED: none

## LANE_23 Orphan adoption protocol (complete=true)
EVIDENCE: local HEAD=9dba1505 moved | remote fix-cb1-new=e5751783, local NOT on remote | packed-refs:10 candidate-b-1=4c1e24cc anchor | verifier:62-63 set() live | verifier:145-147 silent wedge | WAVE2_LANE21:6-16 ref map, 3c2aa516/90dd3956 unresolvable | WAVE2_LANE21:30-35 R1-R5 competing-FINALs | W4_STALE_DOC:10-17 pointer flip in-session | WALL_02:23+WALL_03:25 VERDICT_TRANSFER=NONE | MUSE9_M9:6-7 freeze rule | M3:34-36 number-table rule | UA-D01:29-32 evidence levels
UNRESOLVED: none

## LANE_24 Source-vs-runtime attack (complete=false)
EVIDENCE: HEAD=9dba1505 | github_dispatcher.py:44 venv-or-PATH python | start.bat:4 uv-run resolution | app.py:561-562 Flask-dev :8080 vs supervisor gunicorn:23 | crash.log:2 past waitress run | daemon.py:68 + mac:163 ARTIFACT_UPLOAD default-off | app.py:11 STATE_FILE env-or-relative; central_state.json:1-15 live DONE | .gitignore:17-19,93,108-112 ignored-vs-tracked asymmetry | run_1_mac.sh:20 --port/--db ignored (zero argv parsing) | egg-info/requires.txt:1-4 floor-only pins
UNRESOLVED: 9dba1505 ancestry | lockfile absence not exhaustively proven | venv/ on proof host? | central_state.json tracked?

## LANE_25 B auto-dispatch attack (complete=true)
EVIDENCE: app.py:277-282 B gated on head-index+QUEUED | :503-507 only VERIFY PASS advances | :21-30 bearer-only, no actor | :496-501 verify block no timestamp | :329-331 fresh attempt/dispatch on claim | win daemon:320-329,367 idle-poll 10s | mac daemon:489-508,596 idle-poll 5s | verifier:62-63,145-147 pattern persists | contract:114-172 shape-only, no rehash | test_marathon:27-79 legal-sequence only | HEAD=9dba1505 | MUSE9_M7:12-28 witness rule + null-relay gap
UNRESOLVED: none

## LANE_26 Restart/no-replay attack (complete=true)
EVIDENCE: app.py:361-370 dup-guard-before-409 | :534-545 resume-retry-keeps-stale-result | :561-562 no-argparse | :110-118 opaque client task_ids | win daemon:214-223 timeout-never-kills | win daemon:339-358 redeliver-then-unlink | mac daemon:205-211 any-2xx-is-DELIVERED | mac daemon:547 run_id-uuid-unbound | verify_run2:34-38 vacuous substring | run_2:15-20 kill-pid-only | contract:1-172 noop-worker | central_state:9-61 mirror-divergence
UNRESOLVED: none

## LANE_27 Sticky failure semantics (complete=true)
EVIDENCE: app.py:328-334 claim mints attempts/ids, nulls run/result | :367-370 ACK_DUPLICATE vs 409 | :382-392 SUCCESS->RECEIVED; FAILED->QUEUED<3 else TERMINAL | :496-515 verify block; PASS->RECONCILED+1, FAIL->BLOCKED | :530-549 resume from 3 states; force_success refused | contract:138-151 5-field binding | p3_idempotency:62-64 old-attempt 400 after retry | marathon:97-109 resumed_from preserved | verifier:62-68 omission->FAIL | failure_history zero hits | HEAD=9dba1505 | p3_idempotency:84-108 ACK incl failed-resend
UNRESOLVED: none

## Synthesis child
SYNTHESIS_ERROR=null. Synthesis text NOT delivered in reconciled summary (same
limitation as lane texts). Dedupe NOT available — do not claim lanes are deduped.
Omitted scope: full lane documents (8 texts), synthesis document.
