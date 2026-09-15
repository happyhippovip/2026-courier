# Customer Pilot Project Intake Form — Courier Symphony

This intake form is used by customers to submit their candidate pilot project for evaluation and remediation by Courier Symphony.

---

> [!WARNING]
> ### Critical Safety & Human Gate Notice
> Courier Symphony utilizes **autonomous orchestration with Human Gates**. 
> **NO PRODUCTION DEPLOYMENT WILL OCCUR.**
> Courier Symphony operates strictly in an isolated evaluation environment. Autonomous remediation patches and verification logs are generated, but **no changes will ever be pushed or deployed to external/production environments**.
> You must explicitly review, verify, and provide a **Human Gate approval** before any patch is accepted or merged into your downstream workflows.

---

## 1. Exact Customer Inputs

**A. Isolated Repository**
* **Repository URL / Link:** `[e.g., https://github.com/acme-corp/pilot-repo-sandbox]`
* **Target Branch / Commit SHA:** `[e.g., pilot/remediation-v1]`
* *Note: Ensure this repository is isolated from production systems and contains sanitized test data.*

**B. ONE Bounded Remediation Task**
* **Task Name / Identifier:** `[e.g., FIX-402: Resolve concurrency deadlock in token refresher]`
* **Task Scope & Description:**
  ```text
  [Describe the single bug, edge-case failure, error trace, or bounded remediation needed]
  ```

**C. Deterministic Acceptance Test**
* **Exact Acceptance Test Command:**
  ```bash
  # e.g., pytest tests/test_token_manager.py -v -k "test_token_refresh_race"
  <EXACT_TEST_COMMAND_HERE>
  ```
* **Expected Pass (Post-remediation):** `[Exit code 0, all targeted assertions passing]`

---

## 2. Exact Deliverables (Outputs)

Upon completion of the orchestration cycle, Courier Symphony will return:
1. **A reviewable change/diff** implementing the remediation.
2. **Verification evidence** demonstrating successful execution of your deterministic acceptance test.

---

## 3. Human Gate & Safety Acknowledgment

Please confirm your understanding of the execution boundaries:

- [ ] **Isolated Environment:** The repository link provided is an isolated environment containing sanitized mock data and no production secrets.
- [ ] **No Production Deployment:** I understand and acknowledge that no automatic deployment to production will occur.
- [ ] **Explicit Human Gate Approval Required:** I acknowledge that a designated engineer must explicitly inspect the generated diff, review the verification evidence, and provide **Human Gate approval** before applying changes.

* **Designated Human Gate Reviewer:** `[Name / Email of approving engineer]`
* **Sign-off / Date:** `[YYYY-MM-DD]`
