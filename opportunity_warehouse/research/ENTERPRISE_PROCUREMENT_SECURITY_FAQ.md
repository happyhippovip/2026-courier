# Enterprise Procurement & Information Security Dossier
**Product**: agent-context-trimmer v1.0.0  
**Vendor**: Symphony Autonomous Commercial Division  
**Classification**: Developer CLI / Local Offline Build Tool  
**Compliance Target**: SOC 2 Type II, GDPR, ISO 27001 readiness

---

## Section 1: Architecture & Data Privacy

### Q1.1: Does agent-context-trimmer transmit customer prompts or source code to external servers?
**Answer**:  
**NO.** agent-context-trimmer is an offline CLI and Node.js module. It performs 100% of AST parsing, rule deduplication, and prompt pruning locally on the customer's host machine. There are **zero outbound network connections**, zero telemetry beacons, and zero analytic pings.

### Q1.2: Where is prompt context processed and stored?
**Answer**:  
All processing occurs strictly in volatile RAM. No prompt context, intermediate AST trees, or cached system instructions are written to persistent disk unless explicitly instructed via the `--output` flag by the local developer.

### Q1.3: What third-party runtime dependencies are bundled?
**Answer**:  
**Zero (0).** agent-context-trimmer is authored strictly with native Node.js core modules (`fs`, `path`, `crypto`). There is no reliance on external npm packages, eliminating supply chain attacks (e.g. `event-stream`, prototype pollution). A full CycloneDX SBOM is provided.

---

## Section 2: Licensing, Governance & Auditing

### Q2.1: How does license verification work in air-gapped enterprise environments?
**Answer**:  
The tool uses asymmetric cryptographic ECDSA signature verification. Enterprise license keys are cryptographically signed offline and verified locally against our public key. **Zero network calls** to a licensing server are required.

### Q2.2: Is GDPR and PII compliance maintained?
**Answer**:  
Yes. The built-in PII Redactor module automatically detects and masks emails, IPv4/IPv6 addresses, JWT tokens, and bearer credentials prior to emitting trimmed logs or debug traces.

### Q2.3: How are security vulnerabilities handled?
**Answer**:  
Security disclosures receive priority SLA triage within 4 business hours. Patches are distributed via cryptographically signed tarballs with published SHA-256 digests.

---

## Section 3: Merchant of Record & Financial Governance

### Q3.1: Who acts as Merchant of Record?
**Answer**:  
Gumroad, Inc. acts as the Merchant of Record. Gumroad handles global sales tax, VAT calculation, collection, and automated remittance across all EU member states, the UK, US, and APAC jurisdictions.

### Q3.2: Can enterprise customers pay via Corporate Invoice / Wire Transfer?
**Answer**:  
Yes. For Team and Enterprise Tier licenses (€99–€799/yr), we support standard SEPA, ACH, and wire transfer upon request with 30-day net payment terms.
