# Google Windows Ledger Queue G181-G280 ÔÇö 2026-09-27

Status: ACTIVE LEDGER/HARDENING QUEUE
Purpose: 100 new logical READ_ONLY / TARGETED_TEST tasks after Q001..Q050 exhausted.
This queue is for Windows Google CLI workers. It is not permission to run 100 heavy processes.

## Hard rules

- Windows Antigravity Central Writer remains the only final-candidate application source writer.
- Google CLI workers do not edit application source.
- Google CLI may run narrow deterministic/local checks and targeted tests.
- Write only scratch/result files under:
  C:\Users\lol\courier_work\google_ledger_g181_280\
- No broad repository census.
- No repeated completed tasks.
- No GitHub Actions.
- No push/merge/rebase/reset/clean.
- No peer-process manipulation.
- No billing/auth/API-key changes.
- MAX_HEAVY_JOBS=1 per host.
- Prefer local CPU/deterministic checks over model reasoning.
- A task with a durable result is DONE unless its explicit RETEST_TRIGGER changes.

## Canonical truth

Accepted base:
candidate-b-1 @ 4c1e24ccc522042af826bc4c2b595daf85d097f9

Rejected:
candidate-b-2

candidate-b-3 is not required.

Final candidate source scope:
1. scripts/courier_verifier.py
2. scripts/integration_contract.py
3. tests/test_artifact_upload_flow.py
4. server/app.py
5. tests/test_p3_server_idempotency.py

## Selection

Claim the smallest-numbered dependency-safe G task whose result does not already exist.
If a task is blocked on FINAL_SHA, mark WAITING_FOR_FINAL_SHA and claim another READY task.
Do not repeat a task after account/session change.


### G181 ÔÇö Ledger ID uniqueness audit
Inputs: integration contract + existing ledger/result docs only.
Done: Prove/flag whether Goal/Task/Attempt/Execution/Result IDs have distinct semantics and collision boundaries.


### G182 ÔÇö Result-to-task binding audit
Inputs: integration contract + result persistence path.
Done: Map exact fields binding a Result to the intended Task/Attempt/Execution.


### G183 ÔÇö Dispatch generation binding audit
Inputs: server result intake + idempotency tests.
Done: Map dispatch-generation identity and every reject path for stale generation.


### G184 ÔÇö Worker identity binding audit
Inputs: result schema + server intake.
Done: Show where worker identity is persisted, compared, and protected from changed-worker duplicate ACK.


### G185 ÔÇö Goal-contract provenance audit
Inputs: canonical product plan + integration contract.
Done: Show how task acceptance remains traceable to Goal Contract rather than worker self-claims.


### G186 ÔÇö Evidence provenance audit
Inputs: verifier/result contract.
Done: Classify trusted vs worker-controlled evidence fields and exact trust boundary.


### G187 ÔÇö Unknown provenance preservation
Inputs: ledger/reconcile code/docs.
Done: Verify missing historic provenance remains UNKNOWN and is never synthesized into PASS.


### G188 ÔÇö Canonical candidate binding map
Inputs: final-candidate docs + exact metadata paths.
Done: Map Source SHA, tree/config/runtime evidence needed to bind PASS to one candidate.


### G189 ÔÇö Result ID determinism check
Inputs: result ID generation code/test only.
Done: Determine whether retries/reloads can accidentally create a second logical Result ID.


### G190 ÔÇö Ledger fingerprint packet
Inputs: G181-G189 results only.
Done: Synthesize minimum deterministic ledger fingerprint fields and missing evidence.


### G191 ÔÇö Atomic result persistence audit
Inputs: result save/load path only.
Done: Check temp-write/replace/fsync/error behavior; report exact durability gap if present.


### G192 ÔÇö Partial-write recovery check
Inputs: persistence path + existing tests.
Done: Determine behavior for truncated/partial state and fail-open vs fail-closed.


### G193 ÔÇö Malformed persisted state check
Inputs: persistence loader.
Done: Determine whether malformed state is rejected, quarantined, or silently reset.


### G194 ÔÇö Restart load idempotence
Inputs: persistence load/reconcile path.
Done: Prove repeated load does not duplicate side effects.


### G195 ÔÇö Accepted-result survival map
Inputs: persistence files + restart policy.
Done: Identify exact persistent fields needed so accepted result cannot disappear after restart.


### G196 ÔÇö Pending-verification survival map
Inputs: pending verification state + verifier path.
Done: Verify pending result survives restart without becoming READY or rerunning task.


### G197 ÔÇö Reconcile-pending survival map
Inputs: reconcile state path.
Done: Verify accepted result can resume reconcile after restart without duplicate execution.


### G198 ÔÇö State schema compatibility check
Inputs: persisted JSON/schema/version fields.
Done: Identify missing versioning/fail-closed behavior for incompatible state.


### G199 ÔÇö Persistence corruption targeted test inventory
Inputs: existing tests only.
Done: List exact existing/missing tests for malformed/truncated/empty persistence.


### G200 ÔÇö Persistence proof synthesis
Inputs: G191-G199 results only.
Done: Produce PASS/OPEN/BLOCKED matrix for restart-safe durable truth.


### G201 ÔÇö Duplicate canonicalization audit
Inputs: server/app.py + idempotency tests.
Done: List exact canonical fields used to decide identical result replay.


### G202 ÔÇö Field omission duplicate audit
Inputs: result comparison path.
Done: Check whether omitted optional fields can collapse a changed result into duplicate success.


### G203 ÔÇö Field ordering canonicalization
Inputs: artifact/result serialization path.
Done: Check whether map/list ordering changes duplicate identity incorrectly.


### G204 ÔÇö Artifact order equivalence
Inputs: artifact result comparison.
Done: Determine whether artifact ordering is intentionally canonicalized or must be exact.


### G205 ÔÇö Duplicate after process reload
Inputs: persistence + server intake.
Done: Trace identical replay across reload and identify exact durable comparison source.


### G206 ÔÇö Conflicting replay persistence
Inputs: duplicate rejection path.
Done: Verify rejected conflicting replay cannot overwrite stored canonical result.


### G207 ÔÇö Concurrent duplicate arrival reasoning
Inputs: intake locking/transaction path.
Done: Determine whether two near-simultaneous same-result posts can double-apply side effects.


### G208 ÔÇö Concurrent conflicting arrival reasoning
Inputs: same path.
Done: Determine fail-closed behavior for racing different results.


### G209 ÔÇö Duplicate response contract
Inputs: API response tests.
Done: Document exact status/body semantics for accepted duplicate vs conflict.


### G210 ÔÇö Replay proof synthesis
Inputs: G201-G209 only.
Done: Produce deterministic duplicate/replay acceptance packet for final review.


### G211 ÔÇö Expected artifact ownership map
Inputs: integration_contract.py + verifier.
Done: Trace task-owned expected_sha256 end to end without trusting worker expected hash.


### G212 ÔÇö Expected artifact persistence map
Inputs: prepare/dispatch/pending verification path.
Done: Verify expected hash survives every state transition.


### G213 ÔÇö Expected artifact omission fail-closed
Inputs: verifier logic.
Done: Check missing expected declared artifact cannot disappear from result without failure.


### G214 ÔÇö Extra artifact policy
Inputs: verifier + task contract.
Done: Determine behavior for unexpected extra artifacts and whether it is explicit.


### G215 ÔÇö Duplicate artifact target ambiguity
Inputs: verifier path resolution.
Done: Check duplicate names/targets/paths fail closed rather than select arbitrarily.


### G216 ÔÇö Artifact path traversal audit
Inputs: verifier download/path handling.
Done: Check normalized target cannot escape intended artifact namespace.


### G217 ÔÇö Server-byte hashing boundary
Inputs: verifier download code.
Done: Confirm hash is over server-fetched bytes, not worker-declared metadata.


### G218 ÔÇö Hash format validation
Inputs: task expected hash parser.
Done: Check exact 64-hex validation and malformed/uppercase behavior.


### G219 ÔÇö Artifact error classification
Inputs: verifier error mapping.
Done: Map missing/download/hash/ambiguity errors to deterministic result states.


### G220 ÔÇö Trusted-content proof synthesis
Inputs: G211-G219 only.
Done: Produce exact trusted-content invariants and remaining gaps.


### G221 ÔÇö Reconcile idempotence audit
Inputs: reconcile path only.
Done: Check repeated reconcile of same accepted result cannot double-apply dependency changes.


### G222 ÔÇö Dependency completion atomicity
Inputs: dependency update path.
Done: Check task completion and dependent READY transition cannot be half-applied.


### G223 ÔÇö NEXT_READY determinism
Inputs: queue/ledger policy + resolver code if present.
Done: Verify same durable state yields same next READY set/order.


### G224 ÔÇö READY eligibility separation
Inputs: eligibility/dispatch path.
Done: Check READY does not imply dispatch if worker/permission/resource eligibility fails.


### G225 ÔÇö Blocked dependency honesty
Inputs: dependency resolver.
Done: Verify blocked/failed prerequisite cannot accidentally unlock dependent task.


### G226 ÔÇö Multiple dependent tasks
Inputs: resolver tests.
Done: Check one completion can unlock multiple independent dependents without dropping any.


### G227 ÔÇö Competing READY dispatch
Inputs: dispatch ownership path.
Done: Check one logical task gets at most one active external execution.


### G228 ÔÇö Dispatch failure rollback
Inputs: dispatch failure path.
Done: Verify failed dispatch leaves deterministic retry/reconcile state, not duplicate-active state.


### G229 ÔÇö Provider unavailable isolation
Inputs: routing/eligibility policy.
Done: Verify unavailable provider blocks only affected tasks while other READY work remains legal.


### G230 ÔÇö Motor proof synthesis
Inputs: G221-G229 only.
Done: Produce Result->Verify->Reconcile->READY->Eligibility->Dispatch proof/gap packet.


### G231 ÔÇö Restart before persist
Inputs: result intake sequence.
Done: Model exact expected state if process dies before durable result persistence.


### G232 ÔÇö Restart after persist before validate
Inputs: result pipeline.
Done: Model resume behavior and duplicate-execution risk.


### G233 ÔÇö Restart after validate before verify
Inputs: same.
Done: Model resume behavior and required durable marker.


### G234 ÔÇö Restart after verify before reconcile
Inputs: same.
Done: Model no-loss/no-double-reconcile behavior.


### G235 ÔÇö Restart after reconcile before dispatch
Inputs: same.
Done: Model deterministic NEXT_READY and no A replay.


### G236 ÔÇö Restart after dispatch before result
Inputs: execution state.
Done: Check UNKNOWN execution handling vs blind restart.


### G237 ÔÇö Worker disappears recovery
Inputs: lease/execution policy.
Done: Map bounded evidence-based recovery without duplicate external execution.


### G238 ÔÇö Provider temporary outage recovery
Inputs: provider/routing policy.
Done: Map wait/fallback behavior without resetting task identity.


### G239 ÔÇö Stale result after restart
Inputs: intake/replay logic.
Done: Verify stale result cannot overwrite newer attempt/generation.


### G240 ÔÇö Restart matrix synthesis
Inputs: G231-G239 only.
Done: Produce scenario -> expected state -> evidence/test needed matrix.


### G241 ÔÇö Claim atomicity audit
Inputs: wall claim/lease implementation/docs.
Done: Check two Windows CLI workers cannot both own one task.


### G242 ÔÇö Claim stale threshold semantics
Inputs: claim policy.
Done: Verify stale requires both liveness failure and age threshold where applicable.


### G243 ÔÇö Lease renewal semantics
Inputs: claim implementation.
Done: Check renewals are owner-bound and cannot resurrect expired foreign claims.


### G244 ÔÇö Claim release ownership
Inputs: release path.
Done: Verify worker can release only its own claim.


### G245 ÔÇö Harvester result identity validation
Inputs: harvester contract/results.
Done: Check task/generation/worker/attempt identity before ingest.


### G246 ÔÇö Harvester dedup fingerprint
Inputs: result contract.
Done: Verify repeated same result summary is idempotent.


### G247 ÔÇö Harvester contradiction handling
Inputs: returned-result policy.
Done: Check contradicting results become CONTRADICTED/NEEDS_VERIFICATION rather than overwrite truth.


### G248 ÔÇö Queue refresh lock audit
Inputs: wall queue refresh rules.
Done: Check only one PREPARER refresh can define a generation at a time.


### G249 ÔÇö Completed task persistence
Inputs: queue/result state.
Done: Verify /clear/session/account change cannot make DONE task READY again.


### G250 ÔÇö Wall concurrency synthesis
Inputs: G241-G249 only.
Done: Produce exact one-prompt/no-duplicate wall proof packet.


### G251 ÔÇö Context-clear continuity
Inputs: context hygiene + wall state.
Done: Verify all necessary continuation data is durable before /clear.


### G252 ÔÇö Fresh-session resume
Inputs: wall prompt + durable queue.
Done: Verify new session can choose next task without chat history.


### G253 ÔÇö Manual account change continuity
Inputs: subscription router + queue policy.
Done: Verify manual authorized account change preserves logical task completion.


### G254 ÔÇö Provider change continuity
Inputs: provider abstraction/result contract.
Done: Verify task/result identity is provider-independent where required.


### G255 ÔÇö Host change continuity
Inputs: cross-host policy.
Done: Verify Mac/Windows handoff does not change logical task identity.


### G256 ÔÇö Stale local cache rejection
Inputs: local scratch vs durable truth rules.
Done: Determine how newer durable queue supersedes stale session cache.


### G257 ÔÇö Checkpoint completeness
Inputs: context-hygiene policy.
Done: List minimum checkpoint fields needed before clear/restart.


### G258 ÔÇö Resume do-not-repeat fingerprint
Inputs: task/result schema.
Done: Verify fingerprint prevents work replay after context rotation.


### G259 ÔÇö Session truth-conflict behavior
Inputs: wall truth-resolution rules.
Done: Check conflicting durable pointers produce TRUTH_CONFLICT instead of guessing.


### G260 ÔÇö Continuity proof synthesis
Inputs: G251-G259 only.
Done: Produce /clear/session/account/provider/host continuity matrix.


### G261 ÔÇö Local-vs-model work inventory
Inputs: completed task types/results.
Done: Identify checks that should be shell/Python/git/pytest instead of model reasoning.


### G262 ÔÇö Idle token waste audit
Inputs: wall logs/results metadata only.
Done: Identify repeated no-op model cycles and exact backoff condition.


### G263 ÔÇö Repeated-read waste audit
Inputs: result read lists if available.
Done: Find unchanged files repeatedly reread across tasks; propose result reuse keys.


### G264 ÔÇö Repeated-test waste audit
Inputs: result test commands.
Done: Find identical tests rerun without changed inputs/retest trigger.


### G265 ÔÇö Heavy-job admission audit
Inputs: compute safety + wall admission policy.
Done: Verify heavy lock and logical-slot separation.


### G266 ÔÇö Memory/swap guard packet
Inputs: device admission policy only.
Done: Define deterministic guard inputs/actions; no live heavy probing unless authorized.


### G267 ÔÇö Queue-size pressure audit
Inputs: queue policy.
Done: Check queue growth does not itself trigger unnecessary worker activity.


### G268 ÔÇö Provider-call budget semantics
Inputs: cost ledger docs.
Done: Map known/estimated/unknown cost states and stop behavior.


### G269 ÔÇö TRUE_IDLE proof
Inputs: wall system + logs/results.
Done: Define evidence that idle is genuine and not missing unharvested work.


### G270 ÔÇö Cost/resource synthesis
Inputs: G261-G269 only.
Done: Produce token/CPU/cost minimization packet with deterministic substitutions.


### G271 ÔÇö Proof Card field completeness
Inputs: canonical product plan + ledger outputs.
Done: Map each required Proof Card field to durable evidence source.


### G272 ÔÇö Proof Level calculation
Inputs: proof rules + evidence classes.
Done: Verify P0/P1/P2/P3 can be derived without worker self-upgrade.


### G273 ÔÇö Autonomy Grade calculation
Inputs: product plan + run evidence contract.
Done: Map A0-A4 requirements and missing evidence.


### G274 ÔÇö Covered Surface binding
Inputs: final candidate/runtime configs.
Done: Map exact modules/config/contracts/tests included in current proof surface.


### G275 ÔÇö Revalidation trigger map
Inputs: evidence invalidation rules.
Done: List exact deltas that invalidate prior PASS/grade and those outside covered surface.


### G276 ÔÇö Human intervention accounting
Inputs: run/pilot metric rules.
Done: Define deterministic HUMAN_RELAY_COUNT vs legitimate HUMAN_REQUIRED event.


### G277 ÔÇö Core-freeze unknown audit
Inputs: G181-G276 summaries.
Done: Identify gate-violating UNKNOWNs only; do not invent speculative concerns.


### G278 ÔÇö Independent-review input packet
Inputs: final SHA gate + synthesized results.
Done: Prepare minimal Codex input refs without duplicating deterministic evidence.


### G279 ÔÇö Pre-physical-run checklist
Inputs: final gate + restart/run prep results.
Done: Produce exact boolean preconditions for RUN_1/RUN_2 handoff.


### G280 ÔÇö Morning ledger handoff
Inputs: G181-G279 result summaries only.
Done: Return LEDGER_PROVEN/OPEN/BLOCKED, PRE_CODEX_READY, RUN1_PREP_READY, NEXT exact action.


## End condition

When G181..G280 are complete or explicitly blocked:
- do not invent G281 automatically;
- synthesize G280;
- if final candidate gate is green, request Codex HIGH once;
- if blocked on Windows Central Writer FINAL_SHA, enter WAITING_FOR_FINAL_SHA;
- if no authorized useful work remains, TRUE_IDLE.
