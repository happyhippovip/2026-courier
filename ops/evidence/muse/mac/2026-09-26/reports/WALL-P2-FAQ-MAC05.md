# WALL-P2-FAQ — draft (evidence-gated copy, PREP ONLY)

WORKER=MAC-05 (MUSE) · HOST=MAC · MODE=READ_ONLY · 2026-09-26
DEDUPE NOTE: sibling FAQs landed same window (WALL-P2-FAQ-MAC10/MUSE-15/MUSE-SUP).
MAC10 covers crash/duplicate mechanics in depth — this file defers to it on Q1/Q3
mechanics and is UNIQUE on permission-spam (Q5), pricing (Q6), availability (Q7),
AWS/Meta (Q8), 48h mode (Q9). Q4 here is deliberately more conservative than
MAC10 (names the open DUPADD edge); both agree on unit-level proof + qualifiers.
Sources: docs/WEBSITE_BLUEPRINT_2026.md (HEAD 332a42f9), permission rules
(b123768d), fast-track 48h (38d70e97), Z01 evidence index
(muse_zero_interference/MAC-muse-01a0d7e1-1790434092/Z01_EVIDENCE_INDEX.md).
Rule: every public line below carries CLAIM / CURRENTLY_PROVEN / EVIDENCE_SOURCE /
SAFE_TO_PUBLISH_NOW. ASPIRATION lines may only ship inside HONEST LIMITS framing.

---

## 1. What does Courier do?

COPY: "Courier runs computer work step by step: it takes a task, executes it,
checks the result, stores proof, and continues with the next task — all inside
a project you approved."
- CLAIM=Courier executes tasks with result check + proof + continuation
- CURRENTLY_PROVEN=YES (mechanism exists in test and fixture runs)
- EVIDENCE_SOURCE=server/app.py claim/result/verify endpoints; cannon motor run_step;
  GM5 canary A→VERIFY→B fixture
- SAFE_TO_PUBLISH_NOW=YES

## 2. Does it work without a human watching?

COPY: "In isolated test runs, yes: one task finished, was checked, and the next
started with zero human messages between steps. Continuous unattended operation
is what we are proving next — it is not claimed yet."
- CLAIM=zero-human-relay continuation
- CURRENTLY_PROVEN=PARTIAL (fixture-scoped HUMAN_RELAY=0 only)
- EVIDENCE_SOURCE=GM5 canary fixture; full physical canary NOT run (Z01 NOT_PROVEN)
- SAFE_TO_PUBLISH_NOW=YES (only with the second sentence)

## 3. What happens when something is unclear or fails?

COPY: "Courier stops instead of guessing. Unclear results are parked for review;
nothing is silently retried, and crashed work is quarantined rather than replayed."
- CLAIM=fail-closed on unknown outcomes
- CURRENTLY_PROVEN=YES (unit-tested)
- EVIDENCE_SOURCE=tests/test_muse_wall_supervisor.py 10/10 (AMBIGUOUS→PAUSED_ERROR,
  RESULT_READY untouched); work_queue STALE_WORKER_EFFECT_AMBIGUOUS pin (94087def);
  server 409/400 guards on verify/result
- SAFE_TO_PUBLISH_NOW=YES

## 4. Can work be executed twice by accident?

COPY: "Double execution is blocked by design: only one worker can hold a task,
retries get fresh identities, and stale work is quarantined, not replayed.
One edge — re-submitting the exact same task — is a known tracked fix, not a
silent behavior."
- CLAIM=duplicate protection (+ honest open edge)
- CURRENTLY_PROVEN=PARTIAL (claim race single-winner proven; DUPADD guard OPEN)
- EVIDENCE_SOURCE=/tmp repros (claim-race, stale-reclaim); backlog
  MUSE04-DUPADD-IDENTITY-01 (READY, P1)
- SAFE_TO_PUBLISH_NOW=YES (only with the open-edge sentence)

## 5. Will it keep asking me "Allow / Proceed"?

COPY: "No. You approve a project once. Inside that project Courier works on its
own and only comes back for real decisions: money, logins, publishing,
irreversible steps, or anything outside the approved scope."
- CLAIM=scoped autonomy, no permission spam
- CURRENTLY_PROVEN=PRODUCT LAW (design commitment, permission rules doc;
  customer-default enforcement is roadmap, not measured product behavior)
- EVIDENCE_SOURCE=docs permission rules b123768d (NO_PERMISSION_SPAM + genuine-gate list)
- SAFE_TO_PUBLISH_NOW=YES (framed as how it is designed to behave)

## 6. What does it cost / is there pricing?

COPY: "There is no public pricing yet. Early pilots are scoped individually, and
every run tracks what it spends so cost per finished task is visible."
- CLAIM=cost visibility, no public pricing
- CURRENTLY_PROVEN=PARTIAL (cost tracking exists in design/ledger; per-task
  billing NOT a product surface)
- EVIDENCE_SOURCE=blueprint §pricing (later); cost ledgers internal
- SAFE_TO_PUBLISH_NOW=YES (no numbers published)

## 7. When can I use it? Is there a download?

COPY: "Not yet. Courier is in closed preparation: join the pilot list and we
contact you when a supervised pilot fits your work. There is no public download
or installer today."
- CLAIM=availability status
- CURRENTLY_PROVEN=YES (no installer exists — HONEST LIMIT)
- EVIDENCE_SOURCE=blueprint build order (§7 pricing/installer later); landing
  draft forbidden-claims list
- SAFE_TO_PUBLISH_NOW=YES

## 8. Is it an AWS / Meta product or partner?

COPY: "No. Courier is independent. It can run on standard cloud infrastructure;
no partnership is claimed."
- CLAIM=independence, no endorsement
- CURRENTLY_PROVEN=YES (no partnership exists)
- EVIDENCE_SOURCE=blueprint §§AWS/Meta alignment (explicit prohibitions)
- SAFE_TO_PUBLISH_NOW=YES

## 9. What is the 48-hour mode?

COPY: "A deadline mode for when you have little time left: Courier spends the
remaining capacity on the most valuable safe work first, keeps evidence, and
leaves a resumable result. It is a preparation concept that follows the same
safety rules — not a rush mode that skips checks."
- CLAIM=deadline-mode behavior
- CURRENTLY_PROVEN=PRODUCT LAW (concept doc; behavior not yet a product surface)
- EVIDENCE_SOURCE=fast-track doc 38d70e97 (status: preparation concept)
- SAFE_TO_PUBLISH_NOW=YES (framed as planned behavior, not shipped feature)

## 10. What can I actually see today?

COPY: "A supervised demo of the task → result → check → next-task chain, plus
the honest list on this page of what is proven, what is partial, and what is
still being built."
- CLAIM=demo availability + honesty contract
- CURRENTLY_PROVEN=YES (demo storyboard exists; evidence index maintained)
- EVIDENCE_SOURCE=WALL-P2-DEMO-STORYBOARD-MAC02; Z01 index
- SAFE_TO_PUBLISH_NOW=YES

---
PUBLISH GATE: this FAQ may ship only together with the HONEST LIMITS block and
the evidence pointers above. Any line whose CURRENTLY_PROVEN is not YES/PRODUCT
LAW must keep its limiting sentence. No counters, no customer names, no partner
logos, no installer claims.
