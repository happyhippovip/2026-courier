# PRIMARY LAUNCH CHANNEL EVALUATION & DECISION

**Product**: `agent-context-trimmer` (v1.0.0)  
**Target Revenue**: First €5.00  
**Target Velocity**: Immediate upon human approval  

---

## Comparative Channel Analysis

| Evaluation Dimension | Channel 1: Gumroad | Channel 2: GitHub (Sponsors / Releases) | Channel 3: Direct Stripe / LemonSqueezy |
| :--- | :--- | :--- | :--- |
| **Friction to Launch** | **Extremely Low** (3-5 mins, web form + zip upload) | High (requires OAuth app or webhook gating infrastructure) | Moderate (requires business verification & KYC) |
| **Fee Structure** | 10% flat + $0.30 per transaction | 0% - 3% + payment processing | 5% + $0.50 per transaction (MoR) |
| **Compliance & Tax** | **Merchant of Record** (handles global VAT, EU digital goods tax, invoices) | No tax remittance for releases; sponsors is donation-focused | MoR (LemonSqueezy) or Self-managed VAT (Direct Stripe) |
| **Buyer Trust for Devs** | High (widely used for dev books, icon packs, CLI tools, themes) | Very High | High |
| **Time to First Dollar** | **Instant** (buyers checkout in 20 seconds via Apple Pay, Google Pay, Card, PayPal) | Delayed / Multi-step | Instant once KYC approved |
| **Courier Observability** | **High** (Public URL verification + unauthenticated HTTP ping + optional webhook) | High (GitHub API) | Moderate |

---

## Evaluation Detail

### 1. Gumroad (Primary Winner)
- **Why it wins**: For a one-off €5 digital utility, tax compliance is the biggest hidden friction. EU VAT MOSS requires collecting buyer location evidence and submitting multi-country tax filings unless using a Merchant of Record (MoR). Gumroad is a full MoR, handling all global VAT/sales tax liabilities autonomously.
- **Workflow**: Upload `PRODUCT_PACKAGE.zip`, set €5, paste description, click Publish.
- **Net payout on €5**: Approximately **€4.20** after Gumroad 10% + standard card processing fee.

### 2. GitHub Releases / Sponsors (Runner-Up / Distribution Amplifier)
- GitHub does not provide a native turnkey paywall for release asset zips without third-party integration. While developer trust is peak, the engineering overhead to gate downloads violates our "fastest safe path" rule.
- Free/open tier or source code repo can live on GitHub as an inbound acquisition funnel leading to the Gumroad full package.

### 3. Direct Stripe / Self-Hosted
- Excellent for recurring SaaS, but introduces high operational overhead (building checkout sessions, hosting delivery webhook, registering for EU tax OSS/IOSS).

---

## Canonical Selection

### **PRIMARY LAUNCH CHANNEL**: `GUMROAD`
- **Backup / Secondary**: `LEMONSQUEEZY`
- **Organic Inbound Funnel**: GitHub repository README + Twitter/X release announcement + r/Cursor post with link to Gumroad.

---

## Next Action Required
Proceed to Phase 12 to establish the authoritative 7-stage `REVENUE_EVIDENCE_CONTRACT.json`.
