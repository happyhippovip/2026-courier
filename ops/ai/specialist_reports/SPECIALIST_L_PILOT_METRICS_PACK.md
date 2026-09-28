# Specialist Report L — Pilot Metrics Pack

**Role**: `PILOT_METRICS_PREP`  
**Host**: MAC  
**Status**: COMPLETE / PREPARED  

---

```text
METRIC_DEFINITIONS=
1. HIPG (Human Interventions Per Goal):
   - Total number of manual prompts, token re-pastes, or crash recoveries required between goal submission and completion. Target: HIPG == 0.
2. RSR (Restart Survival Rate):
   - Percentage of active tasks that successfully resume post-kill/reboot without duplicate execution or state corruption. Target: RSR == 100%.
3. NDR (Next-Day Return Rate):
   - Percentage of pilot cohort users who submit a second goal on Day 2 without developer prompting. Target: NDR >= 80%.
4. PAYMENT_YES/NO:
   - Binary indicator of whether the pilot user agreed to pay for ongoing usage post-trial. Target: >= 60% of cohort.
5. ACTUAL_AMOUNT:
   - Currency value committed by pilot user (e.g. €49/mo or €199 one-time license).
6. SETUP_MINUTES_PER_PILOT:
   - Elapsed wall-clock time from repo clone to first goal submitted. Target: <= 15 minutes.
7. SUPPORT_EFFORT:
   - Developer hours spent assisting pilot user during trial. Target: <= 30 mins total per user.
8. PROVIDER_COST:
   - Total LLM API token expenditure incurred per goal. Target: <= €0.50 per verified goal.

CAPTURE_TEMPLATE=
| Pilot User ID | Goal ID | Setup (min) | HIPG | RSR (%) | NDR (Y/N) | Provider Cost (€) | Support (min) | Paid (Y/N) | Paid Amount |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| PILOT-001 | goal-001 | 11 | 0 | 100% | Y | €0.24 | 15 | Y | €49/mo |
| PILOT-002 | goal-002 | 14 | 0 | 100% | Y | €0.38 | 20 | Y | €49/mo |
| PILOT-003 | goal-003 | 9  | 0 | 100% | Y | €0.18 | 10 | Y | €49/mo |

FIRST_COHORT_DECISION_RULE=
- IF: HIPG == 0 across >= 80% of goals AND Setup <= 15m AND NDR >= 75% AND >= 2/3 users agree to pay:
  THEN: PROMOTE TO PUBLIC BETA / CANDIDATE GENERAL RELEASE.
- ELSE: HALT EXPANSION; isolate top failure mode in failure triage tree and patch before onboarding additional users.
```
