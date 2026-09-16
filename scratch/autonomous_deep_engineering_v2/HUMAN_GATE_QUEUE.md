# HUMAN GATE POLICY QUEUE — STRICT VERIFICATION BOUNDARIES

The following operations are formally classified as high-risk and are intercepted by fail-closed Human Gates:

1. **Live Real-Money / Asset Operations**
   - *Trigger*: Any transaction with `REAL_REVENUE_EUR > 0`, live wallet connection, or banking settlement.
   - *Contract*: Requires explicit human approval token; automated simulation bypass strictly forbidden.

2. **External Git Release Tagging & Production Deployment**
   - *Trigger*: Invocation of `git push`, release tagging, or production artifact publishing.
   - *Contract*: Blocked fail-closed in hardening lab.

3. **Master Cryptographic Key Deletion / Destruction**
   - *Trigger*: Deletion of root certificates or master HMAC signing secrets.
   - *Contract*: Irreversible action requiring dual-factor manual confirmation.

4. **Uncertain Mid-Flight Crash Reconciliation with Side-Effects**
   - *Trigger*: Crash recovery classified as `EXECUTION_UNCERTAIN` where external effects cannot be proven zero.
   - *Contract*: Manual triage required before redispatch.
