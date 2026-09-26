# WALL-P2-SUPPORT-FLOW — draft MD (MUSE-MAC-21)

TASK_ID=WALL-P2-SUPPORT-FLOW
STATUS=DONE
WORKER=MUSE-MAC-21 · HOST=MAC · MODE=READ_ONLY · 2026-09-26T14:58Z
CONSTRAINTS=no fake customers, no unproven SLA claims. Commercial-safe only.

## Support flow (pilot phase: humans answer, system provides the evidence)
1. Customer reports an issue in plain words (no log-hunting required from them).
2. Operator pulls: the task's proof card (RV08), the incident card if one was
   filed (RV13), and LAST_VERIFIED_STATE from durable state. Response always
   attaches these three — the customer never has to prove what happened.
3. Triage by RV07 class (provider/quota, verification, ambiguous STARTED,
   duplicate, restart, permission gate, human-required). Each class already
   defines what the customer sees and how resume works — support quotes the
   policy, never improvises.
4. Resolution or scheduled fix recorded on the incident card; card stays with
   the task history. No silent fixes.

## Contact surface (minimal, honest)
- One channel, stated response window in BUSINESS terms ("next working day"),
  never a 24/7 or uptime claim (unproven — Z10 class 4).
- Status page = the customer's own proof cards, not a marketing dashboard.

## Pilot pricing copy (commercial-safe wording)
- "Pilot: one scoped project, one witnessed acceptance test before anything
  is paid. You pay for the scoped run, not for our learning."
- "If the acceptance test prints FAIL in front of you, there is no invoice.
  The failure report is yours to keep."
- No per-seat, no tiers, no SLA numbers, no "autonomy guarantee" — none of
  these are proven (GAP-3/4/5). Pricing stays time-and-scope until the
  supervised loop runs unattended for hours (GAP-3 exit criterion).
- Money is a REAL_GATE (RV17): every charge needs explicit approval, and
  approval is per-scope, revocable, with audit evidence.

## Explicitly excluded until proven
Uptime %, response-time SLA, "fully autonomous" wording, self-serve signup,
any claim containing "guarantee".

BLOCKER=NONE
NEXT=next pending P2/P3 by wall priority
