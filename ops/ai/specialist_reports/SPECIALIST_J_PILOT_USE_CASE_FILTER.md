# Specialist Report J — Pilot Use-Case Filter

**Role**: `PILOT_USE_CASE_FILTER`  
**Host**: MAC  
**Status**: COMPLETE / PREPARED  

---

```text
PILOT_SELECTION_CRITERIA=
1. Recurring Manual Coordination Pain: Candidate routinely runs multi-step tasks across terminal, scripts, or multiple sessions where context drops cause repetitive rework.
2. Digital Executability: Task produces verifiable digital artifacts (code changes, test suites, reports, exports, configs).
3. Clear Before/After Value: Measurable reduction in babysitting hours (from 45 mins manual relay to 2 mins review).
4. Short Time-to-Proof: First goal completes and verifies within 15 minutes of initial onboarding.
5. Willingness-to-Pay Testability: High consequence of task dropping or state loss; clear economic ROI.
6. Setup Burden: Can be configured in <= 15 minutes using local Python environment without admin rights.
7. Low Support Burden: User comfortable running shell commands; understands Grandma-Test 3-state UI.
8. Bounded Data Scope: Work conducted within dedicated project directory; no sensitive production credentials.

CANDIDATE_TEMPLATE=
- Candidate Profile: Senior Developer / Freelance Engineer / Technical Founder
- Primary Pain Point: Context loss across IDE/CLI restarts; babysitting long-running workflows
- Pilot Task: End-to-end repository audit, automated regression testing, and report generation
- Expected Duration: 1-2 hours overnight
- Success Metric: Next-day resume shows completed and verified artifacts without manual prompts

DISQUALIFIERS=
- Tasks requiring real financial transactions or production payment credentials
- Tasks requiring broad uncontrolled filesystem write access across root
- Tasks with undefined acceptance criteria (cannot be verified by independent verifier)
- Users requiring a graphical 1-click native desktop installer on Day 1

FIRST_CONTACT_QUESTIONS=
1. "Which multi-step task do you currently babysit or repeat because tools lose context?"
2. "If Courier runs this overnight and presents verified artifacts in the morning, what exact file proves it succeeded?"
3. "Are you willing to spend 10 minutes setting up a local virtual environment to test this today?"
```
