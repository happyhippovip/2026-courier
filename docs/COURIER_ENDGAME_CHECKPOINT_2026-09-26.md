# Courier Endgame Checkpoint — 2026-09-26

Status: active endgame / handoff-safe checkpoint  
Purpose: allow a fresh chat, Codex, Opus, Google or Muse worker to continue without reopening settled architecture.

## Short answer first

For family / nontechnical explanation, answer first:

> Ich programmiere etwas Neues.

Only if asked for more:

> Wir erfinden ein Programm, das Arbeit am Computer selbst weiterführen soll.

Rules:
- SHORTEST_TRUE_ANSWER_FIRST
- KNOWN_WORDS_FIRST
- EXPLANATION_ONLY_AFTER_CORE_ANSWER
- TECHNICAL_DETAIL_ON_DEMAND

## Product permission law

NO_PERMISSION_SPAM:
- Developer environment may use aggressive trusted-workspace permissions.
- Customer product must use scoped autonomy, not global YOLO.
- Customer authorizes a project scope once.
- Inside that scope Courier continues autonomously.
- Ask again only for a real gate: money, auth/2FA, publish, destructive/irreversible action, outside-scope write, or permission expansion.

## Current critical path

1. Build final canonical candidate from candidate-b-1.
2. Physically confirm Muse stdout/result contract on Mac in an isolated scratch workspace.
3. Bind Mac runtime to the exact final candidate SHA in an isolated worktree/runtime.
4. RUN_1: physical A -> VERIFY -> B with human relay = 0.
5. RUN_2: deterministic restart with no A replay.
6. Only then proceed to longer chain / branch / bounded loop / scale / product-shell gates.

N1-010 remains PARKED.

## Canonical candidate decision

Accepted repair base:

- branch: candidate-b-1
- SHA: 4c1e24ccc522042af826bc4c2b595daf85d097f9
- server/app.py fingerprint: 97c1bf46... (authorized two-patch server state)

Rejected:

- candidate-b-2
- SHA: 83940de3d7d33776a712e7506aa76726d16f8587
- server/app.py fingerprint: 61fa19e0...
- reason: removes status from duplicate comparison, weakening duplicate semantics; none of this behavior should be retained merely because it exists in b-2.

Also invalid as candidate/proof:
- agent/canonical-wall-supervisor-v2 @ 332a42f9 (second wall / noncandidate live Mac code)
- prior unbound Mac proof on 332a42f9
- any Google line not based on the accepted repair base

## Final writer scope

Exactly five files may change for the final correction:

1. scripts/courier_verifier.py
2. scripts/integration_contract.py
3. tests/test_artifact_upload_flow.py
4. server/app.py
5. tests/test_p3_server_idempotency.py

Everything else stays unchanged for this correction.

### Trusted content verification rule

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
- this must NOT be claimed as deterministic content verification
- Canary task without the target must fail.

Worker-supplied expected_* fields must be rejected by contract.

Claim boundary:
expected_sha256 proves exact deterministic Canary content, NOT universal semantic correctness.

### Duplicate semantics rule

Only a legitimate replay of the same accepted result for the same attempt/dispatch generation may receive duplicate ACK.

Before ACK, validate current attempt/dispatch binding and canonical result equivalence.

Changed status, worker, attempt, dispatch, or artifact result must not be treated as identical duplicate success.

Do not broaden FAILED execution retry semantics.

Any FAILED execution invalidates Canary 1; do not hide it behind a successful retry.

## Minimum final tests

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

## Mac physical binding requirements

Use the exact final candidate SHA in its own worktree, not the ordinary live repo tree.

Requirements:
- clean worktree
- isolated state file
- isolated artifact directory
- isolated logs
- isolated workspace
- isolated server port (8081 was reported available, re-check physically)
- do not use the live server on old code
- do not reuse old courier_canary state
- verifier from final candidate
- canonical muse_supervisor.py, not muse_wall_supervisor.py
- own wall/config pointing at a new empty workspace
- COURIER_ARTIFACT_UPLOAD=1
- Muse CLI physical binary: /Users/user/.local/bin/muse
- Muse Code 1.4.0
- exec, --workspace and --yolo physically confirmed
- reasoning_effort only if actually documented by current Muse help

## Open Muse output blocker

The existing adapter accepts success only when stdout contains the expected fenced JSON success payload.

Before RUN_1, perform one separately authorized probe OUTSIDE Courier in a fresh empty scratch directory.

Need to record:
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

## Invalid proof reminders

Do not count as final physical proof:
- prior Mac run on nonfinal/nonbound candidate
- any run where B remains DISPATCHED rather than completed
- simulated tests
- stale handoffs claiming no unknowns without real tests
- single-task proof that never demonstrates A -> VERIFY -> B
- incorrect fixture byte counts or inferred values

## RUN_1 pass criteria

Physical A -> VERIFY -> B:

- exact final candidate SHA bound
- A execution count = 1
- A artifact exists
- task-owned expected hash used
- server-side bytes verify PASS
- A reconciles
- B becomes legal because A verified
- B starts automatically
- B completes
- human relay count = 0
- no FAILED execution

## RUN_2 pass criteria

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
- A execution count remains 1

## Current model roles

- Windows Antigravity Central Writer: ONLY source writer for final candidate.
- Mac Antigravity: physical proof runner / isolated physical probe.
- Google CLI / secondary Google workers: read-only evidence/support.
- Muse pools: read-only finalization/support unless explicitly assigned otherwise.
- Codex: independent final candidate code reviewer.
- Opus Ultracode: convergence sentinel/judge, not a source writer.

## Stop condition for analysis

Once BOTH are true:

- final candidate SHA exists with real targeted tests and correct five-file scope
- Muse stdout probe matches adapter expectations

stop broad analysis.

Proceed directly to:
Mac binding preflight -> RUN_1 -> RUN_2.

After RUN_2, update visible proof / Grandma card and only then open the next product gate.
