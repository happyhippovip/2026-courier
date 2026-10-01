# T12 RESULT — Queue/Auto-Next wiring (static chain map, read-only)

MODE: shell-less LIGHT. All paths OBSERVED-in-file (server/app.py = P3,
read-only here; courier_verifier.py = motor scope). No execution.

## The automatic chain (no USER_CONTINUE in code path)
1. CLAIM: POST /tasks/claim (app.py:720) — worker lease (DISPATCHED),
   self-reclaim of own DISPATCHED (747), WAITING_PROVIDER/BLOCKED_TRANSIENT
   auto-resume after provider-lock expiry (754-762, lock key
   quota_pool:provider).
2. RESULT: POST /tasks/result (893) — DISPATCHED+owner check, duplicate
   protection (identical->ACK_DUPLICATE, contradictory->409), durable-result
   validation, then SUCCESS->RESULT_RECEIVED + checkpoint next_action=VERIFY
   (932-939); failure->bounded execution retry w/ backoff (943-949);
   AMBIGUOUS_CRASH->HUMAN_REQUIRED (950).
3. VERIFY-POLL: courier_verifier.py run_loop (42-113) — GET
   /tasks/pending_verification every 5s (backoff to 60s on error);
   revenue_safety_audit tasks via revenue_v1_safety_baseline.py (60s timeout,
   PASS/FAIL), others via artifact sha256 check; POST /tasks/verify.
4. VERIFY: POST /tasks/verify (1037) — verifier-auth, producer!=verifier
   principal (1072), independent verifier_id (1063), replay/alias/
   contradiction guards (1048-1056), runtime-identity binding (1084-1090),
   attestation receipt on clean PASS (1100-1116), PASS->RECONCILED (+resource
   release, workflow_plan sync, ready-work recompute 1136-1152,
   auto-replenish w/ instruction+target dedupe 1153-1199, DONE/BLOCKED
   terminals); FAIL->bounded verification retry (1212-1219) then
   FAILED_TERMINAL (1221); worker release in all terminals (1224-1228).
5. NEXT: workers re-poll /tasks/claim; QUEUED+deps-met steps dispatch.
   RECONCILED_PENDING_MERGE holds protected_code behind human merge gate
   (1120-1124) without stopping unrelated dispatch.

## Findings (for owners, not fixed here)

Q-T12-1 (LOW) REJECTION BLOCKERS NEVER CARRY A CAUSE.
FAIL path builds blockers from data.get('reason', 'no reason') (1218, 1223),
but courier_verifier.py's payload (90-98) never sends 'reason'. Every
VERIFICATION_REJECTED blocker reads "...: no reason". Evidence-quality gap.
Owner: server/verifier scope.

Q-T12-2 (INFO) TWO MOTOR SHAPES COEXIST — PROOF RUNNER MUST PICK ONE.
server/app.py embeds a full dispatch/verify/reconcile/replenish loop (API
path, no separate motor process needed). scripts/courier_continue.py drives
agent_handoff_ledger.json as a file-based motor (ledger path). This is the
RC checkpoint's hypothesis A-vs-B question in concrete form: the acceptance
run must declare which motor it proves. No code change; routing note.

Q-T12-3 (OK) RETRY ACCOUNTING IS BOUNDED BOTH SIDES.
Execution retries (943) and verification retries (1213) both check
retry_state < MAX_RETRIES before increment; no zero-reset in these paths.
test_server_infinite_retry.py exists (T10). OK.

Q-T12-4 (OK) USER_CONTINUE-FREE ADVANCE IS STRUCTURALLY PRESENT.
Every transition above is poll/timeout/state-driven. Liveness (do workers
actually poll forever, do timers fire under load) still needs the physical
proof run — structure alone is not proof. Supports RC step 6 structurally.

## Disposition
Read-only mission: NO FIXES (P3 + motor scopes foreign). Q-T12-1 handed to
server/verifier owner; Q-T12-2 noted for the acceptance-proof runner.
No files outside runtime/slots/MUSE-45 touched.
