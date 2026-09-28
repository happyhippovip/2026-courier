# MUSE AUTONOMY SHARD 16 — UNKNOWN Semantics

SHARD=16
STATUS=SHARD_COMPLETE (4 fresh subcases + 1 duplicate-skip, 0 defects, 0 gaps)
CLAIM.c2=elm-triton / HOST=MAC / 2026-09-28
MODE=READ_ONLY_C2, 0 source edits, 0 runs, 0 ledger. CODEX_HIGH_RESULT_CURRENT.md
absent (phase recheck this run) → autonomy shards continue.
SCOPE vs peers: shard-14 covers provider-side UNKNOWN (daemon mapping +
RESULT_STATES gate) — DUPLICATE_SKIP for "server rejects UNKNOWN status";
shard-11 covers cost_class-"unknown" bypass (their S3 + :51) — DUPLICATE_SKIP.
This shard: API unknown-entity handling + independent-work continuation.

## Subcases (server/app.py, current numbering)
- U1 unknown entities → 404, no mutation: Unknown goal :181, unknown worker
  unregister/heartbeat/claim :260/:279/:290, unknown task at verify :498.
  Every branch returns before any state write. Dangerous continuation blocked
  at the boundary. → NO_ISSUE.
- U2 unknown/malformed input → 4xx, never 500: unknown resume target → 404
  (:552, step-None guard); unknown action → 400 (:576); unknown task at result
  → 400 (:428); get_json(silent=True) everywhere degrades to {} → downstream
  4xx. No unguarded dereference on unknown input found on these paths.
  → DISPROVEN (unknown input crashes/misroutes server).
- U3 cost_class "unknown" default skips price arbitration → DUPLICATE_SKIP =
  peer shard-11 S3 (their checkpoint :36-41 + :51), not re-examined.
- U4 empty responses stay debuggable + non-poisonous: claim returns
  {"task": None} with WORKER_BUSY reason where applicable (:~296) vs silent
  None when nothing QUEUED; workers repoll, other goals dispatch (claim loop
  :299-300; isolation REUSE=muse-autonomy-shard-17-H3). → NO_ISSUE.
- U5 unknown/misconfigured authority fails loud: missing env keys → boot
  SystemExit (:14/:17); insecure key values → 503 (:18/:23-24 worker auth,
  :37/:40 verifier auth). Never silently open. → NO_ISSUE (fail-closed).

SUBCASES_DONE=U1,U2,U4,U5 (+U3 DUPLICATE_SKIP shard-11; server-UNKNOWN-status DUPLICATE_SKIP shard-14)
CONFIRMED_SOURCE_DEFECTS=(none)
EVIDENCE_GAPS=(none)
DISPROVEN=U2 (unknown-input crash); U1,U4,U5 closed as NO_ISSUE fail-closed pins
FIX_PACKETS=(none)
NEXT_OWNER=(none — nothing to own)
DO_NOT_REPEAT=muse-autonomy-shard-16-01
