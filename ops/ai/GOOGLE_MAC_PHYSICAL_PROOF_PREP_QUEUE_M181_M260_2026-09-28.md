# Mac Google Physical-Proof Prep Queue M181-M260 — 2026-09-28

Status: ACTIVE / MAC-SPECIFIC / READ_ONLY_OR_TARGETED_LOCAL_CHECK
Purpose: keep Mac productive with genuinely Mac-specific preparation while FINAL_SHA durability / physical-run authorization is unresolved.

## Hard rules

- RESULT_REUSE_FIRST=YES
- MINIMUM_NECESSARY_READS=YES
- NO_BROAD_REPO_SCAN=YES
- NO_DUPLICATE_REVIEW=YES
- NO_BUSYWORK=YES
- APPLICATION_SOURCE_WRITE=NO
- NO_PHYSICAL_RUN_1_BEFORE_READY_FOR_PHYSICAL_RUN
- NO_RUN_2_BEFORE_RUN_1_PASS
- MAX_HEAVY_JOBS=1
- one live claim per task
- candidate-sensitive tasks may be WAITING_FOR_DURABILITY; then claim another task
- FAMILY_COMPLETE != GLOBAL_TRUE_IDLE

## M181-M190 — Mac runtime provenance / environment binding

M181 — Python executable/interpreter identity capture contract
M182 — Python version + virtualenv binding fields
M183 — dependency/environment fingerprint fields
M184 — working-directory/repo-root binding
M185 — branch/ref vs loaded runtime distinction
M186 — config-file identity capture
M187 — environment-variable allowlist fingerprint plan without secret values
M188 — executable/script path normalization on macOS
M189 — source/build/runtime mismatch detection checklist
M190 — runtime-provenance synthesis

## M191-M200 — macOS filesystem / persistence semantics

M191 — atomic rename assumptions on target filesystem
M192 — fsync/durable-write evidence expectations
M193 — temporary-file cleanup boundaries
M194 — partial/truncated result file detection
M195 — stale file/cache precedence
M196 — file-permission expectations for proof artifacts
M197 — symlink/path-resolution ambiguity
M198 — case-sensitivity portability risk
M199 — state-directory ownership/isolation
M200 — filesystem/persistence synthesis

## M201-M210 — Process / port / resource isolation

M201 — process ownership identity fields
M202 — PID reuse defense requirements
M203 — process-group/session ownership evidence
M204 — port ownership/preflight evidence
M205 — stale listener detection plan
M206 — peer-process noninterference proof
M207 — bounded cleanup contract
M208 — one-heavy-job admission evidence
M209 — CPU/memory pressure fallback evidence
M210 — process/resource isolation synthesis

## M211-M220 — Restart / no-replay edge semantics

M211 — restart before result persistence
M212 — restart after persist before validate
M213 — restart after validate before verify
M214 — restart after verify before reconcile
M215 — restart after reconcile before dispatch
M216 — restart after dispatch before result
M217 — worker disappearance + lease ambiguity
M218 — stale result arriving after new generation
M219 — duplicate result after process restart
M220 — restart edge-case synthesis

## M221-M230 — Evidence / logs / clock / proof integrity

M221 — monotonic vs wall-clock timestamp use
M222 — clock-skew impact on evidence ordering
M223 — log-file identity/fingerprint contract
M224 — stdout/stderr capture completeness
M225 — artifact-directory identity
M226 — evidence packet atomicity
M227 — run-id / attempt-id / execution-id binding
M228 — failed-execution evidence preservation
M229 — Proof Card source/build/runtime linkage
M230 — evidence-integrity synthesis

## M231-M240 — Cross-host portability / handoff

M231 — Windows-path to Mac-path normalization table
M232 — host-local scratch vs durable shared truth
M233 — line-ending / executable-bit portability
M234 — case sensitivity cross-host check
M235 — JSON/path serialization portability
M236 — candidate/evidence ref portability
M237 — session/provider change continuity on Mac
M238 — stale local checkout fallback to origin ref
M239 — Mac-to-Windows handback packet completeness
M240 — portability synthesis

## M241-M250 — Physical-run admission / falsifiability prep

M241 — RUN_1 authorization boolean contract
M242 — exact candidate-binding precondition
M243 — A exactly-once counter evidence
M244 — real Result A identity evidence
M245 — server-byte verification evidence
M246 — verify/reconcile transition evidence
M247 — B auto-dispatch causality evidence
M248 — HUMAN_RELAY_COUNT zero evidence
M249 — FAILED execution invalidation evidence
M250 — RUN_1 admission/falsifiability synthesis

## M251-M260 — RUN_2 / Core-Freeze prep

M251 — RUN_2 authorization depends on RUN_1 PASS
M252 — restart cutpoint evidence packet
M253 — persisted A pre-restart evidence
M254 — A no-reexecution evidence
M255 — post-restart reconcile evidence
M256 — B auto-start after restart evidence
M257 — A execution count remains one
M258 — restart matrix coverage binding
M259 — Core-Freeze handoff fields
M260 — Mac proof-prep final synthesis

## Result

TASK_ID=
STATUS=PROVEN|OPEN|BLOCKED|WAITING_FOR_DURABILITY|RESULT_REUSED|NOT_APPLICABLE
INPUTS_READ=
LOCAL_CHECKS=
RESULTS_REUSED=
FINDING=
MISSING=
NEXT_DEPENDENCY=
DO_NOT_REPEAT_FINGERPRINT=

## End

After M260:
- harvest
- route to MAC_CROSS_FAMILY_AUTO_CONTINUATION_PROMPT.txt
- do not return GLOBAL_TRUE_IDLE unless the global Mac/EITHER routing pass finds no legal work.
