# MUSE WHAT IS LEFT — checkpoint (READ_ONLY_ADVERSARIAL_QA)

OWNER=MUSE elm-triton / HOST=MAC / 2026-09-28
MODE=READ_ONLY_ADVERSARIAL_QA, 0 source edits, 0 runs, 0 ledger writes,
0 PRE_CODEX re-validation, 0 git show/fetch.

CURRENT_PHASE=PRE_CODEX_PENDING
CURRENT_GATE=GATE_STATE_CURRENT.md: PRE_CODEX_STATE=DURABILITY_PENDING,
AUTHORITATIVE_READY=NO, REPORTED_FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf,
NEXT=ONE_GATE_PERSISTENCE_OWNER_ONLY.
WALL_QUEUE_CURRENT.md agrees (GATE blocked by PRE_CODEX Windows durability).
No MUSE_WHATS_LEFT_CURRENT.md existed — lane opened this run.

DONE_WORKBANK=A,C,D,E,I,L,W
DO_NOT_REPEAT=muse-whats-left-A,C,D,E,I,L,W-01 + banned-knowns (RESULT_RECEIVED/
RECONCILED mapping, VALIDATED_PENDING_VERIFY non-state, S2-misdescription,
wall_claim lease limits, RUN_1 witness gaps, timestamp/verify-vs-reconcile/
NEXT_READY gaps, PRE_CODEX prose contradictions, F1/F2-ACK width, result_id
triple-authority, 015-resume-R1, 027-tmp/torn, V1/A1 writer lane, Q1/Q2/Q3
intake writer lane — all cited only, none re-reported as new).

## Round result (7 points, source-grounded)

A API-State-Contract Drift — NO_ISSUE (fail-closed).
- Claim takes target from target_agent (server/app.py:292), mints identity
  (:337-343), then prepare_task rejects unknown capability with 400 (:344-347;
  WORKER_IDS scripts/integration_contract.py:26-31, check :51-52).
- Submitted plans skip planner normalization (:136-144 applies to planner path
  only), so exotic target_agent fails at claim, task stays QUEUED, worker gets
  400. Fail-closed, no corrupt state.

C Error-Code Semantics — EVIDENCE_DOC_DEFECT (minor, fail-closed both sides).
- Unknown worker: 404 at claim (:278) and heartbeat (:267), but 400
  "Invalid task or worker" at task_result (:424). No behavioral harm; contract
  never documents the split.

D Schema Drift adapter/intake/verifier — CONFIRMED_SOURCE_DEFECT (revenue path
end-to-end broken, 3 independent breaks, exact refs):
- D1 adapter posts result_data/artifact_name/artifact_sha256/
  artifact_content_base64 with NO durable fields (goal_id, dispatch_id, run_id,
  result_id, status, artifacts) (scripts/revenue_worker_adapter.py:128-141) →
  intake validate_durable_result 400s "result is missing"
  (scripts/integration_contract.py:135-137; server/app.py:386-391).
- D2 intake strips everything outside `required` (:171; stored :393) while the
  verifier consumes result.result_data (scripts/courier_verifier.py:121) →
  always {} even if D1 were fixed.
- D3 verifier revenue branch gated on task.capabilities containing
  revenue_safety_audit (:112), but the server never sets task["capabilities"]
  (grep: capabilities exist only on worker records server/app.py:226 and claim
  matching :297-301; prepare_task sets none). Branch unreachable via
  /tasks/pending_verification.

E Identity Normalization run_attempt — NO_ISSUE (consistent).
- Adapter enforces str+digit pre-POST (scripts/github_worker_adapter.py:84-85);
  contract enforces digit-string (scripts/integration_contract.py:133-144);
  tests pin "1" (tests/test_github_worker_adapter.py:38,63-109;
  tests/test_p3_server_idempotency.py:161-173). Origin is worker JSON, both
  gates agree. (result_id authority scheme untouched — known, not repeated.)

I JSON Crash Consistency — NO_ISSUE for sanctioned single-proc config.
- save_state tmp+fsync+replace is atomic (server/app.py:65-72); load_state has
  no JSON guard (:57-58). Cross-process torn-file residual is peer-027-owned
  (cited, not new); sanctioned deploy pins single process.

L Registration/Heartbeat/current_task — NO_ISSUE (self-consistent).
- Re-register overwrites record incl. clearing unregistered (:221-229), matching
  the documented comment (:244); heartbeat respects unregistered (:262).
- Changed current_task on re-register → HUMAN_REQUIRED + goal BLOCKED
  (:204-217); resume restores goal ACTIVE (:557). Round trip closes.

W central_state Path Consistency — NO_ISSUE for the live server path.
- Single live path server/app.py:11 (precheck reads same default read-only;
  acceptance isolates via env). CWD-relative 'central_state.json' files belong
  to other lanes: intake_dispatcher.py:40 (known Q2, writer-owned, not new) and
  gemini_worker_adapter.py:77-98 (own local-side ledger, different schema:
  dispatch_ref/pid/real_wall — not the server state).

NEW_CONFIRMED_DEFECTS=D (revenue adapter/intake/verifier triple break)
NEW_EVIDENCE_GAPS=C (404-vs-400 split, minor)
DISPROVEN=(none this round)
BLOCKED_OTHER_OWNER=(none new; P/V1/A1, Q1-Q3, F1/F2, result_id authority stay
with Central/Windows Writer — untouched)
STOP_DOING=FINAL_SHA re-validation; banned-knowns as new; intake/ledger/
writer-lane touches; RUN_1/RUN_2 execution; Codex simulation; filler.

OPUS_NOW=NO (1 defect + 1 doc-gap; 8-dedup threshold far; rich candidate-
independent bank remains: B,G,J,K,T,U,X,Y,Z,AA,AB,AC,AD,AE,AF).
OPUS_QUESTIONS=(none yet — threshold not met)
CODEX_NOW=NO (gate DURABILITY_PENDING / AUTHORITATIVE_READY=NO).
WINDOWS_OWNER_ACTION=Reconcile revenue path (adapter payload shape +
intake passthrough/drop policy + verifier task-capabilities gating) OR retire
revenue_worker_adapter + verifier revenue branch as dead code; plus D1/D2/D3
owner decision. Unblocks nothing phase-gated (candidate-independent either way).
NEXT_WORKBANK=B,G,J,K,T,U,X,Y,Z,AB (lowest first; B with F1-care, K vs resume
comment :547-548, Y via placeholder-token grep on live proof files).
CLEAR_SAFE=YES
