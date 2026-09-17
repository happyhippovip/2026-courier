# Courier Canonical Ledger (Zero-Chat Handoff)

**Revision:** 7
**Date:** 2026-09-17 UTC
**Author:** Google Antigravity Primary Worker

## 1. Repository State
- **Branch:** release-candidate-integration
- **Exact SHA:** c32727e4a853fb085c9b45665c88282051be2ff1
- **Status:** Public release packaging completed (MIT License, requirements.txt, pyproject.toml, GitHub Pages deploy script, Sales/Pilot Kit ready).

## 2. Canonical Goal & Active Work State
- **Goal State:** `HUMAN_REQUIRED`
- **Active Task / Frontier:** Deployment & Publication phase. Codebase is Pilot-ready.
- **First Causal Blocker:** `HUMAN_REQUIRED_CONTACT_DESTINATION` (Pilot intake and website deployment require a human to configure the public email environment variable `COURIER_CONTACT_EMAIL` in GitHub Actions).

## 3. Active Writers and Collision Scopes
- **Google Antigravity:** Primary release/publication/ledger scope (Active).
- **PR41 Writer (Codex):** `motor-eligibility-v1` scope (Isolated/Remote).
- **Collision Rules:** `ONE_WRITER_PER_LOGICAL_SCOPE`. Do not modify Motor Core unless the PR41 writer durably releases ownership.

## 4. Runtime & Motor State
- **Motor Core State:** Untouched by this run (per directive).
- **PR41 Current Head:** `a9b1b27e0ad3593f58b04ac608acf7d4d84d3f2f` (Historical Acceptance Evidence requires causal re-evaluation by Acceptance Guard when PR41 completes).
- **Previous Acceptance Evidence:** `HISTORICAL_REQUIRES_EXACT_SHA_CAUSAL_REEVALUATION` due to PR41 changing claim/eligibility predicates.

## 5. Completed / Proven Acceptance Edges
- **Website QA:** `PASS`
- **Minimal Task Packet / Token Efficiency:** `PASS` (persisted to `docs/TOKEN_EFFICIENCY_LAYER.md`)
- **Zero-Chat Handoff Infrastructure:** `PASS` (This ledger).
- **Demo Readiness:** `PASS` (headless execution verified).

## 6. Stale / Invalidated Evidence
- Earlier Motor Physical Acceptance evidence is marked `PROVISIONAL` pending Acceptance Guard re-evaluation against PR41's changes. Do not promote to `PASS` without re-running the validation test against the new Motor Core (once PR41 is merged).

## 7. Writable Scope & DO_NOT_TOUCH
- **Writable Scope:** Documentation, Sales Material, Release artifacts, Ledger.
- **DO_NOT_TOUCH:** `PR41`, Motor Runtime Core (unless a product-blocking defect is proven *and* scope unowned).

## 8. Exact NEXT_EXECUTABLE_ACTION
- `EXTERNAL_PUBLICATION` (Blocked by `HUMAN_REQUIRED_CONTACT_DESTINATION`).
- Note: While waiting for the human gate, the only allowed autonomous work is independent release/Ledger/Acceptance work that reduces time to a verified sellable Courier.

## 9. Current Minimal Task Packet
```json
{
  "GOAL_ID": "COURIER-PUBLIC-RELEASE",
  "TASK_ID": "LEDGER-HANDOFF-7",
  "CURRENT_RUNTIME_SHA": "c32727e4a853fb085c9b45665c88282051be2ff1",
  "OBJECTIVE": "Maintain zero-chat handoff ledger and ensure publication readiness without spending money or auto-deploying.",
  "REQUIRED_CAPABILITIES": ["documentation_generation", "git_inspection"],
  "REQUIRED_AUTHORITY": ["repo:write"],
  "FIRST_CAUSAL_BLOCKER": "HUMAN_REQUIRED_CONTACT_DESTINATION",
  "NEXT_EXECUTABLE_ACTION": "EXTERNAL_PUBLICATION"
}
```

## 10. EXISTING_ASSET_REUSE
The recent 15-day read-only asset recovery found valuable existing Courier primitives. These should be preserved and integrated into the canonical path:

*   **PR40 Agent Handoff Ledger:** preserve/integrate after human gate
*   **PR41 Motor Eligibility:** Acceptance re-evaluation required before integration
*   **TaskDedupeEngine:** later canonical reuse
*   **FileManifestTracker:** later Minimal Task Packet/context reuse
*   **ChiefContextPackageBuilder:** later context minimization reuse
*   **ReviewDedupeTracker:** later redundant-review avoidance
*   **AgentSessionManager:** canonical candidate for exact owned-process cleanup
*   **RevenueV1SafetyBaseline:** existing revenue-capable workflow to evaluate/use

**DO_NOT_REVIVE_AS_AUTHORITY:**
*   `run_autonomous_loop.py`
*   `TaskLeaseManager`
*   `intake_dispatcher.py` / `queue_processor.py`
*   `dashboard/server.py`
*   `account_switch.py`
