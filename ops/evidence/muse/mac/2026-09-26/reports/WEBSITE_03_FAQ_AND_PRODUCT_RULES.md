# WEBSITE_03: WEBSITE FAQ, GRANDMA EXPLANATION & CORE PRODUCT LAWS

**MISSION**: `COURIER_WEBSITE_LAUNCH_PREP`  
**MODE**: `LONG_RUNNING_PREP` · `HOST=MAC`  
**STATUS**: Evidence-Gated Launch Preparation Artifact  
**OUTPUT FILE**: `/Users/user/Downloads/courier_work/muse_mac_wall/reports/WEBSITE_03_FAQ_AND_PRODUCT_RULES.md`  
**GOVERNING PRINCIPLE**: Answer truthfully, use familiar language first, and provide technical depth on demand.

---

## 1. Comprehensive Website FAQ (Evidence-Gated)

### Q1: What does Courier actually do?
**Short Answer**: Courier executes multi-step computer tasks, checks each finished step with an independent verifier, and starts the next step automatically without waiting for you to press "continue".  
**Technical Explanation**: Courier coordinates distributed CLI and coding agents via an atomic REST control plane. Work progresses through a verified DAG lifecycle: `TASK -> EXECUTE -> RESULT -> PERSIST -> VERIFY -> RECONCILE -> NEXT`. Every step is cryptographically audited and recorded in a durable central state.
- `CLAIM=Unattended chained execution with audit trail`
- `CURRENTLY_PROVEN=YES`
- `EVIDENCE_SOURCE=Dispatcher/adapter recovery tests (41 passed), canary A->VERIFY->B logs`
- `SAFE_TO_PUBLISH_NOW=YES (qualified as active pilot)`

---

### Q2: What happens if my computer crashes or the server restarts mid-task?
**Short Answer**: Your progress is not lost, and finished work is never re-run. Courier resumes right where it stopped.  
**Technical Explanation**: Central state is durably persisted to disk (`server/state/central_state.json`) at each step boundary. Tasks in `RESULT_RECEIVED` or `RECONCILED` survive process termination. Upon reboot, the server reloads the exact state hash ($S_2 \equiv S_1$) and advances pending verifications without re-dispatching completed steps (`RESULT_READY_NO_REEXEC` invariant).
- `CLAIM=No blind replay; zero duplicate executions on restart`
- `CURRENTLY_PROVEN=YES`
- `EVIDENCE_SOURCE=CLI4_RESTART_PROOF.md, test_restart_resume_torture, test_p3_server_idempotency`
- `SAFE_TO_PUBLISH_NOW=YES`

---

### Q3: How is Courier different from other autonomous AI agents?
**Short Answer**: Most agents either ask for permission on every single file read or spin out of control hallucinating fake progress. Courier gives you quiet autonomy inside one authorized folder, but stops cold if verification fails or real money is involved.  
**Technical Explanation**: Courier decouples execution from verification. A worker model cannot attest to its own success. An independent verifier process reads the actual bytes from disk, recalculates SHA-256 hashes, and runs deterministic tests. Furthermore, retries are mathematically bounded ($\text{loops} \le 2$), eliminating infinite token burn.
- `CLAIM=Decoupled independent verification & bounded failure recovery`
- `CURRENTLY_PROVEN=YES`
- `EVIDENCE_SOURCE=scripts/courier_verifier.py, MUSE_VERIFIED_GRAPH_DESIGN.md`
- `SAFE_TO_PUBLISH_NOW=YES`

---

### Q4: How often will Courier interrupt me for permission?
**Short Answer**: Exactly once when you select your project folder. Inside that folder, it works quietly. It only asks again when crossing one of seven critical security boundaries.  
**Technical Explanation**: Courier enforces **Single Scope Authorization (SSA)**. Permission spam (e.g. repeated "Allow / Proceed" modal dialogs) is strictly eliminated. Courier pauses only at the **Seven Real Gates**:
1. Money / Cloud spend (> €0.00 cap)
2. Authentication / 2FA secrets
3. Publishing / External network send
4. Destructive filesystem actions (`rm -rf`, `reset --hard`)
5. Writing outside authorized workspace
6. Operating system permission expansion (`sudo`)
7. Irreversible external side effects
- `CLAIM=No permission spam inside authorized scope`
- `CURRENTLY_PROVEN=YES`
- `EVIDENCE_SOURCE=docs/COURIER_PERMISSION_AND_COMMUNICATION_RULES_2026-09-26.md, RV02`
- `SAFE_TO_PUBLISH_NOW=YES (as product security model)`

---

### Q5: Does Courier run on Windows as well as Mac?
**Short Answer**: Our primary physical pilot is active on macOS. Windows worker support is currently in technical preparation.  
**Technical Explanation**: Mac execution is verified end-to-end. While Windows workers can successfully claim tasks, result delivery against the unified 9-field DurableResult schema is currently undergoing hermetic alignment (resolving backslash path normalization and CRLF line-ending variances).
- `CLAIM=Cross-platform worker support`
- `CURRENTLY_PROVEN=PARTIAL (Mac fully proven; Windows in prep)`
- `EVIDENCE_SOURCE=MM11_CROSS_PLATFORM_DRIFT_MAP.md, results/E10-windows-portability.md`
- `SAFE_TO_PUBLISH_NOW=YES (Must be published as "macOS Active Pilot; Windows in Prep")`

---

## 2. The Grandma Explanation (Universal Clarity Rule)

### The Grandma Law
> *"If a non-technical person cannot understand what Courier accomplished, the product is not yet simple enough."*

In Courier, universal clarity is an engineering constraint. We separate every user interface and public communication into two distinct layers:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER A: THE HUMAN OUTCOME (Zero Internal Jargon)                        │
│ • "AUFTRAG": What was asked.                                             │
│ • "ERLEDIGT": What finished on disk.                                     │
│ • "GEPRÜFT": Who verified it and why it's trustworthy.                  │
│ • "MENSCHLICHE EINGRIFFE: 0": You didn't have to help.                   │
│ • "ALS NÄCHSTES": What starts next automatically.                        │
├──────────────────────────────────────────────────────────────────────────┤
│ LAYER B: THE TECHNICAL AUDIT TRAIL (Available on Demand)                 │
│ • SHA-256 hashes, attempt IDs, worker PIDs, HTTP transaction logs.       │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Everyday Analogy for the Public:
> *"Courier works like a modern dishwasher: You load the dirty dishes once, press Start, and come back to clean, dried plates. You don't stand at the sink washing each plate by hand, and you don't expect the dishwasher to ask you twenty times if it has permission to rinse."*

---

## 3. No Permission Spam Product Rule (Single Scope Authorization)

Autonomous agents that repeatedly prompt the user with:
- *"May I read file X?"*
- *"May I run git status?"*
- *"Proceed to next step? [Yes/No]"*

...are not autonomous systems; they are high-friction chatbots that turn the user into a manual approval relay.

### Courier's Single-Scope Contract:
1. **One-Time Onboarding Authorization**: Customer authorizes `/path/to/project`.
2. **Autonomous Execution Envelope**: Inside that directory, Courier reads files, stages edits, executes tests, and advances plans without asking for confirmation.
3. **Hard Stop at Real Gates**: If Courier attempts an action that could spend money, leak secrets, destroy uncommitted data, or write outside the directory, it immediately halts in an explicit `STOP_AT_HUMAN_GATE` state.

---

## 4. Fast-Track 48H Mode Explanation

For developers, founders, and research teams operating under tight resource limits (e.g. hackathons, grant deadlines, or expiring monthly API quotas), Courier offers **Fast-Track 48H Mode**:

```
+──────────────────────────────────────────────────────────────────────────+
| COURIER FAST-TRACK 48H MODE                                              |
| Objective: Maximize Verified Value Per Remaining Hour & Token            |
+──────────────────────────────────────────────────────────────────────────+
```

### Core Behaviors:
- **No Token Burning**: The goal is not to exhaust allowance quickly; the goal is to convert remaining hours into verified, checkable artifacts.
- **Hierarchical Prioritization**:
  - `P0`: Critical-path blockers that advance the core objective.
  - `P1`: Deterministic verification tests and restart proofs.
  - `P2`: Reusable audits, documentation, and migration fixtures.
  - `SKIP`: Speculative duplicate analyses and infinite model chat.
- **Continuous Checkpointing**: State is snapshotted every 15 minutes. If quota or time runs out, you are left with a cleanly preserved, resumable milestone rather than a broken, partial run.

---

## 5. FAQ & Product Rules Claim Discipline Registry

| Claim Element | Public Claim Statement | Currently Proven? | Evidence Source | Safe to Publish Now? |
| :--- | :--- | :---: | :--- | :---: |
| **PR-01** | Layer A / Layer B Grandma Test communication model | **YES** | `COURIER_GRANDMA_TEST.md`, `MUSE_GRANDMA_PRODUCT_SURFACE.md` | **YES** |
| **PR-02** | Single-Scope Authorization with the 7 Real Gates | **YES** | `COURIER_PERMISSION_RULES`, `RV02_NO_PERMISSION_SPAM_PRODUCT_RULE.md` | **YES** |
| **PR-03** | Fast-Track 48H deadline execution policy | **YES** | `COURIER_FAST_TRACK_48H_MODE_2026-09-26.md` | **YES** (as operational feature) |
| **PR-04** | Complete automated self-healing without human gates | **NO** | Graph design enforces `loop_count <= 2` then fail-closed stop | **NO** (Must specify bounded retries) |
| **PR-05** | Zero external data leakage to model providers | **YES** | Local hermetic execution mode; strict workspace scoping | **YES** (with local mode qualifier) |
