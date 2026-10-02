# User Acceptance Requirement 03: Cost & Provider Transparency (No Hidden Spend)

## 1. User-Visible Ambiguity
When a user runs a Goal in Courier, tasks are claimed and dispatched to background workers.
The user is left with critical financial and operational uncertainty:
- Did this run consume paid pay-as-you-go (PAYG) API credits on my credit card?
- Which AI model providers were invoked, and under what subscription tier?
- Did background tasks run on local CPU or remote cloud APIs?
Currently, `/status` only reports worker counts, and `/goals/<goal_id>` shows raw worker IDs without cost categorization.

## 2. What the System Can Actually Prove Today
The server runtime state (`state["workers"]` and `task["worker_id"]`) tracks:
1. `worker["cost_class"]`: Defined as `"free"`, `"low"`, `"medium"`, or `"high"`.
2. `worker["provider"]`: Identifier of the backing runtime (e.g., `"google"`, `"antigravity"`, `"local"`, `"github"`).
3. `task["worker_id"]`: Exact identity of the worker that executed each step.
4. Auto-router rule ([`SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md`](file:///C:/Users/lol/2026-workspace/2026-courier/ops/ai/SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md)):
   Enforces that PAYG is never invoked unless explicitly configured and enabled.

## 3. Concrete Acceptance Requirement
Every completed or in-progress Goal presentation must provide a **`Cost & Provider Transparency Card`**:
1. **`payg_spend_triggered`**: Boolean (`false` if zero incremental pay-as-you-go billing occurred).
2. **`estimated_marginal_cost`**: Human string (e.g. `"0.00 EUR (100% Flatrate / Local / Subscription)"`).
3. **`provider_usage_breakdown`**: Table mapping tasks to provider identity and billing mode:
   - Example:
     - `Task 1 (Data prep)`: `Local Deterministic (FREE)`
     - `Task 2 (Canary run)`: `Google CLI Subscription (INCLUDED)`
     - `Task 3 (Verification)`: `Local Verifier (FREE)`
4. **`budget_firewall_status`**: Confirmation that the financial firewall remained untriggered.

## 4. Required Runtime State & Evidence
- **State Fields**:
  - `state["goals"][goal_id]["workflow_plan"]`
  - `state["workers"][worker_id]["cost_class"]`
  - `state["workers"][worker_id]["provider"]`
- **Evidence Verification**:
  - Aggregation function `derive_goal_cost_summary(goal, state)` asserting that all dispatched steps match permitted cost tiers and producing a verified zero-surprise cost receipt.
