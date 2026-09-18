# WINDOWS PREP PACKET — DLQ-06 behavioral race verification + evidence handoff (Mac-prepared)

CURRENT_HEAD=82bbe0908dfd7db55b5820974f1c0b11e570d7a1
EXPECTED_WINDOWS_SHA=UNKNOWN (Mac does not observe Windows; re-observe on worker)
TASK=Run the DLQ-06 concurrent ledger read/write collision on the real Windows
worker and return raw evidence; plus evidence-handoff field checklist so future
Windows artifacts survive DLQ-01/02/07 gates.

FILES=
- scripts/agent_handoff_ledger.py (exact HEAD code under test; load_bundle +
  atomic_write)
- /tmp/windows_ledger_race_inject.py (Mac simulation harness — REFERENCE ONLY,
  not Windows proof)
- tests/test_windows_ledger_race.py (static tripwire, passes-while-broken)

COMMANDS (Windows worker, exact-SHA worktree)=
1. python -m pytest tests/test_windows_ledger_race.py -q (tripwire baseline)
2. Two-loop collision: Loop A `while($true){ python -c "load_bundle(...)" }`;
   Loop B motor --once iteration; run 50 collision cycles, capture every
   PermissionError/OSError traceback verbatim.
3. Post-fix repeat of (2) after Google lands the retry loop; tripwire test
   must be flipped in the same commit.

PRECONDITIONS=Reviewed deployable SHA checked out on worker; canonical ledger
path used (not a copy); no synthetic injection on worker (real concurrency
only — the Mac harness already covers the synthetic case).
PROCESS_IDENTITY_CHECK=OS-owned worker identity observed (per PHYSICAL plan);
no interactive-agent ownership.
RUNTIME_SHA_CHECK=Worker reports exact SHA; must equal deployed SHA.
STATE_PATH=Production ledger path (worker-local agent_handoff_ledger.json).
TEST_INPUT=50 real concurrent read/write collision cycles.
EXPECTED_OUTPUT=Pre-fix: PermissionError traceback on reader or writer
(Mac-simulated shape: PermissionError [WinError 32] from atomic_write,
no retry). Post-fix: zero crashes + flipped tripwire green.
RAW_EVIDENCE_REQUIRED=Full tracebacks, cycle count, SHA report, process
identity — pasted verbatim, no summaries as proof.
FAIL_CONDITION=Stale/wrong/unknown SHA; zero collisions attempted (test
without contact proves nothing); mock/shim replace on worker; traceback-free
"it worked" claims.
NEGATIVE_TEST=Single-reader/single-writer run stays clean (proves the crash
is concurrency-caused, not environmental); Linux/Mac control run of the same
50 cycles stays clean (proves Windows-specificity).
LEDGER_INVARIANT_SUPPORTED=DLQ-06 (concurrent readers must not crash writers).
WHAT_MUST_NOT_COUNT_AS_PROOF=Mac simulation output in this packet; static
tripwire passing; desired-state patches; temporary substitute ledger server;
any VALID-marked artifact without independent producer/verifier (DLQ-01);
stale or future observed_at (DLQ-02); revision-0 CANONICAL bundles (DLQ-07).

EVIDENCE-HANDOFF CHECKLIST (Windows artifacts must carry, else rejected):
producer_id + verifier_id distinct, server-attested (no ghost strings);
observed_at within freshness window of worker clock AND server clock;
evidence_sha == deployed SHA; runtime_binding == observed worker identity;
source_url durable https://, retrievable, immutable per revision.

MAC CLAIMS NOTHING: no WINDOWS_RUNTIME_READY, no EXACT_SHA_DEPLOYED, no
PHYSICAL_ACCEPTANCE_PASS. Harness result above is simulation input only.
