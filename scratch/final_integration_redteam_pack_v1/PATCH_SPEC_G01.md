# PATCH SPECIFICATION — CANDIDATE G01: HUMAN-GATE & DEFERRED FINANCIAL LIABILITY

- **Invariant**:
  $$\text{Action} \in \{\text{IMMEDIATE\_CHARGE}, \text{FUTURE\_CHARGE}, \text{SUBSCRIPTION}, \text{AUTO\_RENEW}, \text{BINDING\_AUTH}, \text{EXTERNAL\_EFFECT}\} \implies \text{HUMAN\_GATE\_REQUIRED}$$
  $$\text{AUTONOMOUS\_SPEND\_LIMIT\_EUR} = 0 \quad (\text{Strict Invariant})$$
  $$\text{Analysis/Simulation} \land \neg \text{ExecutionPayload} \implies \text{AUTONOMOUS\_EXECUTION\_ALLOWED}$$
- **Severity**: P0 (Unauthorized external financial liability, fraudulent subscriptions, unintended billing commitments)
- **Target Subsystem**: `money_factory/safety_gates.js`, Tool Dispatcher, and HTTP/API Capability Gateway

---

## 1. CURRENT BEHAVIOR
In the existing codebase:
- `money_factory/safety_gates.js` contains `SAFETY_INVARIANTS` with `AUTONOMOUS_SPEND_LIMIT_EUR: 0`.
- `SafetyGateManager.checkOperation()` checks an array of strings: `['payment', 'subscription', 'purchase', ...]`.
- `SafetyGateManager.createSpendRequest()` checks `if (effectivePrice <= 0) throw Error('price_eur must be a positive number')`.
- **THE FLAW**:
  1. **Deferred Liability Blindspot**: If an autonomous agent triggers a "14-day free trial with auto-renew at €50/mo", or "€0 due today with billing agreement on file", `effectivePrice === 0`. The spend request function either throws or is bypassed, allowing the agent to bind the organization to a recurring commitment without any human authorization.
  2. **Fragile String Matching**: Substring or keyword matching on "deploy" or "trade" creates severe false positives on benign analysis (e.g. "analyze deployment script", "simulate trading strategy"). Conversely, adversarial prompts ("activate premium service tier without upfront cost") evade verb matching entirely.
  3. **Absence of Tool Capability Gating**: If an LLM bypasses the prompt classifier, the low-level HTTP client or tool executor executes the API request because it lacks an independent, hard-coded capability gate.
  4. **Approval Replay & "weiter" Confusion**: A generic "weiter" or user response to an unrelated prompt could be misinterpreted as approving a pending financial transaction.

---

## 2. TARGET BEHAVIOR (THREE-TIER DEFENSE ARCHITECTURE)
To ensure complete safety without causing paralysis:
1. **Tier 1 — Semantic Intent & Grammar Classifier**:
   - Parses intent with grammatical polarity awareness.
   - Detects negative qualifiers ("simulate", "analyze only", "draft", "dry run", "do not execute") -> marks as `ANALYSIS_ONLY` (no gate required).
   - Detects deferred liability patterns ("auto-renew", "free trial", "monthly recurring", "deferred invoice", "terms agreement", "usage billing") -> marks as `HUMAN_GATE_REQUIRED`.
2. **Tier 2 — Capability & Tool Enforcement Gateway**:
   - Low-level network/tool interceptor placed inside HTTP client and tool execution layer.
   - Intercepts any call targeting payment processors (Stripe, PayPal, AWS Marketplace, cloud billing APIs) or containing billing tokens.
   - Even if Tier 1 were completely bypassed, Tier 2 halts execution unconditionally unless a valid approval token is attached to the request payload.
3. **Tier 3 — Scoped Single-Use Approval Token System**:
   - Human approval cannot be granted via bare conversation text ("weiter", "yes", "proceed").
   - Requires an explicit, cryptographically signed approval object.

---

## 3. APPROVAL TOKEN SCHEMA
```json
{
  "approval_id": "APPR-20260910-A7F9B1",
  "nonce": "e4d3c2b1a0987654",
  "goal_id": "GOAL-FINANCIAL-AUDIT",
  "task_id": "TASK-BILLING-CHECKOUT",
  "task_version": 1,
  "state_version": 4,
  "operation": "ACTIVATE_SUBSCRIPTION",
  "provider": "GitHub Enterprise",
  "currency": "EUR",
  "immediate_amount_eur": 0.00,
  "deferred_recurring_amount_eur": 45.00,
  "billing_cycle": "MONTHLY",
  "maximum_liability_eur": 45.00,
  "expires_at": "2026-09-10T12:00:00Z",
  "single_use": true,
  "consumed": false,
  "signature": "sha256-hmac-or-ed25519-human-auth"
}
```
- **Mandatory Fields**: `approval_id`, `nonce`, `task_id`, `task_version`, `operation`, `maximum_liability_eur`, `expires_at`, `single_use`, `signature`.
- **Anti-Replay**: Tokens are stamped `consumed: true` inside a durable ledger immediately upon execution. Replay attempts fail closed.
- **Scope Restriction**: If actual tool payload amount > `maximum_liability_eur` or provider != `provider`, execution fails closed.

---

## 4. MINIMAL CHANGE SPECIFICATION
In `money_factory/safety_gates.js`:

```javascript
const DEFERRED_LIABILITY_PATTERNS = [
  /\bauto[\s-]?renew\b/i,
  /\bfree\s+trial\b/i,
  /\brecurring\b/i,
  /\bbilling\s+agreement\b/i,
  /\bsubscription\b/i,
  /\bmonthly\s+charge\b/i,
  /\bannual\s+charge\b/i,
  /\busage[\s-]?based\s+billing\b/i,
  /\bdeferred\s+invoice\b/i,
  /\bcredit\s+card\s+authorization\b/i
];

const ANALYSIS_ONLY_QUALIFIERS = [
  /\banalyze\b/i,
  /\bcompare\b/i,
  /\bdraft\b/i,
  /\bsimulate\b/i,
  /\bpaper\s+trade\b/i,
  /\bresearch\b/i,
  /\bdo\s+not\s+(?:charge|buy|subscribe|deploy)\b/i,
  /\bpreparation\s+only\b/i
];

class HardenedSafetyGate {
  static evaluateIntent({ prompt = '', operation = '', toolName = '', toolArgs = {} }) {
    const text = `${prompt} ${operation} ${JSON.stringify(toolArgs)}`.toLowerCase();

    // 1. Tool capability check (Tier 2 hard barrier)
    const isFinancialTool = ['stripe_charge', 'checkout_api', 'subscribe_tier', 'cloud_billing_enable'].includes(toolName);
    if (isFinancialTool) {
      return {
        requires_human_gate: true,
        reason: `Direct financial tool capability '${toolName}' strictly requires human approval.`,
        category: 'FINANCIAL_TOOL_CAPABILITY'
      };
    }

    // 2. Check for deferred liability
    const hasDeferredLiability = DEFERRED_LIABILITY_PATTERNS.some(p => p.test(text));

    // 3. Check for analysis/informational qualifiers
    const isAnalysisOnly = ANALYSIS_ONLY_QUALIFIERS.some(q => q.test(prompt)) && !toolName.startsWith('exec_');

    if (hasDeferredLiability) {
      // Deferred liability always gates, even if today's price is 0
      return {
        requires_human_gate: true,
        reason: 'Detected deferred or recurring financial liability (auto-renew, subscription, or billing agreement).',
        category: 'DEFERRED_FINANCIAL_LIABILITY'
      };
    }

    if (isAnalysisOnly) {
      return {
        requires_human_gate: false,
        reason: 'Operation is classified as analysis/simulation/preparation without execution capability.',
        category: 'HARMLESS_ANALYSIS'
      };
    }

    // Default safety check for traditional operations
    return SafetyGateManager.checkOperation(operation);
  }

  static validateApprovalToken(token, expectedTask) {
    if (!token || typeof token !== 'object') {
      throw new Error('[GATE_SECURITY_VIOLATION] Missing required approval token');
    }
    if (token.consumed === true) {
      throw new Error(`[GATE_SECURITY_VIOLATION] Approval token '${token.approval_id}' has already been consumed`);
    }
    if (new Date(token.expires_at).getTime() < Date.now()) {
      throw new Error(`[GATE_SECURITY_VIOLATION] Approval token '${token.approval_id}' has expired`);
    }
    if (token.task_id !== expectedTask.id || token.task_version !== expectedTask.version) {
      throw new Error(`[GATE_SECURITY_VIOLATION] Approval token task binding mismatch: expected ${expectedTask.id}:v${expectedTask.version}, got ${token.task_id}:v${token.task_version}`);
    }
    return true;
  }
}
```

---

## 5. REQUIRED STATE FIELDS & PERSISTENCE
- In `Task` & `Goal` durable state:
  - `has_financial_implications`: `boolean`
  - `deferred_liability_type`: `'NONE'` | `'SUBSCRIPTION'` | `'AUTO_RENEW'` | `'USAGE_BILLING'`
  - `approval_token_id`: `string | null`
  - `consumed_tokens_ledger`: Path to append-only audit log `runtime/audit/consumed_approvals.jsonl`.

---

## 6. FAIL-CLOSED RULES
- If intent classifier is ambiguous or fails to parse: default to `HUMAN_GATE_REQUIRED`.
- If prompt combines harmless analysis with an executable tool payload: fail closed to `HUMAN_GATE_REQUIRED`.
- A conversational "weiter" or "yes" is strictly rejected as an approval token.

---

## 7. MIGRATION & ROLLBACK
- **Migration**: Existing tasks in `HUMAN_GATE` state remain in `HUMAN_GATE`. No existing task is automatically approved during migration.
- **Rollback**: Rollback preserves consumed token ledger to prevent post-rollback replay attacks.

---

## 8. CLASSIFICATION
- **Classification**: `CONFIRMED_ARCHITECTURAL_REQUIREMENT` / `LIKELY_PRODUCTION_DEFECT` (P0).
- **Mac-Native Proof**: None required. Pure deterministic policy logic.
