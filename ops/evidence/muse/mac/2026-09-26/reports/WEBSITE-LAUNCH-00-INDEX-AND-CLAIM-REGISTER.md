# Courier Website Launch Package — Index and Claim Register

Date: 2026-09-26 | Owner: MAC (Muse, website prep lane) | Status: PREP_ONLY, proof-gated
Sources read: `docs/WEBSITE_BLUEPRINT_2026.md`, `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md`
Requested but NOT FOUND in repo: `docs/WEBSITE_GRANDMA_TEST*`, `docs/COURIER_PERMISSION_AND_COMMUNICATION_RULES_2026-09-26.md`, `docs/COURIER_FAST_TRACK_48H_MODE_2026-09-26.md`
→ sections derived from those titles are marked accordingly; nothing from them is stated as product fact.

## Gate truth (evidence date 2026-09-26)

No Gate 1–4 PASS evidence found in repo (only design mentions of PASS, no acceptance records).
Canonical plan state (2026-09-20): Gate 1 IN_PROGRESS, Gate 2 IN_PROGRESS (bounded), Gate 3 NOT_PROVEN/PREP_ONLY, Gate 4 NOT_PROVEN/PREP_ONLY, Gate 5 NOT_STARTED, Gate 6 LOCKED, Gate 7 LOCKED.
Consequence: **every capability claim below is CURRENTLY_PROVEN=NO unless stated otherwise.**
The site therefore launches in "building in the open + pilot waitlist" posture, never in "shipping product" posture.

## Package files (this directory)

- `WEBSITE-LAUNCH-00-INDEX-AND-CLAIM-REGISTER.md` (this file)
- `WEBSITE-LAUNCH-01-LANDING-PAGE-STRUCTURE.md` — sitemap, section order, per-section publish gate
- `WEBSITE-LAUNCH-02-HERO-AND-HOW-IT-WORKS.md` — HERO_COPY + HOW_IT_WORKS
- `WEBSITE-LAUNCH-03-PILOT-PAGE.md` — PILOT_PAGE, form fields, onboarding, prerequisites, pricing experiment
- `WEBSITE-LAUNCH-04-FAQ-PRIVACY-DATAFLOW.md` — FAQ, PRIVACY_SUMMARY, DATA_FLOW_EXPLANATION
- `WEBSITE-LAUNCH-05-TRUST-SUPPORT-GRANDMA.md` — TRUST/EVIDENCE_SECTION, SUPPORT_FLOW, GRANDMA_EXPLANATION, NO_PERMISSION_SPAM_EXPLANATION, FAST_TRACK_48H_EXPLANATION
- `WEBSITE-LAUNCH-06-DEMO-STORYBOARD.md` — DEMO_STORYBOARD
- `WEBSITE-LAUNCH-07-DOWNLOAD-AND-WAITLIST.md` — DOWNLOAD_PAGE_STRUCTURE (gated), INSTALL_PREREQUISITES, WAITLIST/PILOT_FORM_FIELDS, MANUAL_ONBOARDING_FLOW

## Master claim register

Rule: a claim is SAFE_TO_PUBLISH_NOW=YES only if CURRENTLY_PROVEN=YES, or if it is phrased strictly as intent/roadmap/waitlist (column "Safe phrasing").

| # | CLAIM | CURRENTLY_PROVEN | EVIDENCE_SOURCE | SAFE_TO_PUBLISH_NOW | Safe phrasing (if NO) |
|---|---|---|---|---|---|
| C1 | Courier continues your work where you stopped, next day | NO | Plan §External promise = goal, Gate 3 NOT_PROVEN | NO as capability; YES as mission | "We're building Courier so that…" / "Our goal:" |
| C2 | No copying prompts / moving results between agents | NO | Plan §1 (autonomy target), Gate 2/3 not PASS | NO as capability; YES as mission | "Designed to eliminate…" |
| C3 | Every step is auditable (proof cards, evidence) | PARTIAL (design+tests exist, no gate PASS) | Plan §10–11; repo `tests/` | NO as guarantee; YES as engineering approach | "Every run produces a proof card we can show you" → only after Gate 1 PASS |
| C4 | Courier stops only at real boundaries (decision, money, permission, safety) | NO (behavioral target) | Plan §1, §5 | YES as design principle | "Courier is designed to ask only when…" |
| C5 | One confirmation of the goal, then it works autonomously | NO | Plan §5 (Goal Contract) | YES as design principle | "How it will work:" (future tense) |
| C6 | Reliable unattended operation / runs while nobody watches | NO | Blueprint hero = direction, Gates 2–4 not PASS | NO | HOLD until A4; use "Direction:" label |
| C7 | Recovery after restart, nothing lost silently | NO | Plan §9, Gate 4 NOT_PROVEN | NO | HOLD until RSR=100% |
| C8 | Fixed pilot price / pricing | NO | Plan §18: price is an experiment (49–99 € orientation) | YES only as labeled experiment | "Pilot pricing is an experiment: …" |
| C9 | Any metric (tasks done, uptime, cost/task) | NO | Blueprint §5: real metrics only, none published yet | NO | Metrics section ships EMPTY with "first numbers after proof" note |
| C10 | AWS / Meta partnership or endorsement | NO | Blueprint §§AWS/Meta alignment: do not claim | NO | "Built on AWS" only when technically true; no logos |
| C11 | Download / installer available | NO | Plan Gate 7 LOCKED | NO | Download page stays DRAFT-gated, unpublished |
| C12 | A "48-hour fast track" offering exists | NO | No source doc found in repo | NO | File 05 contains HOLD template only |
| C13 | Company facts (team, offices, customers, investors) | NO | Blueprint §10: do not invent | NO | Company page: mission + philosophy + contact only |

## Publish gate (proof → publish)

1. Gate 3 PASS (physical A→B, HUMAN_RELAY_COUNT=0) → may publish C1/C2 in present tense + DEMO video.
2. Gate 4 PASS (RSR=100%) → may publish C6/C7.
3. Gate 1 PASS + FROZEN → may publish C3 (proof-card example with real IDs).
4. First paid pilot completed → may publish C8 as reference (anonymized), pilot story.
5. Until then: site = mission + approach + evidence-in-progress + waitlist. No fake PASS, no counters, no customer logos.
