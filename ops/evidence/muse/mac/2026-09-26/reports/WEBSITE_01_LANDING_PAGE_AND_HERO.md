# WEBSITE_01: LANDING PAGE STRUCTURE, HERO COPY & HOW IT WORKS

**MISSION**: `COURIER_WEBSITE_LAUNCH_PREP`  
**MODE**: `LONG_RUNNING_PREP` · `HOST=MAC`  
**STATUS**: Evidence-Gated Launch Preparation Artifact  
**OUTPUT FILE**: `/Users/user/Downloads/courier_work/muse_mac_wall/reports/WEBSITE_01_LANDING_PAGE_AND_HERO.md`  
**GOVERNING PRINCIPLE**: Every public claim must carry verifiable proof. Unproven claims remain marked `SAFE_TO_PUBLISH_NOW=NO` until physical proof passes.

---

## 1. Landing Page Information Architecture

The homepage is designed to inform, build trust, and demonstrate physical reality within 10 seconds. It follows a calm, evidence-driven, high-contrast visual hierarchy.

```
+──────────────────────────────────────────────────────────────────────────+
| 1. NAVIGATION BAR                                                        |
| Logo: Courier Symphony | Links: How it Works, Architecture, Trust, Pilot |
+──────────────────────────────────────────────────────────────────────────+
| 2. HERO SECTION                                                          |
| Headline: "Software that finishes the second step on its own."           |
| Subline: Autonomous execution, independent verification, zero relay.     |
| CTAs: [ Request Pilot Access ]  [ View Physical Proof / Evidence ]       |
| Live Visual: Minimal Interactive Proof Card                              |
+──────────────────────────────────────────────────────────────────────────+
| 3. PRODUCT PROOF CHAIN (HOW IT WORKS)                                    |
| 3 Steps: (1) AUFTRAG -> (2) GEPRÜFT -> (3) ALS_NÄCHSTES                 |
| Visual: State transition timeline with cryptographic hash checks         |
+──────────────────────────────────────────────────────────────────────────+
| 4. HONEST LIMITS (MANDATORY TRANSPARENCY BLOCK)                          |
| Clear statement of what Courier does NOT do today                        |
+──────────────────────────────────────────────────────────────────────────+
| 5. WHY COURIER IS DIFFERENT (ARCHITECTURE PILLARS)                       |
| Unattended continuation · Independent verifier · Single-scope autonomy   |
+──────────────────────────────────────────────────────────────────────────+
| 6. EVIDENCE & TRUST EMBED                                                |
| Verification ledger · Zero duplicate runs · Fail-closed boundary         |
+──────────────────────────────────────────────────────────────────────────+
| 7. PILOT CALL TO ACTION & WAITLIST                                       |
| 1-Click scoped pilot signup for technical teams                          |
+──────────────────────────────────────────────────────────────────────────+
| 8. FOOTER                                                                |
| Privacy · Architecture Docs · Status · Contact                           |
+──────────────────────────────────────────────────────────────────────────+
```

---

## 2. Hero Section Copy & Components

### 2.1 Primary Headline & Subline Options

#### Headline Option A (Recommended — Outcome Focused):
> **"Software that finishes the second step on its own."**

#### Headline Option B (Engineering Focused):
> **"AI operations that keep working when nobody is watching."**

#### Headline Option C (Grandma Test Compliant):
> **"Start it once. It keeps going. You don't have to keep pressing 'Continue'."**

### Subline:
> *"Courier executes a task, independently verifies the output artifact on disk, and advances to the next step automatically — with zero human relays between steps and zero duplicate execution on restart."*

---

### 2.2 Call-to-Action (CTA) Buttons

- **Primary CTA**: `[ Join Paid Pilot ]` (links to `/pilot`)
- **Secondary CTA**: `[ Inspect Live Proof Card ]` (scrolls to `#proof`)
- **Developer Sub-link**: `View Architecture Specification & API Contract ->`

---

### 2.3 Hero Live Proof Card (Embedded UI Component)

The hero section features a live rendering of the verified proof card:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ COURIER EXECUTION BEACON — RUN #CANARY-01                                │
├──────────────────────────────────────────────────────────────────────────┤
│ TASK A: Intake & Static Analysis              STATUS: RECONCILED (PASS)  │
│ VERIFIER: courier_verifier (Independent)      HASH: a7b9...42f9 (Disk)   │
│ AUTO-CONTINUATION: Yes (< 0.4s latency)       HUMAN INTERVENTIONS: 0     │
├──────────────────────────────────────────────────────────────────────────┤
│ TASK B: Code Generation & Artifact Packaging  STATUS: IN_PROGRESS        │
│ SCOPE: /Users/customer/projects/app           SAFETY: 7 Real Gates Active│
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. "How It Works" (The 3-Step Execution Loop)

Courier replaces the manual copy-paste relay with an automated verification loop:

### Step 1: AUFTRAG (Define Scope Once)
- **Customer Action**: You designate a project folder once (`AUTHORIZED_WORKSPACE`) and submit the objective.
- **System Action**: Courier registers the workflow in the central state, creates an immutable execution ledger, and issues the first bounded task to an authorized worker.
- **Promise**: No endless permission dialogs. Inside scope, Courier works quietly.

### Step 2: GEPRÜFT (Independent Verification Before Advancement)
- **System Action**: The worker completes Step A and writes outputs to disk. Crucially, **the worker cannot approve its own work**.
- **Verification Engine**: An isolated verifier process reads the artifact bytes directly from disk, recalculates SHA-256 digests, and tests for schema compliance.
- **Promise**: No result advances to "done" without an independent check.

### Step 3: ALS NÄCHSTES (Autonomous Continuation & Crash Recovery)
- **System Action**: Upon verification `PASS`, the server reconciles Step A and legally unlocks Step B. Worker B claims the task automatically.
- **Crash Invariant**: If the computer restarts, crashes, or goes to sleep, state survives in `central_state.json`. Finished steps are **never** re-run (`RESULT_READY_NO_REEXEC`).
- **Promise**: Zero human relay (`HUMAN_RELAYS=0`). You return to find finished work, not an abandoned terminal.

---

## 4. Honest Limits (The "No Hype" Transparency Block)

To maintain absolute credibility with technical buyers, grants, and partners, this block appears prominently on the homepage:

```markdown
### What Courier Is NOT (Today's Real Limits):
1. **Not an Open-Ended Autonomous General Intelligence**: Courier executes bounded, structured workflows with checkable criteria; it is not a chat companion.
2. **Deterministic Artifact Verification**: Today's physical proof verifies exact-hash and schema-conforming outputs; subjective code quality judgment remains a human gate.
3. **No Unrestricted Machine Access**: Courier operates under Single Scope Authorization (SSA); it cannot and will not touch files outside your authorized folder.
4. **Platform Availability**: Local physical proof is verified on macOS; Windows daemon integration is currently in preparation.
```

---

## 5. Hero & Core Flow Claim Discipline Registry

| Claim Element | Public Claim Statement | Currently Proven? | Evidence Source | Safe to Publish Now? |
| :--- | :--- | :---: | :--- | :---: |
| **CL-01** | Unattended step continuation without human relay ($A \rightarrow B$) | **YES** | `tests/verify_restart_proof_deterministic.py`, `MUSE_A2B_EVIDENCE_CARD.md`, Canary run logs | **YES** (with "isolated test run" note) |
| **CL-02** | Independent verifier checks disk bytes before state advances | **YES** | `scripts/courier_verifier.py`, `server/app.py:verify_task_result` | **YES** |
| **CL-03** | Finished tasks are never re-run after server restart | **YES** | `CLI4_RESTART_PROOF.md`, `central_state.json` snapshot $S_2 \equiv S_1$ | **YES** |
| **CL-04** | Single Scope Authorization (No permission dialog spam) | **PARTIAL** | Architectural design in `RV02`, `RV17`, `COURIER_PERMISSION_RULES` | **YES** (labeled as product rule/terms) |
| **CL-05** | Instant 1-click global desktop installer | **NO** | `RV11_INSTALLATION_PREP.md` (prep-only, no binary built) | **NO** (Do not publish installer links) |
| **CL-06** | Full multi-cloud AWS burst orchestration | **NO** | `WEBSITE_BLUEPRINT_2026.md` roadmap | **NO** (Keep as architecture blueprint) |
