# MUSE AUTONOMY SHARD 05 — Opportunity Queue Dedupe (read-only C2)

SHARD=05
STATUS=COMPLETE
OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T14:40Z
GATE=DURABLE/READY (reused read; no revalidation). No executions, no source edits.
Reads (bounded): run_academy.py:271-286+292-345, invoice_generator.py:20-60,
dashboard/server.py:111-136, run_thought_curator.py:132 (signature), claim path (reuse).
SUBCASES_DONE=5
CONFIRMED_SOURCE_DEFECTS=1:
- S3 invoice-seq TOCTOU (scripts/invoice_generator.py:28-30,52-54): invoice_id =
  glob-count+1, then plain open('w'). Concurrent/retry generation yields identical
  invoice_id; second write silently overwrites first (one invoice lost, numbering
  gap or silent replace). No lock, no existence check, no fsync.
EVIDENCE_GAPS=2:
- S4 per-opportunity single-invoice policy unknown: same opportunity_id spawns N
  invoices (DRAFT_SIMULATION lane); no evidence 1:1 is intended. MISSING_EVIDENCE.
- S5 idea-handoff receiver idempotency: deliveries carry uuid each (redelivery =
  new record); curator dedupe unverified this shard. MISSING_EVIDENCE.
DISPROVEN=2:
- S1 core double-execution via claim (QUEUED-only + single claimant; HNI-10 reuse).
- S2 academy lesson double-create (exists-guards run_academy.py:301/450/494/552).
FIX_PACKETS=1:
  FILES=scripts/invoice_generator.py
  CAUSAL_BUG=count-then-write race on invoice_id (glob len + non-atomic create)
  MIN_FIX=atomic create (O_EXCL/x-mode) + retry-with-next-seq on exists; fsync
  before return. (Text-only proposal; NOT applied — READ_ONLY.)
  TARGETED_TEST=two-process same-prospect generation → distinct files, no overwrite.
  OWNER=revenue/commercial lane (NOT courier core, NOT codex path).
  LATER (candidate-independent commercial tooling; DRAFT_SIMULATION status).
NEXT_OWNER=revenue-lane owner (S3 packet) + curator owner (S5).
DO_NOT_REPEAT=sha256-muse-shard05-opp-dedupe-20260928 (+ session fingerprints).
