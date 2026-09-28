# Family 14: First-Friend UX Readiness & Truth Surface

**Status**: SPECIFIED  
**Principle**: Minimal Honest Truth (The "Grandma Test")  
**Format**: Streamlined Terminal / Single-File Status View

---

## 1. The 5 Core Truth States

A non-technical user or busy developer must understand system state in 3 seconds without deciphering debug logs:

```
+-----------------------------------------------------------------------+
| COURIER SYMPHONY                                                      |
| Goal: "Refactor database migrations and verify test suite"           |
+-----------------------------------------------------------------------+
| STATUS:      ARBEITET (Working)                                       |
| PROGRESS:    Step 2 of 4                                              |
| CURRENT:     Running integration tests on Mac worker                  |
| VERIFIED:    [PASS] Step 1: SQL schema generated & validated          |
| DOES IT NEED YOU?  NEIN (Zero input required right now)              |
| NEXT ACTION: Will automatically verify test results and commit        |
+-----------------------------------------------------------------------+
```

### The 4 High-Level User Indicators

1. **ARBEITET (Working)**:
   - Green status indicator.
   - Tells user: "Courier is making progress; you can close your laptop or work on something else."
2. **BRAUCHT DICH (Needs You)**:
   - Yellow/Amber status indicator.
   - Explains exactly why in 1 plain English sentence: "Please confirm permission to run migration against staging database."
   - Prompts with a simple `[Y/N]` or write-in decision.
3. **FERTIG (Finished)**:
   - Blue status indicator.
   - Displays: What was delivered + cryptographic verification proof.
4. **BLOCKIERT / UNBEKANNT (Blocked / Unknown)**:
   - Red status indicator.
   - Explains failure condition without techno-jargon.

---

## 2. The Grandma Test Audit

| User Question | System Output | Pass/Fail |
|---|---|:---:|
| *What did I ask?* | Displays exact Goal Contract summary text. | **PASS** |
| *Is Courier working?* | Displays `ARBEITET` with live active step name. | **PASS** |
| *What actually finished?* | Displays list of completed steps with timestamp. | **PASS** |
| *Was it verified?* | Clearly labels results as `VERIFIED` (re-hashed & confirmed) vs `UNVERIFIED`. | **PASS** |
| *Does Courier need me?* | Explicit `BRAUCHT DICH: NEIN` or `JA: [Reason]`. | **PASS** |
| *What happens next?* | Explicit `NEXT ACTION: Auto-dispatching Step 3`. | **PASS** |
