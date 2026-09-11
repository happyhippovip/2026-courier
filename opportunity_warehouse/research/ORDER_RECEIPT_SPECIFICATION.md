# ORDER RECEIPT SPECIFICATION & REVENUE SETTLEMENT CONTRACT
**DOCUMENT:** `opportunity_warehouse/research/ORDER_RECEIPT_SPECIFICATION.md`  
**TARGET DIRECTORY:** `money_factory/inbox/orders/`  
**PURPOSE:** Define the exact machine-readable receipt schema required to satisfy `EvidenceLedger` and unlock 100% Commercial Truth.

---

## 1. Zero-Friction Settlement Flow

When customer #1 purchases `agent-context-trimmer v1.0.0` on Gumroad:
1. Gumroad displays the order confirmation screen and sends an email receipt.
2. The operator (or webhook forwarder) saves the transaction details as a JSON file into:
   `money_factory/inbox/orders/order_<ORDER_ID>.json`
3. The Money Factory Revenue Observer reads the file, cryptographically validates the fields, logs the transaction hash to `money_factory/evidence_ledger.js`, and advances Symphony progress to **100%**.

---

## 2. Mandatory Schema Fields

```json
{
  "order_id": "GUMROAD-ORD-12345678",
  "product_id": "agent-context-trimmer-v1",
  "product_name": "Agent Context Trimmer CLI (v1.0.0)",
  "gross_amount_eur": 5.00,
  "net_amount_eur": 4.20,
  "currency": "EUR",
  "payment_processor": "GUMROAD",
  "purchased_at_utc": "2026-09-11T12:00:00.000Z",
  "customer_country": "DE",
  "receipt_url": "https://gumroad.com/receipt?id=12345678",
  "refunded": false,
  "disputed": false,
  "verification_source": "HUMAN_OPERATOR_FORWARDED"
}
```

---

## 3. Inviolable Invariant Rules
1. `gross_amount_eur` must be $\ge 5.00$.
2. `currency` must be `EUR` (or equivalent in `USD` with rate $\ge$ €5.00).
3. `refunded` and `disputed` must be strictly `false`.
4. `order_id` must be a unique, non-empty external identifier.
5. Simulated or test orders (`FAST_TEST_MODE`) are strictly rejected by `EvidenceLedger`.

---

## 4. Verification Check
Once the file is placed, run:
```powershell
node money_factory/first_eur5_fast_path/run_revenue_observer.js
```
The counter will automatically advance:
* **Current Proven Revenue:** €0.00 $\to$ **€5.00**
* **Symphony Progress:** 97% $\to$ **100%**
* **Status:** `COMMERCIAL_TRUTH_PROVEN`
