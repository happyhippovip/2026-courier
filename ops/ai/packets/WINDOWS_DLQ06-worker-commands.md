# WINDOWS WORKER COMMANDS — DLQ-06 50-cycle collision + evidence handoff (Mac-prepared)

CURRENT_HEAD=5a8befb7b19a436a8ded2dd619c7ea32645023c2
EXPECTED_WINDOWS_SHA=UNKNOWN (Mac does not observe Windows; re-observe on worker)
TASK=Execute the real (non-mocked) DLQ-06 concurrency collision on the Windows
worker and return raw evidence. Companion to
ops/ai/packets/WINDOWS_DLQ06-race-prep.md (behavioral design) — this file holds
the worker-execution half. No Windows claims are made here.

COMMANDS (Windows worker, exact-SHA worktree, production ledger path):
1. Baseline: python -m pytest tests/test_windows_ledger_race.py -q
   (expect 2 failed / 1 passed pre-fix — the mocks; record output verbatim).
2. Real collision, 50 cycles: Loop A `while($true){ python -c "from
   scripts.agent_handoff_ledger import load_bundle; load_bundle('agent_handoff_ledger.json')" }`;
   Loop B runs the motor --once iteration concurrently. Capture every
   PermissionError/OSError traceback verbatim with cycle index.
3. Post-fix repeat of (2) after Google lands the PermissionError-only retry;
   the behavioral tests must flip green in the same commit.

PRECONDITIONS=Reviewed deployable SHA checked out; canonical ledger path (not
a copy); NO mocks/shims on worker (mock coverage already exists Mac-side);
OS-owned worker identity (no interactive-agent ownership).
PROCESS_IDENTITY_CHECK=OS-owned identity observed and recorded.
RUNTIME_SHA_CHECK=Worker-reported SHA must equal deployed SHA.
STATE_PATH=Worker-local agent_handoff_ledger.json.
TEST_INPUT=50 real concurrent read/write cycles + mocked behavioral suite.
EXPECTED_OUTPUT=Pre-fix: WinError-32-style PermissionError on reader or writer
(no retry in current code). Post-fix: zero crashes, behavioral suite green.
RAW_EVIDENCE_REQUIRED=Full tracebacks, cycle count, SHA + identity report —
verbatim, never summaries-as-proof.
FAIL_CONDITION=Stale/wrong/unknown SHA; zero real collisions attempted;
traceback-free "it worked"; substitute ledger server; desired-state patches.
NEGATIVE_TEST=Single-reader/single-writer control stays clean (proves
concurrency cause); Mac/Linux 50-cycle control stays clean (proves
Windows-specificity).
LEDGER_INVARIANT_SUPPORTED=DLQ-06 (concurrent readers must not crash writers;
writers must not crash readers; persistent errors fail boundedly).

EVIDENCE-HANDOFF CHECKLIST (Windows artifacts must carry, else DLQ-01/02/07
gates reject): producer_id + verifier_id distinct and server-attested (no
ghost strings); observed_at within freshness window of BOTH worker and server
clocks; evidence_sha == deployed SHA; runtime_binding == observed worker
identity; source_url durable https://, retrievable, immutable per revision.

WHAT_MUST_NOT_COUNT_AS_PROOF=Mac simulation (/tmp/windows_ledger_race_inject.py);
mocked suite passing pre-fix; tripwire/test green without the 50 real cycles;
any VALID-marked artifact without independent producer/verifier (DLQ-01);
stale/future observed_at (DLQ-02); revision-0 CANONICAL bundles (DLQ-07).

MAC CLAIMS NOTHING: no WINDOWS_RUNTIME_READY, no EXACT_SHA_DEPLOYED, no
PHYSICAL_ACCEPTANCE_PASS.
