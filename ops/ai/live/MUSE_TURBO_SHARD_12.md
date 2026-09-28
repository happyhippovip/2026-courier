# MUSE TURBO ENDGAME SHARD 12 — RUN_1 Failure-Stickiness (Evidence-Retention)

SHARD=12
CLAIM.c2=elm-triton / HOST=MAC / 2026-09-28. Master prompt ENOENT → fallback table.
CODEX_HIGH_RESULT_CURRENT.md absent → Post-Codex-Paket vorbereitet, kein Vollzug.
READ_ONLY_C2, 0 edits, 0 runs, 0 ledger. Peer MUSE_ENDGAME_FAILED_EXEC.md covers
status transitions (adopted, not repeated); MUSE_TURBO_SHARD_09 taken by peer.
This shard: ONLY evidence retention across retry/resume/terminal (disjoint).

## Subcases (server/app.py, current numbering)
- S1 FAILED→QUEUED keeps failed evidence: :404-406 store failed durable_result;
  :411-413 set only status+worker_id (attempts<3), task["result"] NOT cleared →
  superseded failure persists through the re-execution window until next
  accepted result overwrites :405. Machine consumers safe (pending_verification
  lists only RESULT_RECEIVED); get_goal dumps raw tasks incl. stale result.
  → NO_ISSUE (bounded) + operator-visibility note, no machine path affected.
- S2 claim does not clear: re-claim sets run_id/result_id None (:353-354), never
  task["result"] → same persistence as S1, second endpoint confirmed.
  → NO_ISSUE (same bound as S1).
- S3 resume preserves history: retry sets resumed_from/status/worker_id only
  (resume body) — task["result"] AND task["verification"] survive resume, so a
  resumed task carries superseded failed evidence + old FAIL verdict until a new
  result lands. Verify path itself binds the NEW result (result_id/artifacts
  equality), so no false verdict; readers see history, not corruption.
  → NO_ISSUE (history-preserving by construction; 015-R1 replay-ACK cited, not redone).
- S4 terminal retention: 3rd FAILED → FAILED_TERMINAL + goal BLOCKED (:414-415,
  :425-426); only resume exits (precondition :557). Last failed evidence
  retained permanently unless resumed. → NO_ISSUE (stickiness holds terminally).

FILES=server/app.py:404-406,411-415,425-426; claim :353-354; resume body
(retry sets 3 fields only); verify binding; get_goal raw dump.
CAUSAL_RISK=Superseded-failure visibility window (operator-facing only; no
machine consumer reads result outside RESULT_RECEIVED).
MIN_FIX=(none — no defect; IF owner ever wants it: clear task["result"] on
requeue, one line, behavior change — NOT proposed here).
MIN_TEST=(future, unexecuted): status-gated read test — verifier ignores
non-RECEIVED results; get_goal marks superseded payloads. Post-Codex packet.
EVIDENCE=This checkpoint + cited lines; peer FAILED_EXEC adopted for transitions.
OWNER=CENTRAL_WRITER (future test only; nothing to fix now).
BEFORE_RUN1=Packet-Kenntnis (RUN_1 witness must not mistake a superseded
QUEUED-window failure for current evidence). No code gate.
DO_NOT_REPEAT=muse-turbo-shard-12-01 (+ peer failed-exec-01 adopted).
STATUS=SHARD_COMPLETE (single shard per order; no second shard taken).
