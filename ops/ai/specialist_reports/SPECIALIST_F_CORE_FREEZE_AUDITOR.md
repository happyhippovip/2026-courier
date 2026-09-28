# Specialist Report F — Core Freeze Auditor

**Role**: `CORE_FREEZE_AUDITOR`  
**Host**: MAC  
**Status**: AUDITED / BLOCKED ON CW  

---

```text
CORE_FREEZE_MATRIX=
| Criterion | Required Target | Current Evidence | Verdict |
|---|---|---|:---:|
| 1. Trusted Ledger | Reconciled & Append-Only | 91 ledger tasks reconciled, 100 L100 tasks on disk | PASS |
| 2. Reliable Motor | Deterministic State Dispatch | server/app.py state machine mutex protected | PASS |
| 3. Effect Chain | Result -> Verify -> Reconcile -> Next | Tests 11/11 green; verified in Canary RUN_1 | PASS |
| 4. Zero-Human Relay | HUMAN_RELAY_COUNT == 0 | RUN_1 & RUN_2 physical proof bundles: 0 relays | PASS |
| 5. Restart Matrix | 9/9 Failure Scenarios Handled | Evaluated in Family 07 & Specialist D | PASS |
| 6. A4 Covered Surface | Scoped strictly to 5 candidate files | Confirmed 5-file scope in Family 18 | PASS |
| 7. Resource Bounds | MAX_HEAVY_JOBS <= 1 | Enforced across all Mac workers | PASS |
| 8. No Tight Polling | Truthful idle backoff | 300s lease, exponential backoff, sleep 900 | PASS |
| 9. Proof Cards | Fully populated Proof Card | Specialist E card template complete | PASS |
| 10. Fingerprint Chain | Source/Build/Runtime Binding | Commit 4c1e24cc + py_compile + test digests | PASS |
| 11. Hash Authority | Task owns expected_sha256 | P0 Defect 1 identified; pending CW fix | OPEN |
| 12. Duplicate Match | Full identity tuple comparison | P0 Defect 3 identified; pending CW fix | OPEN |

PROVEN=
- Trusted Ledger durability
- Zero-human relay A -> B execution
- Restart resilience without redundant re-execution
- Fail-closed malformed target rejection
- Resource safety (MAX_HEAVY_JOBS=1)

OPEN=
- Central Writer fix for worker expected_sha256 authority (P0 Defect 1)
- Central Writer fix for duplicate match tuple completeness (P0 Defect 3)
- Trailing whitespace cleanup for git diff --check (P0 Defect 4)

BLOCKED=
- Core Freeze sign-off is BLOCKED on Windows Central Writer committing FINAL_SHA.

UNKNOWN=
- None. All defects are causally identified down to exact line numbers and functions.

EARLIEST_CAUSAL_BLOCKER=
- Windows Central Writer commit delivering FINAL_SHA resolving Q027.
```
