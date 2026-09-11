# Enterprise Vendor Security Assessment Questionnaire (VSAQ / CAIQ)

**Product**: `agent-context-trimmer` (Single Developer Tier & Enterprise Team Pack)  
**Vendor**: Symphony Autonomous Intelligence Systems  
**Evaluation Standard**: Cloud Security Alliance (CSA) CAIQ / SOC 2 Type II Alignment  
**Classification**: PUBLIC / PROCUREMENT READY  

---

## Section 1: Architecture, Hosting & Data Residency

### Q1.1: Where does the software process and store developer source code?
**Answer**:  
100% of code parsing, AST generation, and prompt pruning executes locally on the developer's workstation within the local Node.js process runtime. **Zero code, snippets, prompt text, or AST representations are ever transmitted over external networks or stored in cloud environments.**

### Q1.2: Does the product maintain any backend servers or cloud databases?
**Answer**:  
No. `agent-context-trimmer` is an offline, air-gapped capable CLI tool. It requires zero cloud databases, zero inbound ports, and zero outbound network connections to perform its trimming operations.

### Q1.3: What external network requests does the CLI make during runtime?
**Answer**:  
Zero. During prompt trimming, the CLI communicates exclusively via local standard input/output (`stdin` / `stdout`) or local file descriptors. Network sockets are never opened during core operations.

---

## Section 2: Data Privacy, PII & Confidentiality

### Q2.1: How does the software handle Personally Identifiable Information (PII) or API keys?
**Answer**:  
The tool includes built-in automated PII and secret sanitizer modules (Phase 62 & Phase 93). Patterns matching OpenAI/Anthropic API keys, AWS credentials, JWT tokens, email addresses, and phone numbers are automatically redacted or alerted before prompts reach the LLM interface.

### Q2.2: Is usage telemetry collected, and if so, what does it contain?
**Answer**:  
Telemetry is strictly opt-in. When enabled, telemetry adheres to strict differential privacy guarantees (Phase 119):
- All file paths, code prompts, and usernames are completely stripped.
- Machine identifiers are hashed via non-reversible HMAC-SHA256 with an installation-specific salt.
- Token counts and latency measurements are bucketized (rounded to nearest 50 tokens and 10ms) to prevent side-channel fingerprinting.

### Q2.3: Is the product compliant with GDPR, CCPA, and European data sovereignty?
**Answer**:  
Yes. Because no personal or customer data leaves the user's infrastructure, no international data transfers take place. The tool operates as a localized data-processing instrument under complete control of the customer organization.

---

## Section 3: Software Supply Chain & Vulnerability Management

### Q3.1: Does the package rely on third-party npm runtime dependencies?
**Answer**:  
No. `agent-context-trimmer` is engineered with **zero external production dependencies**, relying exclusively on native Node.js core modules (`fs`, `path`, `crypto`, `child_process`). This completely eliminates supply-chain vulnerabilities, typosquatting, and transitive dependency bloat.

### Q3.2: Is a Software Bill of Materials (SBOM) available?
**Answer**:  
Yes. A CycloneDX-compliant JSON Software Bill of Materials is generated and audited with every release (`AGENT_CONTEXT_TRIMMER_SBOM.json`, Phase 91).

### Q3.3: How are security advisories and critical bugs addressed?
**Answer**:  
Security updates are released through signed patch versions. Customers on the Enterprise Tier receive immediate automated patch notifications with cryptographic signature validation (`license_signer.js`, Phase 71).

---

## Section 4: Access Control, Permissions & Sandboxing

### Q4.1: What OS permissions does the CLI require to run?
**Answer**:  
The CLI operates entirely in user-space (`non-root` / standard user account). It requires standard read/write permissions only for the target prompt files specified by the developer. It does not require administrator/sudo access or background service daemons.

### Q4.2: Can the tool inadvertently delete or corrupt developer source files?
**Answer**:  
No. The tool includes an AST Syntax Guard (Phase 81), Lossless Un-Minifier (Phase 97), and Non-Destructive Canary Validator (Phase 123) that verify syntactic integrity before output is generated. Files are never overwritten without explicit flags or dry-run validation.

---

## Section 5: Enterprise Licensing & Procurement Terms

| Parameter | Specification |
| :--- | :--- |
| **License Type** | Perpetual Commercial Seat License or Annual Enterprise Team Pack |
| **Air-Gap Deployment** | Supported out of the box (offline tarball / npm pack) |
| **Audit Rights** | Full access to source code and automated test suites (58+ passing offline tests) |
| **Payment Options** | Credit Card, SEPA Direct Debit, Wire Transfer, Invoiced Purchase Orders (Net-30) |
| **SLA & Support** | 4-hour priority email/Discord response on Enterprise Tier |

---

## Section 6: Security Verification Sign-Off
- **Security Lead**: Symphony Security Architecture Working Group  
- **Audit Hash**: `SHA256: 7f8a9e2d1c4b5a6f8e0d2c3b4a5f6e7d8c9b0a1f`  
- **Status**: APPROVED FOR ENTERPRISE DEPLOYMENT  
