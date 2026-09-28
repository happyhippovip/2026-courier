# Family 14: First-Friend UX Readiness & Grandma-Test Surface

Status: SPECIFIED
Design Rule: Minimum Honest Truth Surface. Zero vanity metrics. Zero giant dashboards.

---

## 1. The 4 Essential User Truth States

```
+--------------------------------------------------------------------------+
|  [ARBEITET]                                                             |
|  Courier is currently working on: "Build clean reporting pipeline"       |
|  Step 2 of 4: Generating artifact summary                                |
|  Capacity: 1 worker active | CPU healthy | Tokens normal                |
+--------------------------------------------------------------------------+

+--------------------------------------------------------------------------+
|  [! BRAUCHT DICH]                                                        |
|  Courier paused because: "Ambiguous instruction on config file"          |
|  Question: Should we overwrite config.json or create config.bak?         |
|  [Keep existing]   [Overwrite]   [Skip this step]                        |
+--------------------------------------------------------------------------+

+--------------------------------------------------------------------------+
|  [FERTIG]                                                                |
|  Goal completed: "Generate weekly report & test matrix"                  |
|  Verified outputs: report.md (Verified PASS by independent SHA)          |
|  Time elapsed: 4m 12s | Cost: €0.08                                      |
+--------------------------------------------------------------------------+

+--------------------------------------------------------------------------+
|  [NEXT ACTION]                                                           |
|  Courier suggests next step: "Publish report to team repo"               |
|  [Start this now]   [Edit goal]   [Exit]                                 |
+--------------------------------------------------------------------------+
```

---

## 2. Truth Distinctions: Verified vs Reported vs Unknown

- **VERIFIED (Green Check):** The effect was independently confirmed by an isolated verifier inspecting actual server bytes. Customer can 100% trust this result.
- **REPORTED (Yellow Warning):** The worker claimed the task succeeded, but independent verifier confirmation has not yet completed.
- **UNKNOWN (Red Flag):** Execution state is ambiguous (e.g. process died mid-flight). Courier stops and alerts rather than making false claims.

---

## 3. The 6 Grandma Test Answers

1. **What did I ask?** -> Display original plain-language goal text prominently.
2. **Is Courier working?** -> Clear green spinner with current active task name.
3. **What actually finished?** -> Concrete list of verified files created on disk.
4. **Was it verified?** -> Plain text: *"Checked and confirmed by verifier"*.
5. **Does Courier need me?** -> Red banner only when human decision is genuinely required; zero permission spam.
6. **What happens next?** -> Clear statement: *"Next: Step 3 will automatically start in 5 seconds"*.
