# Courier Wall V2 Big Packages

Status: ACTIVE
GENERATION=WALL-V2-A
REQUESTED_LOGICAL_SLOTS=100

Each package is intentionally larger than the earlier WBUILD microtasks.

## BP01 — Publish existing completed Ledger/Muse artifacts
Goal: eliminate local-only truth.
Inputs:
- known wall/Ledger scratch outputs
- ops/ai stable pointers
Actions:
- identify completed reusable ops/ai artifacts in wall scratch only
- do not broad-scan repo or disk
- stage publish candidates
Done:
- publish queue contains every completed reusable Ledger/Muse artifact or explicit MISSING record

## BP02 — Extended Ledger convergence
Inputs:
- existing Ledger specs/results
- RETURNED_RESULT_POLICY
- forward-only contract
Substeps:
- identity chain
- state machine
- evidence refs
- reconciliation
- NEXT_READY
- stop/block states
Done:
- one converged Ledger artifact staged for publish

## BP03 — Truth/path resolver
Inputs:
- WALL_SYSTEM
- canonical completion handoff
- forward-only contract
Substeps:
- repo root
- logical truth keys
- supersession
- missing path
- authority conflict
- moved checkout
Done:
- resolver spec + acceptance matrix staged

## BP04 — Claim/lease concurrency
Inputs:
- task packet schema
- Ledger convergence
Substeps:
- atomic claim
- lease identity
- stale lease
- reclaim
- duplicate live claim
- crash recovery
Done:
- exact implementation/test packet

## BP05 — Result fingerprint + duplicate semantics
Inputs:
- Returned Result Policy
- Ledger convergence
Substeps:
- canonical result fingerprint
- identical duplicate
- changed status/worker/attempt/dispatch/artifact
- contradictory results
Done:
- dedup contract + targeted cases

## BP06 — Automatic Harvester
Inputs:
- BP04/BP05 results
Substeps:
- validate identity
- dedup
- attach evidence
- reconcile
- dependency unlock
- next READY
- human gate only when required
Done:
- Harvester spec + implementation packet

## BP07 — NEXT_READY dependency engine
Inputs:
- Ledger + Harvester results
Substeps:
- dependency state
- READY calculation
- BLOCKED
- RETEST trigger
- queue empty
- refill rule
Done:
- deterministic NEXT_READY contract

## BP08 — Queue generations + refresh
Inputs:
- BP03/BP06/BP07
Substeps:
- generation fingerprint
- supersession
- result carry-forward
- retest-only reopening
- one-preparer refresh lock
- no broad scan
Done:
- queue generation/refresh spec

## BP09 — Session/context continuity
Inputs:
- Muse clear rule
- queue generation result
Substeps:
- checkpoint
- /clear
- new session
- CLI restart
- machine restart
- resume current package
Done:
- continuity spec + test plan

## BP10 — Provider/account continuity
Inputs:
- subscription-first router
- Ledger/queue results
Substeps:
- provider route
- auth mode
- quota state
- manual authorized account change
- no duplicate work
- reset/cooldown
Done:
- provider continuity packet

## BP11 — Cost/quota guard
Inputs:
- night cost policy
- provider continuity
Substeps:
- subscription first
- explicit PAYG fallback
- budget state
- minimum reads
- result reuse
- queue empty idle
- per-package cost evidence
Done:
- cost guard contract + regression cases

## BP12 — Device-adaptive motor admission
Inputs:
- device admission policy
- queue/Ledger results
Substeps:
- requested/admitted/active/guarded
- workload class
- reserve interactive
- scale down
- slow scale up
- no queue loss
Done:
- admission state machine + tests

## BP13 — Muse wall adapter
Inputs:
- BP06-BP12 results
- Muse startup/clear rule
Substeps:
- minimal bootstrap
- claim
- exact input read
- result write
- context rotate
- continue
Done:
- reusable Muse wall bootstrap staged for publish

## BP14 — Google wall adapter
Inputs:
- BP06-BP12 results
- Google continuous worker
Substeps:
- same as Muse adapter
- manual account continuity
Done:
- reusable Google wall bootstrap staged

## BP15 — Mac/Windows portability
Inputs:
- BP13/BP14
Substeps:
- repo root abstraction
- scratch root abstraction
- path handling
- shell differences
- no absolute truth identity
Done:
- portability packet

## BP16 — One-prompt role selection
Inputs:
- Publisher/Harvester/Executor/Preparer rules
Substeps:
- control locks
- role priority
- fairness
- crash release
- duplicate prevention
Done:
- universal role-selection algorithm

## BP17 — No-waste regression plan
Inputs:
- BP08-BP16
Substeps:
- no repo census
- no repeated unchanged read
- result reuse
- no idle analysis
- queue empty idle
- new session no replay
Done:
- targeted cost regression plan

## BP18 — Wall concurrency acceptance
Inputs:
- BP04/BP06/BP12/BP16
Substeps:
- 4 same-prompt workers
- competing claims
- harvester contention
- publisher contention
- motor reduction
- queue continuity
Done:
- one-prompt acceptance plan

## BP19 — 100-slot logical Muse task bank
Inputs:
- current canonical product/engineering blockers
- durable package results
Actions:
- generate 100 logical task packets only when concrete independent/retest/dependency work exists
- exact inputs and done condition for every task
- no filler/busywork
Done:
- Muse logical task bank staged or honest count <100 with reason

## BP20 — Central Writer implementation packet
Inputs:
- BP02-BP18 results only
Actions:
- deduplicate
- order by causal dependency
- exact file/function/change/test
- no application source edit by this worker
Done:
- one implementable Central Writer packet

## BP21 — Source implementation verification packet
Dependency: Central Writer implementation exists
Inputs:
- exact changed files
- exact targeted tests
Actions:
- map change to spec
- list targeted verification only
Done:
- verification packet

## BP22 — Universal wall proof
Dependency: implementation verification green
Actions:
- prove same universal prompt with 4 workers first
- prove claims/results/harvest/no-human relay
- do not jump to 100 active workers
Done:
- ONE_PROMPT_READY YES/NO with evidence

## BP23 — Muse overnight production queue
Dependency: BP22 green
Inputs:
- current concrete OPEN work only
Actions:
- create next overnight queue
- large work packets
- exact inputs
- cost guards
Done:
- production Muse queue staged

## BP24 — Morning synthesis
Inputs:
- all completed BP results only
Done:
- LEDGER_READY
- HARVESTER_READY
- PUBLISHER_READY
- ONE_PROMPT_READY
- MUSE_WALL_READY
- COST_GUARD_READY
- SOURCE_IMPLEMENTATION_OPEN
- NEXT
