# INTEGRATION CANDIDATES — WINDOWS TO MAC COURIER HARDENING LAB

The following proven hardening modules and invariant checks from the V2 lab are ready for integration into Courier:

1. **Formal Lifecycle Transition Matrix Guard**
   - *Source*: `MODELS/formal_lifecycle_model.js`
   - *Impact*: Enforces 39 legal transitions and strictly blocks all 217 illegal shortcuts fail-closed.

2. **Logical Work Identity Engine**
   - *Source*: `MODELS/logical_identity_engine.js`
   - *Impact*: Decouples physical worker routing metadata from canonical task identity.

3. **Strict Fallback Precondition Engine**
   - *Source*: `MODELS/fallback_policy_engine.js`
   - *Impact*: Ensures fallback is permitted ONLY on `DEFINITE_NO_EFFECT`.

4. **Multi-Factor Process Lease Engine**
   - *Source*: `MODELS/process_lease_engine.js`
   - *Impact*: Combines PID, start time, task ID, and command line to eliminate PID recycling risks.

5. **Border Guard & 42-Field Passport Customs Engine**
   - *Source*: `MODELS/border_and_customs_v2.js`
   - *Impact*: Blocks unauthorized spend, egress, and path traversal; enforces 42-field signed passports.

6. **Append-Only Cryptographic Hash-Chain Ledger**
   - *Source*: `MODELS/money_factory_and_ledger_v2.js`
   - *Impact*: Protects ledger immutability and enforces `REAL_REVENUE_EUR = 0` simulation bounds.
