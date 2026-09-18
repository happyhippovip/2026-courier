# Codex Weekly Controller

Codex is a scarce independent-verification resource.

Optimize:

VERIFIED_OUTPUT / CODEX_PERCENT

not raw utilization.

## Rolling allowance

```
days_left = remaining days in current 7-day budget window
reserve_percent = 8

base_daily = max(remaining_percent - reserve_percent, 0) / max(days_left, 1)

today_min = base_daily * 0.4
today_max = base_daily * 1.6

rollover = min(yesterday_unused, base_daily * 0.5)

today_budget = clamp(base_daily + rollover, today_min, today_max)
```

If no genuinely qualifying prepared Codex task exists, do **not** invent work to meet the minimum.

## Zones

- GREEN: normal CODEX_SCORE threshold.
- YELLOW: raise threshold; independent/P0 work only.
- RED: verification of already-implemented critical fixes and hard blockers only.
- RESERVE: final integration/sign-off/emergency only.

Recompute from actual remaining allowance and time to reset; do not assume a fixed reset schedule.

## Required Codex review packet

```
CURRENT_HEAD=
COMMITS_UNDER_REVIEW=
INVARIANTS=
DIFF_SCOPE=
REPRODUCERS=
T2_RESULTS=
T3_RESULTS=
KNOWN_ATTACKS=
FILES_TO_READ=
QUESTIONS_TO_ANSWER=
```

Missing required information:
`PACKET_INCOMPLETE`
→ MUSE/NEWSY repair packet
→ do not continue broad Codex exploration.

## Batch rule

Batch related fixes only when:
- same invariant family,
- combined logical change remains reviewable,
- no single high-risk item would lose scrutiny.

Codex should return root cause/verdict; mechanical fixes normally go back to Google.
