# WALL-P2-FAQ-MAC10 — Website FAQ (evidence-gated)

RULE: every CLAIM below carries CURRENTLY_PROVEN + EVIDENCE_SOURCE +
SAFE_TO_PUBLISH_NOW. Unproven claims stay OFF the site until proven.

## What does Courier actually do?
Runs one task at a time through TASK → EXECUTE → RESULT → PERSIST →
VERIFY → DONE → NEXT, unattended, with every step recorded.
- CLAIM=unattended chained execution with audit trail.
- CURRENTLY_PROVEN=YES (local + test evidence).
- EVIDENCE_SOURCE=dispatcher/adapter recovery tests (41 passed),
  ack/duplicate tests, crash/resume torture tests (repo test suite).
- SAFE_TO_PUBLISH_NOW=YES (as "in pilot", not "generally available").

## What happens if a worker crashes mid-task?
The task is not blindly re-run. Ambiguous outcomes quarantine to human
review; persisted results are re-sent identically, never recomputed.
- CLAIM=no blind replay; no duplicate execution on crash.
- CURRENTLY_PROVEN=YES (unit/contract level).
- EVIDENCE_SOURCE=test_restart_resume_torture, test_motor_crash_swallow,
  ACK_DUPLICATE/CONTRADICTORY_DUPLICATE pins.
- SAFE_TO_PUBLISH_NOW=YES with "verified in testing" qualifier.

## What if the same result arrives twice?
Identical resends are acknowledged without re-execution; contradictory
second results are rejected (409) for human review.
- CLAIM=duplicate-safe result intake.
- CURRENTLY_PROVEN=YES (unit/contract level).
- EVIDENCE_SOURCE=test_result_duplicates (ACK_DUPLICATE + CONTRADICTORY).
- SAFE_TO_PUBLISH_NOW=YES with qualifier.

## Does it retry failed work forever?
No. Retries are bounded (e.g. provider waits capped, then terminal +
blocked with reason). Auth failures are a known improvement area:
currently consume retry budget before failing terminal.
- CLAIM=bounded retries, no infinite loops.
- CURRENTLY_PROVEN=YES for bounds; auth fail-fast NOT YET.
- EVIDENCE_SOURCE=test_server_infinite_retry; probe of 401→PROVIDER_WAIT
  classification (backlog JOKER-AUTH-PROVIDERWAIT-01).
- SAFE_TO_PUBLISH_NOW=PARTIAL — publish bounds claim; do NOT publish
  "smart retry" or "fail-fast auth" until fixed and pinned.

## Does it run on Windows and Mac?
Mac execution is tested; Windows workers can claim tasks. Windows result
delivery against the current server contract is a known open gap.
- CLAIM=cross-platform workers.
- CURRENTLY_PROVEN=PARTIAL.
- EVIDENCE_SOURCE=results/E10-windows-portability.md (schema mismatch
  → 400 on current lineage).
- SAFE_TO_PUBLISH_NOW=NO for "Windows supported" — publish only
  "Mac pilot; Windows in preparation".

## How often must I click approve?
Once per project scope. Inside the scope Courier proceeds silently; it
re-asks only for money, credentials/2FA, publishing, destruction,
out-of-scope writes, or irreversible effects.
- CLAIM=no permission spam.
- CURRENTLY_PROVEN=YES (operational pattern, documented rule).
- EVIDENCE_SOURCE=reports/RV02_NO_PERMISSION_SPAM.md.
- SAFE_TO_PUBLISH_NOW=YES as product principle (pilot terms).

## Can I see proof, not promises?
Yes: every task gets a proof card (task, status, result, verified-by,
timestamps, human-intervention count). Live metrics only — no fabricated
counters.
- CLAIM=per-task verifiable proof.
- CURRENTLY_PROVEN=PARTIAL (spec RV08 exists; live metrics pending).
- SAFE_TO_PUBLISH_NOW=YES for the card spec; metrics section stays
  hidden until real numbers exist.

## Is my data safe?
Least-privilege scoped workspaces; credentials never in task payloads;
revocation stops work and freezes state. (Details: privacy/dataflow page
WALL-P2-PRIVACY-DATAFLOW-MAC-21.)
- CLAIM=scoped, revocable, auditable operation.
- CURRENTLY_PROVEN=PARTIAL (design + hygiene regression test
  test_server_does_not_leak_bearer_token).
- SAFE_TO_PUBLISH_NOW=YES as principle; no compliance badges (SOC2/ISO:
  explicitly NOT claimed).
