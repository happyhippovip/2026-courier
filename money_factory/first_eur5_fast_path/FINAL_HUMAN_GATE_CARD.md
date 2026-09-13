# FINAL HUMAN GATE LAUNCH CARD (MINIMUM FRICTION)

**Product**: `agent-context-trimmer` (v1.0.0)  
**Security Status**: STRICT_HUMAN_GATE_ACTIVE  
**Spend Limit**: €0.00 (Zero autonomous spend)  
**Date**: 2026-09-10  

---

## 1. Platform Comparison: Selecting Lowest Human Friction

| Comparison Criteria | Option 1: Gumroad | Option 2: LemonSqueezy | Option 3: Direct Stripe + Self-Hosted |
| :--- | :--- | :--- | :--- |
| **Setup Time** | **3–5 minutes** | 1–3 business days (merchant review) | 2–4 hours (server + webhook code) |
| **Merchant of Record (VAT/Tax)** | **Yes** (Automated global VAT remittance) | **Yes** (Automated global VAT remittance) | **No** (Operator must self-file EU VAT MOSS) |
| **File Hosting & Delivery** | **Built-in** (Instant zip delivery upon pay) | **Built-in** (Instant download link) | Requires custom S3/Cloud storage + signed URLs |
| **KYC / Verification Barrier** | Low (standard payout bank entry) | Moderate (underwriting review required) | Moderate (Stripe identity verification) |
| **Fee per €5 Sale** | ~10% + $0.30 (~€0.80 total fee) | ~5% + $0.50 (~€0.75 total fee) | ~1.5% + €0.25 (lowest fee, highest work) |
| **Verdict** | **RECOMMENDED: Fewest Human Actions** | Secondary Alternative | Rejected: High friction & tax overhead |

---

## 2. HUMAN MUST DO (Exact Minimal Human Actions: 3–5 Minutes)

1. **Log in to Gumroad**: Navigate to `https://app.gumroad.com/products/new`.
2. **Set Product Details**:
   - Title: Copy from `PRODUCT_TITLE.txt`
   - Summary: Copy from `ONE_SENTENCE_VALUE.txt`
   - Description: Copy markdown from `LONG_DESCRIPTION.md`
3. **Upload Deliverable**:
   - Upload `PRODUCT_PACKAGE.zip` (12.7 KB, SHA-256 verified).
4. **Set Price**:
   - Set flat price to **€5.00** (or $5.00 USD). One-time payment.
5. **Configure Payout**:
   - Select your personal/business payout account (PayPal, Stripe, or SEPA bank account).
6. **Publish Listing**:
   - Click the green **"Publish"** button.
7. **Notify Courier**:
   - Paste the generated public listing URL into:
     `money_factory/first_eur5_fast_path/LIVE_PRODUCT_URL.txt`

---

## 3. COURIER MAY DO AFTER APPROVAL (Autonomous Safe Operations)

1. **Unauthenticated Public Health Check**:
   - Perform an unauthenticated HTTP GET request to the public URL in `LIVE_PRODUCT_URL.txt`.
   - Verify HTTP 200 response, verify product title string, and confirm €5 price tag.
2. **Order Pickup & Evidence Transition**:
   - Monitor the local pickup directory (`money_factory/inbox/orders/`) for order receipts or webhook payloads dropped by the operator.
   - Advance the 7-stage state machine in `REVENUE_EVIDENCE_CONTRACT.json` from `PRODUCT_READY` toward `SETTLED_REVENUE`.
3. **Economic Ledger Logging**:
   - Append cryptographically verifiable transaction hashes to `money_factory/evidence_ledger.js`.

---

## 4. COURIER MUST NEVER DO WITHOUT NEW APPROVAL (Strict Negative Bounds)

- **NEVER attempt automated login or credential extraction**: Courier has no browser session, no passwords, no API tokens, and zero access to human banking credentials.
- **NEVER initiate autonomous financial spend**: Autonomous spend limit remains strictly **€0.00**.
- **NEVER send outbound promotional messages**: Zero automated tweets, Reddit posts, emails, or cold outreach.
- **NEVER modify or withdraw payout balances**: Courier has zero capability or permission to touch financial payout flows.
- **NEVER touch Mac host or `universuX`**: Mac host and protected repositories remain strictly off-limits.
