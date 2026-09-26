# Meta Model API Billing Guard — 2026-09-26

Status: ACTIVE / PAY-AS-YOU-GO ENABLED

## Purpose

Keep Meta Model API / Muse Code pay-as-you-go usable for Courier without accidentally reaching the payment threshold before the next funding date.

## Confirmed billing facts

- Meta Model API billing is usage-based.
- A payment method is configured.
- Current balance observed at setup: EUR 0.00.
- Payment threshold observed in the Meta billing UI: EUR 20.00.
- Monthly bill date observed in the Meta billing UI: 2026-10-01.
- The EUR 20 threshold is a charge trigger, not a spend limit.
- The "Spend limits" control shown in the UI is an email usage alert, not a hard stop.
- API keys must never be committed, pasted into repo files, logs, reports, screenshots intended for sharing, or chat handoffs.

## Operational budget guard

- EMAIL_USAGE_ALERT_EUR=14
- INTERNAL_SOFT_STOP_EUR=17
- PAYMENT_THRESHOLD_EUR=20
- Rule: stop new API-heavy work at the internal soft stop and inspect Billing/Usage before continuing.
- Rule: do not rely on the EUR 20 payment threshold as a safety cap.
- Rule: prefer the lowest-cost model that is sufficient for the assigned Courier task.
- Rule: use API-backed Muse only for work that materially advances the current critical path; free Google CLI capacity remains preferred for broad read-only scouting.

## Authentication

Muse Code API-key authentication can use META_API_KEY or a stored key. Environment keys take precedence over browser sign-in.

Never store the actual key in this repository.

## Courier coordination

This note does not change canonical source-writer authority.

- Windows Antigravity remains the only source writer for the final candidate.
- Google CLI and Muse API lanes remain read-only unless explicitly reassigned.
- This billing note is coordination-only and does not authorize a physical Canary or source mutation.
