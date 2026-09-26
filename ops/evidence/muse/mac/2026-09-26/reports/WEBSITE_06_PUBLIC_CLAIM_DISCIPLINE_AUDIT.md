# WEBSITE_06: MASTER PUBLIC CLAIM DISCIPLINE REGISTRY & ANTI-HYPE AUDIT

**MISSION**: `COURIER_WEBSITE_LAUNCH_PREP`  
**MODE**: `LONG_RUNNING_PREP` · `HOST=MAC`  
**STATUS**: Evidence-Gated Launch Preparation Artifact  
**OUTPUT FILE**: `/Users/user/Downloads/courier_work/muse_mac_wall/reports/WEBSITE_06_PUBLIC_CLAIM_DISCIPLINE_AUDIT.md`  
**GOVERNING PRINCIPLE**: "Never turn an unproven claim into marketing text." Every public assertion must have checkable evidence.

---

## 1. The Courier Public Claim Law

Trust is the single most valuable asset for an AI operations platform. Once lost to exaggerated marketing claims, it cannot be recovered.
Therefore, Courier enforces the **Public Claim Law**:
1. Every claim published on the website, documentation, pitch deck, or pilot proposal must exist in this registry.
2. If `CURRENTLY_PROVEN == NO`, the claim is strictly forbidden from customer-facing copy.
3. If `SAFE_TO_PUBLISH_NOW == NO`, the feature may only be discussed internally or in architecture roadmaps.

---

## 2. Master Public Claims Registry

```
+───────────────────────────────────────────────────────────────────────────────────────────────────────────+
| MASTER PUBLIC CLAIM REGISTRY                                                                              |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| ID  | CLAIM                       | PROVEN?  | EVIDENCE SOURCE                         | SAFE TO PUBLISH? |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C01 | Unattended chained step     | YES      | tests/verify_restart_proof_deterministic| YES              |
|     | execution ($A \to B$)       |          | MUSE_A2B_EVIDENCE_CARD.md (Canary run)  | (Qualified)      |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C02 | Independent verification of | YES      | scripts/courier_verifier.py             | YES              |
|     | disk artifacts before next  |          | server/app.py:verify_task_result        |                  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C03 | Zero human relays between   | YES      | Server HTTP access logs during canary;  | YES              |
|     | verified sequential steps   |          | HUMAN_RELAYS = 0 count                  | (In pilot runs)  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C04 | Finished results survive    | YES      | central_state.json snapshot S2 == S1;   | YES              |
|     | server crash & restart      |          | CLI4_RESTART_PROOF.md                   |                  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C05 | Finished tasks are NEVER    | YES      | RESULT_READY_NO_REEXEC invariant;       | YES              |
|     | re-executed on restart      |          | test_p3_server_idempotency.py           |                  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C06 | Bounded failure retries     | YES      | MUSE_VERIFIED_GRAPH_DESIGN.md           | YES              |
|     | (Loops strictly <= 2)       |          | Finite convergence contract             |                  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C07 | Single Scope Authorization  | YES      | docs/COURIER_PERMISSION_RULES_20260926  | YES              |
|     | (No permission spam dialogs)|          | RV02_NO_PERMISSION_SPAM_PRODUCT_RULE.md | (As product law) |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C08 | The Seven Real Gates for    | YES      | RV02, RV17; Money, 2FA, Publish,        | YES              |
|     | human approval boundaries   |          | Destruction, Scope, Escalation, Effect  |                  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C09 | Grandma Test universal      | YES      | docs/COURIER_GRANDMA_TEST.md            | YES              |
|     | clarity communication model |          | MUSE_GRANDMA_PRODUCT_SURFACE.md         |                  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C10 | Fast-Track 48H Mode for     | YES      | docs/COURIER_FAST_TRACK_48H_MODE        | YES              |
|     | deadline optimization       |          | Value-per-hour scheduling model         |                  |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C11 | Cross-platform worker pool  | PARTIAL  | Mac proven; Windows schema drift        | NO               |
|     | (macOS and Windows equally) |          | documented in MM11 drift map            | (Mac only now)   |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C12 | 1-Click native desktop      | NO       | Packaging remains locked at Gate 7      | NO               |
|     | graphical installer (.dmg)  |          | RV11 installation prep-only             | (CLI setup only) |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C13 | Unlimited autonomous coding | NO       | Defies honest product limits;           | NO               |
|     | on open-ended objectives    |          | Courier targets bounded workflows       | (Never claim)    |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C14 | Automated Stripe credit card| NO       | E30 triple dead; Gate 5 non-code prep   | NO               |
|     | self-serve billing checkout |          | Product Shell locked                    | (Invoicing only) |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
| C15 | Full AWS burst elastic cloud| NO       | Blueprint design in WEBSITE_BLUEPRINT   | NO               |
|     | auto-scaling cluster        |          | Physical cloud write lane in progress   | (Architecture)   |
+─────+─────────────────────────────+──────────+─────────────────────────────────────────+──────────────────+
```

---

## 3. Strict Categorization for Launch Copy

### Category A: Safe to Publish Immediately
These claims are backed by physical code, passing deterministic tests, and empirical run logs in this repository:
- *"Courier executes a task, checks the result, and continues with the next step on its own."*
- *"Every finished result is verified by an independent process before downstream tasks unlock."*
- *"Server crashes do not corrupt state or cause completed work to run twice."*
- *"Authorize your project directory once; Courier operates inside that scope without repeated permission prompts."*
- *"Courier halts unconditionally before spending money, publishing code, or destroying data."*

### Category B: Safe to Publish with Explicit Qualifiers
These statements must include clear context notes on the website:
- *"Pilots currently available for macOS engineering environments (Windows support in technical preparation)."*
- *"Proven on deterministic, structured engineering workflows with verifiable artifacts."*
- *"Requires standard Python 3.11+ developer CLI environment."*

### Category C: Strictly Forbidden from Marketing Text
Any copy containing these concepts will be immediately rejected during launch review:
- ❌ *"Revolutionary autonomous AI that solves any coding problem."*
- ❌ *"Zero human involvement ever required."*
- ❌ *"Download our 1-click macOS desktop application."*
- ❌ *"Seamless cross-platform Windows enterprise clustering ready today."*
- ❌ *"Instant credit card self-serve activation."*

---

## 4. Red-Line Anti-Hype Vocabulary Guide

| Forbidden Marketing Word / Phrase | Why It Is Forbidden | Mandatory Truthful Replacement |
| :--- | :--- | :--- |
| **"Autonomous Magic"** | Hides failure modes and creates false expectations. | *"Unattended sequential execution within an authorized scope."* |
| **"Flawless Verification"** | No verifier catches every logical semantic flaw. | *"Independent artifact inspection and hash-matching."* |
| **"Instant Push-Button Setup"** | Requires Python virtualenv and CLI preflight. | *"3-step developer CLI setup in under 3 minutes."* |
| **"Fully Autonomous Agent"** | Misleading; Courier is a deterministic orchestrator. | *"Supervised execution system with human safety gates."* |
| **"Production Ready for Everyone"** | We are running invite-only engineering pilots. | *"Available for technical pilot teams on macOS."* |

---

## 5. Evidence Gate Transition Guide (Turning "NO" into "YES")

1. **To claim Windows Support (`C11` -> `YES`)**:
   - Resolve `MM11` Windows payload shape mismatch (`BURN30-WINDOWS-RESULT-SHAPE-01`).
   - Run hermetic physical $A \rightarrow \text{VERIFY} \rightarrow B$ canary on native Windows host without error.
2. **To claim 1-Click Installer (`C12` -> `YES`)**:
   - Unlock Gate 7 in Canonical Product Plan.
   - Build signed `.dmg` / `.pkg` with embedded virtualenv and verify clean install on vanilla macOS machine.
3. **To claim AWS Burst Cloud (`C15` -> `YES`)**:
   - Complete AWS write lane (`Machine A -> Machine B -> Headless runtime`).
   - Run physical burst worker test and record cloud billing/ledger trace.
