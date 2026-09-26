# Courier Endgame Checkpoint — 2026-09-26

Status: **ACTIVE / HANDOFF-SAFE / DO NOT RESTART BROAD ANALYSIS**  
Purpose: allow a fresh chat, Codex, Opus, Google, Muse or human operator to continue from the current endgame without reopening settled architecture.

## 0. Short answer first

For family / nontechnical explanation, answer first:

> Ich programmiere etwas Neues.

Only if asked for more:

> Wir erfinden ein Programm, das Arbeit am Computer selbst weiterführen soll.

Rules:
- SHORTEST_TRUE_ANSWER_FIRST
- KNOWN_WORDS_FIRST
- EXPLANATION_ONLY_AFTER_CORE_ANSWER
- TECHNICAL_DETAIL_ON_DEMAND

## 1. Product permission law

NO_PERMISSION_SPAM:
- Developer environment may use aggressive trusted-workspace permissions.
- Customer product must use scoped autonomy, not global YOLO.
- Customer authorizes a project scope once.
- Inside that scope Courier continues autonomously.
- Ask again only for a real gate: money, auth/2FA, publish, destructive/irreversible action, outside-scope write, or permission expansion.

## 2. Current critical path

Do not insert product/world/community work ahead of this sequence:

1. Build the final canonical candidate from candidate-b-1.
2. Run real targeted tests against the integrated server/storage path.
3. Physically confirm Muse stdout/result contract on Mac in an isolated scratch workspace.
4. Bind the Mac runtime to the exact final candidate SHA in an isolated worktree/runtime.
5. RUN_1: physical A -> VERIFY -> B with human relay = 0.
6. RUN_2: deterministic restart with no A replay.
7. Only after RUN_2: build the smallest honest read-only dual-surface UI for owner-led product validation.
8. First friend trial.
9. Broader world/community/product expansion only after the above is real.

N1-010 remains PARKED.

## 3. Canonical candidate decision

Accepted repair base:
- branch: candidate-b-1
- SHA: 4c1e24ccc522042af826bc4c2b595daf85d097f9
- server/app.py fingerprint at that base: 97c1bf46... (authorized two-patch server state)

Rejected:
- candidate-b-2
- SHA: 83940de3d7d33776a712e7506aa76726d16f8587
- server/app.py fingerprint: 61fa19e0...
- reason: candidate-b-2 weakens duplicate equivalence by removing status from the duplicate comparison. No b-2 behavior is retained by default.

Also invalid as final candidate/proof:
- agent/canonical-wall-supervisor-v2 @ 332a42f9
- prior unbound Mac proof on 332a42f9
- any line not based on the accepted repair base plus the explicitly authorized final correction

## 4. Final writer scope

Exactly five files may change for the final correction:

1. scripts/courier_verifier.py
2. scripts/integration_contract.py
3. tests/test_artifact_upload_flow.py
4. server/app.py
5. tests/test_p3_server_idempotency.py

Everything else stays unchanged for this correction unless a later explicit blocker changes scope.

### 4.1 Trusted content verification rule

The expected content hash must originate from trusted task/workflow input, never from worker result data.

Trusted path:

workflow/task definition
-> stored task
-> prepare_task
-> dispatch
-> pending verification
-> verifier
-> fetch artifact bytes from server artifact store
-> hash server-side bytes
-> compare against task-owned expected SHA256
-> verdict / reconcile

Never fall back to result.artifacts[].expected_sha256.

For deterministic Canary content verification:
- one declared artifact
- task-owned expected hash
- valid 64-character hex SHA256
- matching artifact/server evidence
- wrong bytes => FAIL
- malformed/ambiguous target => FAIL

If task has no expected hash:
- legacy integrity/binding behavior may remain for non-Canary tasks
- this must NOT be called deterministic content verification
- Canary task without the required target must fail.

Worker-supplied expected_* fields must be rejected by contract.

Claim boundary:
expected_sha256 proves exact deterministic Canary content, NOT universal semantic correctness.

### 4.2 Duplicate semantics rule

Only a legitimate replay of the same accepted canonical result for the same attempt/dispatch generation may receive duplicate ACK.

Before ACK:
- validate current attempt/dispatch generation
- compare canonical result identity/content, including status and binding fields

Changed status, worker, attempt, dispatch, or artifact result must not be treated as identical duplicate success.

Do not broaden FAILED execution retry semantics.

Any FAILED execution invalidates Canary RUN_1; do not hide it behind a successful retry.

## 5. Minimum final tests

Integrated server/storage tests must cover at least:

1. Task-owned expected hash survives Goal -> Claim -> Pending Verification.
2. Correct server artifact bytes => PASS.
3. Wrong server bytes with internally valid upload digest => FAIL.
4. Worker-supplied expected hash => contract rejection / never PASS.
5. Task expectation is enforced even when worker sends no expected hash.
6. Missing task expectation preserves legacy behavior for non-Canary and is not called content proof.
7. Malformed expected hash or ambiguous artifact mapping => FAIL.
8. Exact legitimate replay => duplicate ACK, including persisted/reloaded state where applicable.
9. Changed status => not duplicate success.
10. Changed worker => not duplicate success.
11. Changed attempt/dispatch => rejected.
12. Changed artifact result => not duplicate success.

Real targeted test output is required. A handoff with SKIPPED tests is invalid.

## 6. Mac physical binding requirements

Use the exact final candidate SHA in its own worktree, not the ordinary live repo tree.

Requirements:
- clean worktree
- isolated state file
- isolated artifact directory
- isolated logs
- isolated workspace
- isolated server port (previously 8081 was reported available; re-check physically)
- do not use the live server on old code
- do not reuse old courier_canary state
- verifier from final candidate
- canonical muse_supervisor.py, not muse_wall_supervisor.py
- own wall/config pointing at a new empty workspace
- COURIER_ARTIFACT_UPLOAD=1
- Muse CLI physical binary previously confirmed as /Users/user/.local/bin/muse
- Muse Code 1.4.0 previously reported
- exec, --workspace and --yolo previously physically reported
- reasoning_effort only if the installed Muse help actually documents a usable value

## 7. Open Muse output blocker

The existing adapter accepts success only when stdout contains the expected fenced JSON success payload.

Before RUN_1, perform one separately authorized probe OUTSIDE Courier in a fresh empty scratch directory.

Record:
- exact command form
- exit code
- raw stdout form
- raw stderr form
- ANSI/TUI behavior
- whether fenced JSON is visible in stdout exactly as the adapter expects

If adapter output does not match:
- RUN_1 remains blocked
- classify as CHANGES_WRITER_SCOPE for muse_adapter parsing
- do not run the physical Canary until resolved

## 8. Invalid proof reminders

Do not count as final physical proof:
- prior Mac run on nonfinal/nonbound candidate
- any run where B remains DISPATCHED rather than completed
- simulated tests
- stale handoffs claiming no unknowns without real tests
- single-task proof that never demonstrates A -> VERIFY -> B
- incorrect fixture byte counts or inferred values
- a verifier PASS that proves only integrity while being described as exact content

## 9. RUN_1 pass criteria

Physical A -> VERIFY -> B:

- exact final candidate SHA bound
- A execution count = 1
- A artifact exists
- task-owned expected hash used
- server-side bytes verify PASS
- A reconciles
- B becomes legal because A verified
- B actually dispatches/starts automatically
- B completes
- human relay count = 0
- no FAILED execution

## 10. RUN_2 pass criteria

Deterministic restart proof:

- A executes exactly once
- A reaches RESULT_RECEIVED
- verifier remains OFF before restart checkpoint
- state captured
- controlled restart
- verifier starts after restart
- same A result is preserved
- A is not reexecuted
- A reconciles
- B starts automatically
- B completes
- A execution count remains 1

## 11. Post-RUN_2 UI decision

After RUN_2, do not remain terminal-only for months.

Build the smallest honest read-only **dual-surface** UI:

USER:
- simple
- calm
- featherlight
- plain-language state
- no infrastructure by default

OWNER:
- optional detail drawer
- gives EYES, not a control cockpit
- shows real state, mismatches, retries, waiting reasons and proof boundaries

Authoritative UI observations must reconcile matching server/task state with the matching worker/slot/process observations. If bindings conflict or are stale, display UNKNOWN / WAITING.

Important rules:
- RESULT_RECEIVED = reported, not independently verified
- RECONCILED + matching PASS = verifier accepted the implemented verification property
- "B automatically started" requires actual post-verification dispatch/execution evidence, not merely an incremented step index
- no fake progress or demo success messages in the live-runtime path

The existing dashboard may contribute CSS/cards/layout, but its demo/activity logic must not be treated as runtime truth.

See:
docs/COURIER_DUAL_SURFACE_OBSERVABILITY_POLICY_2026-09-26.md

## 12. Confirmed observability gaps for first UI

Current code review reports:
- reliable transition timestamps are incomplete
- full time-in-state cannot be computed for all key transitions
- durable verification method/version is not consistently present in stored verdict data
- durable governor reason/resource age is not fully exported
- loaded runtime candidate SHA/fingerprint is not a trustworthy existing dashboard field
- current snapshot alone cannot prove absence of a short-lived duplicate execution

These are **post-RUN_2 UI/observability concerns**, not reasons to delay RUN_1/RUN_2.

If the first UI promises "how long has this been stuck?", a small post-RUN_2 transition timestamp field (for example status_changed_at / phase_changed_at) is the current candidate remedy and needs its own authorization.

## 13. Public/private product boundary

Public/demo/social proof must never expose:
- prompts/instructions
- private filenames/content
- local user/repo paths
- credentials/keys/provider sessions
- customer data
- raw logs/artifact bytes
- unnecessary internal architecture identifiers

Public Proof Cards must be separately redacted and opt-in.

The private Courier Symphony world/community vision is intentionally NOT stored in this public repository.

Public-safe principles that may be stored here:
- verified real work, not clicks, may later drive progression
- resource capacity must stay separate from reputation
- social sharing is opt-in
- community contributions must eventually respect explicit permission/trust boundaries
- LIGHT AS A FEATHER remains mandatory
- future world/community work must not delay the physical core proof

## 14. Current model roles

- Windows Antigravity Central Writer: ONLY source writer for final candidate.
- Mac Antigravity: physical proof runner / isolated physical probe.
- Google CLI / secondary Google workers: read-only evidence/support.
- Muse pools: read-only finalization/support unless explicitly assigned otherwise.
- Codex: independent code-grounded final reviewer.
- Opus Ultracode: product/convergence judge, not a source writer.

## 15. Stop condition for broad analysis

Once BOTH are true:
- final candidate SHA exists with real targeted tests and correct five-file scope
- Muse stdout probe matches adapter expectations

stop broad analysis.

Proceed directly to:
Mac binding preflight -> RUN_1 -> RUN_2 -> smallest honest UI.

## 16. Resume rule

A fresh chat/session should first read:

1. this file
2. docs/COURIER_DUAL_SURFACE_OBSERVABILITY_POLICY_2026-09-26.md
3. docs/COURIER_CURRENT_CONVERGENCE_CHECKPOINT_2026-09-26.md
4. docs/CODEX_MASTER_CONTEXT_2026-09-26.md
5. docs/COURIER_NUMBER_ONE_MASTERPLAN.md

Then:
- load only new evidence
- do not restart settled analysis
- resume at the first unresolved gate
- never claim RUN_1/RUN_2/UI proof from stale/simulated evidence

Current flags:

DO_NOT_RESTART_ANALYSIS=YES
FINAL_BASE=candidate-b-1@4c1e24ccc522042af826bc4c2b595daf85d097f9
CANDIDATE_B2=REJECTED
READY_FOR_PHYSICAL_A_TO_B=NO
READY_FOR_SCALE_4=NO
READY_FOR_UI=NO
N1_010=PARKED
