# COURIER COMPANY VISION EXPANSION — 2026-09-26

Status: Strategic expansion map. Does not override the canonical product gates.
Primary rule: Finish the current proof before product expansion.

Operating laws:
1. CONTINUE_BY_DEFAULT
2. FEATHERLIGHT_BY_DEFAULT
3. THE_GRANDMA_TEST
4. NO_EVIDENCE -> NO_PASS
5. NO_BUSYWORK -> EVERY TASK MUST ADVANCE A GATE, REDUCE RISK, OR CREATE REUSABLE EVIDENCE
6. SHORTEST_TRUE_ANSWER_FIRST
7. NO_PERMISSION_SPAM
8. DUAL_SURFACE_TRUTH
9. SHOW_THE_MAGIC_NOT_THE_MACHINERY
10. WORLD_FEELING_MUST_NOT_DELAY_CORE_PROOF

## 1. Company vision

Courier is not a collection of agent windows.

Courier is a durable autonomous work control plane that can:

- accept one human goal;
- preserve the goal contract;
- turn it into bounded tasks;
- route each task to an appropriate worker/provider;
- persist important state and evidence;
- verify results;
- choose the next legal action;
- survive restarts and provider loss;
- continue without the human becoming a message bus;
- explain the result in ordinary language.

The long-term product promise is:

> Start once. Come back later. Courier can show what finished, what was verified, what remains, what it did automatically, and exactly why it stopped if it stopped.

The external product should feel simple even if the control plane is technically sophisticated.

## 2. What Courier is trying to own

Courier should not try to own the best foundation model.

Courier should own the durable layer around changing models:

GOAL
-> CONTRACT
-> TASK GRAPH
-> CLAIM
-> RESOURCE ADMISSION
-> EXECUTION
-> RESULT
-> VERIFY
-> RECONCILE
-> DECIDE NEXT
-> CONTINUE / BRANCH / LOOP / WAIT / HUMAN GATE / DONE

The strategic asset is the verified state machine and its evidence.

## 3. The breakthrough target

A->B is only the smallest experiment.

The general product capability is:

> After every verified state, Courier can prove what happened, determine what actions are now legal, and continue with the next allowed action without a human relay.

Later this must support:

- linear chains: A->B->C->D
- branches: B->C or B->F
- safe loops: F->A
- bounded retries
- waits
- human gates
- multiple hosts
- multiple providers
- restart and recovery

No branch or loop is accepted unless its transition reason and side-effect safety are explicit.

## 4. Human communication law

For nontechnical explanations:
- shortest true answer first
- known words first
- explanation after the core answer
- technical detail only when requested

Example first answer:

> Ich programmiere etwas Neues.

Then, if asked:

> Wir erfinden ein Programm, das Arbeit am Computer selbst weiterführen soll.

## 5. Permission law

Customer-facing autonomy must not reproduce development-tool permission spam.

NO_PERMISSION_SPAM:
- authorize a project scope once
- work autonomously inside that authorized scope
- ask again only at genuine gates such as money, auth/2FA, publishing, destructive/irreversible action, outside-scope writes or permission expansion

Developer aggressive/trusted mode and customer scoped-autonomy mode are different concepts.

## 6. Product layers

### Layer A — Human outcome

Always understandable without technical vocabulary:

- what did I ask for?
- what finished?
- what was verified?
- did I have to intervene?
- what happens next?

### Layer B — Evidence

For trust and debugging:

- goal/task/attempt/execution/result identity
- candidate SHA/config/runtime binding
- logs
- tests
- artifact hashes
- verifier evidence
- provider/runtime evidence
- resource metrics
- restart/recovery evidence

Layer B exists so Layer A can be trusted.

### Layer C — Owner eyes

After the physical core proof, Courier should expose a small read-only owner/advanced view over the same reconciled truth as the simple user view.

The owner surface exists to reveal:
- stuck/waiting states
- retries/reexecution
- server/worker disagreement
- reported-vs-verified boundaries
- missing/ambiguous evidence
- candidate/runtime binding problems

It must not become a second control plane.

## 7. Core product moats

### Verified continuation
A verified result deterministically enables the next allowed action.

### Durable identity
Results cannot silently jump between attempts/executions.

### Safe recovery
Restarts do not blindly repeat side effects.

### Provider independence
Workers are replaceable. Courier remains the state authority.

### Resource-aware autonomy
Logical capacity may be large while physical concurrency remains bounded.

### Organizational memory
Verified findings and runtime facts should reduce future context/tool cost.

### Human clarity
A non-technical person can understand the visible outcome.

### Evidence-backed reputation
If Courier later introduces progression/reputation, it should derive from real verified work rather than clicks, streaks or payment.

Resource capacity, paid plan, honorary status, reputation and verified contribution must remain separate concepts.

## 8. Company expansion lanes

These are product lanes, not permission to bypass gates.

### Lane A — Trust Core
Ledger, idempotency, stale-result protection, artifact integrity, verifier semantics, restart/recovery.

### Lane B — Autonomous Graph Engine
Verified NEXT transitions, branches, loops, waits, dependencies, bounded retries, human gates.

### Lane C — Worker Fabric
Muse, Google/Antigravity, Codex, Opus and future providers behind a stable contract.

### Lane D — Host Fabric
Mac + Windows coordination, host identity, resource governors, wrong-host protection, owned process trees.

### Lane E — Evidence & Benchmarking
Proof Cards, deterministic acceptance evidence, benchmark harness, single-task latency vs continuation throughput.

### Lane F — Featherlight Runtime
Low idle overhead, small active physical set, cheap logical slots, context reuse, bounded polling.

### Lane G — Human Product Surface
Grandma Update, one-minute visible proof, simple status, dual-surface truth, technical details hidden by default.

### Lane H — Vacation Mode
Bounded long-running operation, rate-limit parking, automatic resume, zero human relay except genuine gates.

### Lane I — Pilot Readiness
Customer problem discovery, baseline, pilot contract, payment experiment, data-flow and permission inventory.

### Lane J — Productization
Only after gates: one-command install, one goal entry, one status surface, one safe stop, update/rollback.

### Lane K — Community / World (deferred)
Future direction only after core proof and early user validation:
- people/projects/teams can discover each other
- community tools/workflows may be contributed under explicit trust and permission boundaries
- social Proof Cards are opt-in and evidence-backed
- larger compute/team capacity should feel simple rather than technical

No implementation of this lane is authorized by this document.

## 9. Muse strategy

Muse should not repeatedly rebuild the same feature.

Use spare Muse capacity for bounded, non-overlapping work that either:

1. advances the current gate;
2. removes a known risk;
3. produces reusable evidence;
4. prepares a later gate without changing locked product scope.

Good Muse work:
- code archaeology
- narrow test creation
- fixture preparation
- branch inventory
- duplicate finding deduplication
- failure-matrix expansion
- documentation/evidence extraction
- benchmark fixtures
- provider capability inventory
- resource-cost measurement scripts
- deterministic demo data extraction
- stale/dead-code maps
- cross-platform compatibility review

Bad Muse work:
- another scheduler
- another wall
- another ledger
- duplicate implementation of an existing subsystem
- speculative world/community implementation before proof
- work created only because credits exist

## 10. Task generation law

A new task is eligible only if it answers YES to at least one:

- Does it unblock the active gate?
- Does it reduce a documented risk?
- Does it create reusable deterministic evidence?
- Does it prepare a later gate without changing locked product scope?
- Does it reduce future human relay, runtime overhead, or context waste?

Every task must also include:
- owner/role
- write scope
- dependency
- forbidden scope
- acceptance evidence
- stop condition

No acceptance evidence -> not a valid task.

## 11. Near-term work model

### NOW — Gate-critical
- final canonical candidate
- trusted deterministic content verification
- duplicate/replay rules
- targeted integrated tests
- Muse stdout/result contract
- exact Mac binding
- physical A->VERIFY->B
- deterministic restart/no-replay proof

### IMMEDIATELY AFTER RUN_2
- smallest honest read-only user/owner UI
- owner-led product validation
- first friend trial preparation
- real Proof Card from real evidence

### PARALLEL SAFE PREP
- read-only runtime authority inventory
- provider quota/authorization checklist
- benchmark fixture design
- restart matrix fixtures
- Grandma Update template/evidence extractor
- context-reuse inventory
- idle-overhead measurement plan
- customer problem interviews/non-code prep

### AFTER FIRST PHYSICAL PROOF
- A->B->C->D chain proof
- branch proof
- bounded loop proof
- 1->4->8->16 scale
- 60-120+ minute soak
- real telemetry demo

### AFTER PILOT SIGNAL
- one-command install
- packaging/update/rollback
- broader connectors
- community/world expansion only when supported by real user demand and core reliability

## 12. Public/private boundary

Publicly show value and proof, not proprietary machinery.

SHOW_THE_MAGIC_NOT_THE_MACHINERY:
- public demos may show outcomes, verified continuation and recovery
- private implementation details, prompts, secrets, local paths, raw customer data and unnecessary architecture details stay private
- social sharing is opt-in
- public Proof Cards must be separately redacted and evidence-backed

The detailed Courier Symphony world/community concept is intentionally kept outside this public repository.

## 13. Business reality

Do not optimize for appearing large tonight.

Optimize for a proof that can become valuable:

- real continuation
- less human relay
- fewer duplicate effects
- safe restart
- measurable time saved
- simple explanation
- low operating cost

Revenue comes from solving a real recurring problem, not from terminal count or model spend.

The fastest credible company path is:

proof -> repeatable proof -> smallest honest UI -> first real users -> one painful customer workflow -> paid pilot -> retention -> productization -> community/network effects.

## 14. Success metric hierarchy

1. VERIFIED_CONTINUATION
2. HUMAN_RELAYS_PER_GOAL
3. DUPLICATE_SIDE_EFFECTS
4. LOST_RESULTS
5. RESTART_RECOVERY_SUCCESS
6. RESULT_TO_NEXT_LATENCY
7. VERIFIED_TASKS_PER_HOUR
8. COST_PER_VERIFIED_OUTCOME
9. IDLE_CONTROL_PLANE_OVERHEAD
10. NEXT_DAY_RETURN
11. PAID_PILOT_CONVERSION

## 15. Tomorrow Test

Every day should end with a visible answer to:

> What can we show tomorrow that did not exist yesterday?

If the answer is "nothing visible yet", say so and state the exact proof still missing.

The company should compound visible verified outcomes, not just conversations.

## 16. World-feeling guardrail

The future product may feel like entering a larger living world of real projects, capability and collaboration, but:
- no fake progression
- no purchased competence/reputation
- no artificial grind
- no game metaphor may hide real system state
- no world/community feature may delay the physical core proof
- the interface must remain LIGHT AS A FEATHER as capability grows

The world may become enormous. The default interaction remains simple.
