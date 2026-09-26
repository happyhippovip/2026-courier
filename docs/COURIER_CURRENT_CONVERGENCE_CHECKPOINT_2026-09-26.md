# Courier Current Convergence Checkpoint — 2026-09-26

Status: **ACTIVE / NOT YET READY FOR IMPLEMENTATION CLOSEOUT**  
Purpose: Durable checkpoint for the current Opus + Codex + Google/Central-writer convergence.  
Rules: **CONTINUE_BY_DEFAULT · FEATHERLIGHT_BY_DEFAULT · TRUTH > SPEED · NO EVIDENCE -> NO PASS**

This file is a coordination checkpoint. It is **not** a claim that the physical Mac A→VERIFY→B proof has passed, and it is **not** a replacement for the final canonical handoff record.

## 1. Current convergence

The next product proof is deliberately narrow:

`TASK A -> real result -> independent content verification -> ACCEPT -> TASK B starts automatically`

Acceptance requires:

- exactly one physical slot
- a bound candidate code/config/runtime state
- `HUMAN_RELAY_A_TO_B = 0`
- no blind replay of A after restart
- no duplicate side effect
- durable result/evidence
- automatic continuation to B

Before that proof, the fixed integration candidate must close:

1. the Artifact → Verify cutover;
2. the currently documented duplicate-detection / duplicate-execution gaps.

The existing Google/Central writer owns this minimal implementation scope. **No new architecture, scheduler or wall is authorized by this checkpoint.**

## 2. Evidence classification

### KNOWN

- Two scheduler source files do **not** prove two active runtime authorities.
- A conflict-free Git merge proves only mergeability, not integration correctness.
- Physical proof must be bound to an exact candidate:
  - candidate branch
  - source SHA / fingerprint
  - relevant configuration
  - loaded runtime identity where applicable
  - provider / CLI binding
- Decision-relevant changes after the proof invalidate automatic reuse of that proof until the affected evidence is rechecked.
- Before scaling to 4 / 8 / 16, provider authorization, quota/capacity and resource admission must be established.
- Benchmarking must separate:
  - `SINGLE_TASK_LATENCY`
  - `VERIFIED_CONTINUATION_THROUGHPUT_WITHOUT_HUMAN`
- Current supplied evidence includes one physical Windows path reaching `RESULT_RECEIVED`; this checkpoint does **not** treat that as Mac A→VERIFY→B proof.
- The next public/demo video must be recorded only after the physical Mac A→VERIFY→B path has passed once.
- Every number displayed in the demo must come from runtime evidence from the relevant run; no simulated, estimated or decorative metrics.

### UNKNOWN / NOT YET PROVEN

- Which live process/component is the actual authority mutating queue, claim, retry and NEXT in the current runtime.
- Current physical Mac state: wall, slots, live writer lock, active sessions and loaded candidate.
- Whether the real Muse binary has the required CLI/protocol/session binding expected by the adapter.
- Provider authorization/quota for multi-slot scaling.
- Whether LIGHT/HEAVY classification exists as a real task-contract field usable by claim/admission logic.
- Actual idle-control overhead at scale.
- Whether a durable structured knowledge layer already exists for reusable repo/branch/test/provider/host findings.

## 3. Corrected assumptions

### 3.1 Scheduler authority

**Previous unsafe shortcut:** two scheduler files imply two scheduler authorities.  
**Correction:** authority is a runtime fact. Determine which live component actually mutates queue/claim/retry/NEXT state.

### 3.2 Merge safety

**Previous unsafe shortcut:** clean merge implies safe integration.  
**Correction:** Git mergeability says nothing about Artifact→Verify correctness, duplicate handling, runtime binding or physical continuation.

### 3.3 Candidate binding

**Previous unsafe shortcut:** proof must happen on `main`.  
**Correction:** a specifically authorized candidate branch/SHA/config/runtime binding is sufficient. The proof belongs to that candidate.

### 3.4 process_identity polling cost

**Previous suspicion:** `ps` might run once per logical slot per supervisor tick.  
**Correction:** current code reading indicates supervisor-owned children can be checked through existing process handles; `ps` is primarily relevant around spawn/adoption/reconciliation paths. The overhead is therefore a **measurement target**, not a proven per-slot-per-tick multiplier.

### 3.5 context reuse gap

**Previous overstatement:** persistent context reuse is definitely absent.  
**Correction:** repeated repo reconstruction was observed in one development log, but no systematic inventory has yet proven absence of an existing persistent structured knowledge layer. Status remains **UNKNOWN / SUSPECTED GAP**.

## 4. Featherlight requirements

`FEATHERLIGHT_BY_DEFAULT` is a product law, not a cosmetic optimization.

Target user experience on the Mac:

- screen recording can continue
- music playback can continue
- browser/desktop remain responsive
- logical capacity can be large
- physical active set stays resource-bounded
- idle capacity is cheap
- no unnecessary busy polling
- no broad-test fanout
- no avoidable context reload
- no unnecessary model process kept alive without work

Important distinction:

`45 LOGICAL SLOTS != 45 HEAVY PROCESSES`

Mac initial heavy-job budget remains 1 until evidence supports a change. Windows may use its independently proven budget.

If heavy admission is unavailable/unknown, Courier should eventually prefer safe light work **only if the actual task contract and scheduler can represent/admit it**. Do not pretend that capability already exists.

## 5. Current blocker chain

`CODEX_FINAL_REPORT`
→ reconcile with Opus
→ exact minimal writer scope
→ Artifact/Verify + duplicate gaps closed
→ bind candidate
→ targeted tests
→ physical 1-slot A→VERIFY→B
→ restart/no-replay proof
→ provider/quota/resource preflight
→ 4
→ 8
→ 16
→ bounded 60–120+ minute featherlight soak
→ demo

## 6. Parked work

`N1-010 = PARKED`

Standalone-business review becomes READY only after the physical single-slot A→VERIFY→B proof.

Do not spend current reviewer/writer capacity on N1-010.

## 7. Human-understanding artifact

Status:

`HUMAN_UNDERSTANDING_COPY_PENDING = YES`

The human-understanding explanation was produced outside the physical Mac report path. Until an actual Mac process writes/copies it to:

`/Users/user/Downloads/courier_work/muse_burn30/reports/OPUS_HUMAN_UNDERSTANDING.md`

do not claim that path exists.

The final demo must translate technical work into visible real-world outcome, but it must not be recorded before the real Mac A→VERIFY→B proof.

## 8. Inputs expected for final reconciliation

Required input:

- Codex final runtime/red-team report

Preferred input when available:

- Opus current convergence report
- exact current candidate branch/SHA
- targeted test evidence
- physical Mac runtime/process evidence
- provider/CLI capability evidence

Final reconciliation must classify every material claim:

`PROVEN | UNPROVEN | CONTRADICTED | UNKNOWN`

Model agreement alone is never proof.

## 9. Final reconciliation output

The final Opus reconciliation must return exactly one implementation direction:

- actual scheduler authority
- Artifact→Verify gap
- duplicate gaps
- minimal writer scope
- forbidden scope
- targeted tests
- candidate binding
- physical A→VERIFY→B acceptance
- restart acceptance
- provider/quota/resource preflight
- one `NEXT_SINGLE_WRITER_TASK`

No architecture rewrite.

## 10. Resume rule

Any new chat/model/session must:

1. read this checkpoint;
2. read the latest Codex/Opus evidence;
3. verify candidate/runtime deltas;
4. resume from the first unresolved item;
5. never restart already-proven unchanged work merely because the session changed.

Current state:

`DO_NOT_RESTART_ANALYSIS = YES`  
`WAIT_FOR = CODEX_FINAL_REPORT`  
`READY_FOR_FINAL_WRITER_TASK = NO`  
`READY_FOR_PHYSICAL_A_TO_B = NO`  
`READY_FOR_SCALE_4 = NO`  
`N1_010 = PARKED`
