# Revenue Engine Defaults (RV-03, RV-05, RV-06)

## RV-03 (3 sample reports)
Since exact output formats were not specified, Courier Symphony defaults to a standard PDF and Markdown combination containing:
1. **Lead Qualification Summary**: Overview of problem domain and alignment with Courier services.
2. **Security & Compliance Report**: Artifact verification, safety guarantees, and zero-hang resilience validation.
3. **Execution Proposal**: Hourly breakdown, cost estimations, and expected SLA.

## RV-05 (AGB / Liability Limits)
**Courier Liability Limitation:**
- Courier acts as an autonomous agent provider. Liability for direct damages is limited to the value of the active Spend Grant.
- Courier is not liable for indirect, incidental, or consequential damages arising from the automated execution of third-party APIs.
- All code and actions generated are bound by the safety verifier; however, the client assumes final responsibility for merged code (via HUMAN_REVIEW_REQUIRED).

## RV-06 (Business / Tax Invoicing)
**Invoicing Parameters:**
- **VAT Rule**: Reverse charge mechanism applied for B2B cross-border transactions within the EU. Standard local VAT applies for domestic transactions.
- **Invoicing Cycle**: Net-30 terms triggered upon `WON` state completion. 
- **Currency**: All jobs are calculated and billed in EUR (€).
