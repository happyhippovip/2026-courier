# Scope & Exclusions — €99 AI Agent Reliability Check

## Included Scope
1. **Single Workflow Focus:** Evaluation covers exactly ONE defined agentic workflow (e.g. code generation loop, scraper pipeline, or research worker).
2. **Read-Only & Sanitized Review:** Analysis of process supervision, lock files, signal handling, and state persistence logic.
3. **10-Point Determinism Matrix:** Each check graded strictly as `PASS`, `FAIL`, or `UNKNOWN (INSUFFICIENT_SAFE_EVIDENCE)`.
4. **Reproducible Test Harness:** Standalone Python verification script proving failure/success boundaries.
5. **Prioritized Action Plan:** Severity-ranked fixes with reference code patterns.

---

## Strict Exclusions & Non-Claims
1. **NO CERTIFICATION CLAIMS:** This check is a deterministic architectural evaluation, not a regulatory compliance certification (e.g., SOC 2, ISO 27001, EU AI Act).
2. **NO PENETRATION TESTING:** We do not perform black-box penetration testing, network vulnerability scanning, or dynamic exploit analysis.
3. **NO GUARANTEED OUTCOMES:** We promise the agreed diagnostic evaluation and deliverable report. We do not guarantee a specific uptime percentage, cost savings, or absence of software bugs.
4. **NO PRODUCTION CODE MODIFICATIONS:** Deliverables include standalone reference fixes; production codebase modification remains the client's responsibility.

---

## FORBIDDEN CUSTOMER INPUTS (Strictly Prohibited)
Clients MUST NOT provide and we will immediately reject:
- Passwords or passphrases
- Production LLM API keys (OpenAI, Anthropic, Gemini, etc.)
- OAuth / session / bearer tokens
- Browser session cookies or authentication state
- Private cryptographic keys or certificates
- Account recovery codes or MFA secrets
- Payment credentials or billing tokens
- Production database connection strings or credentials
- Unrestricted cloud provider IAM credentials
- Secret-bearing `.env` or configuration files
- Unnecessary personal, customer, or confidential end-user data

*Rule: If safe, sanitized inputs are insufficient to perform the evaluation, the engagement is halted before payment is processed.*
