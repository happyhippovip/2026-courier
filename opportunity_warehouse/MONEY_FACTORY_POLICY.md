# MONEY FACTORY POLICY & ECONOMIC SAFETY INVARIANTS

## 1. Absolute Hard Safety Invariants

The autonomous engine operates under strict physical and financial guardrails:

```text
REAL_TRADES = 0
REAL_FUNDS_TOUCHED = NO
REAL_POSITIONS_CHANGED = 0
REAL_WALLETS_CONNECTED = NO
WALLET_SIGNING = NO
AUTONOMOUS_SPEND_LIMIT_EUR = 0
```

Under NO circumstances may any autonomous agent:
1. Execute a real financial transaction, payment, subscription, trade, or purchase.
2. Connect, unlock, import, or sign transactions with a cryptocurrency wallet or banking credential.
3. Touch real funds, change portfolio positions, or create debt liabilities.
4. Auto-bill credit cards or accept terms of service involving recurring subscription fees.

---

## 2. Mandatory Human Gates

The following actions strictly require a physical human gate (`HUMAN_GATE`):
- **Payment / Subscription / Purchase / Upgrade / Overage**: Autonomous spend is capped at €0.
- **Publication**: Deploying public blog posts, launching public repositories, publishing apps to stores.
- **Production Deployment**: Pushing code to live production servers or cloud infrastructure.
- **Customer Outreach / External Messaging**: Sending cold emails, DMs, forum posts, or contacting leads.
- **Real Trade / Position Change**: Financial market orders.
- **Wallet Signing**: Cryptographic authorization of any transaction.
- **Account Creation / Login / 2FA / KYC**: Creating third-party accounts, passing Captchas, entering SMS codes.
- **Real Spend Execution**: Any outflow of currency.

When an opportunity requires spend, the engine must NOT spend. Instead, it generates a structured `SPEND_REQUEST`.

---

## 3. Structured SPEND_REQUEST Contract

Every spend request must supply complete deterministic justification:
```yaml
spend_request_id: SPEND-REQ-YYYYMMDD-XXXX
price_eur: <positive float>
purpose: <concise, substantive justification>
evidence: <direct citation, benchmark, or verified market signal>
expected_upside_eur: <projected return>
maximum_loss_eur: <worst-case scenario>
cheapest_alternative: <evaluated €0 or low-cost alternative>
human_approval_required: true
autonomous_execution_allowed: false
status: PENDING_HUMAN_APPROVAL
```

---

## 4. Economic Anti-Loop Invariant

```text
INVARIANT:
After Courier freeze, Courier infrastructure may ONLY be modified when a reproducible Courier defect concretely blocks product/revenue work.
```

The system operates strictly within the Economic Execution Loop:
```text
RESEARCH
→ OPPORTUNITIES
→ SCORE
→ TEST
→ BUILD
→ VERIFY
→ DISTRIBUTE / HUMAN_GATE
→ REVENUE
→ LEARN
→ NEXT OPPORTUNITY
```

Agents are explicitly forbidden from:
- Creating infrastructure refactor tasks merely because "better architecture could be built."
- Inventing synthetic test signals to simulate revenue (`FAST_TEST_MODE` cannot count as revenue).
- Automated engagement farming (generating synthetic upvotes, followers, or artificial interactions).
- Overwriting historical predictions to inflate historical accuracy.
