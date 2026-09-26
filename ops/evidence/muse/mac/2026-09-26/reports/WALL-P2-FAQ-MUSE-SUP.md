# WALL-P2-FAQ — evidence-gated website FAQ (PREP ONLY, no publish)

WORKER=muse-mac-support · HOST=MAC · MODE=READ_ONLY · 2026-09-26
SOURCES: WEBSITE_BLUEPRINT_2026.md, CANONICAL_PRODUCT_PLAN (gates 2026-09-20),
WALL-P2-LANDING-STRUCTURE-MAC02, RV04/RV14 pool reports.
STATUS RULE: every answer carries CLAIM / CURRENTLY_PROVEN / EVIDENCE / SAFE_TO_PUBLISH.

## Q1 — What does Courier actually do?
A: You define a goal as a task. Courier executes it, checks the result
independently, and continues with the next step — without a human relaying
messages between steps.
CLAIM=A→VERIFY→B with HUMAN_RELAY=0 · CURRENTLY_PROVEN=PARTIAL (fixture/canary
scope: GM5 A→VERIFY→B; HEAD branch-only per CLI-01) · EVIDENCE=GM5 canary,
RES-MUSE02 carrier bank · SAFE_TO_PUBLISH_NOW=YES only with scope qualifier
"in isolated test runs" (see HONEST LIMITS).

## Q2 — What happens if something fails or the machine restarts?
A: Courier is designed to resume where it stopped instead of repeating finished
work — but restart recovery on the shippable tree is not yet proven.
CLAIM=restart/no-replay · CURRENTLY_PROVEN=NO (Gate 4 NOT_PROVEN; proof on side
branches only) · EVIDENCE=CLI4 spec, RV19 GAP-1 · SAFE_TO_PUBLISH_NOW=NO —
publish only as roadmap ("designed to resume; recovery testing in progress").

## Q3 — Will it ask me for permission all the time?
A: No. You authorize one project scope once; inside it Courier works
autonomously. It stops and asks only for real gates: money, passwords/2FA,
publishing, destructive or irreversible actions, anything outside your scope.
CLAIM=scoped autonomy · CURRENTLY_PROVEN=NO (product rule defined in RV02/RV17;
not enforced in code yet) · EVIDENCE=RV02 permission contract (design) ·
SAFE_TO_PUBLISH_NOW=YES as intent ("how it will work"), NO as capability.

## Q4 — Can I try it / buy it today?
A: Not yet. There is no download, no installer, no paid pilot running.
Interested teams can join the pilot list; a first small supervised pilot is the
goal (Gate 5 NOT_STARTED).
CLAIM=availability · CURRENTLY_PROVEN=N/A · SAFE_TO_PUBLISH_NOW=YES (honest
"not yet" + waitlist CTA converts better than hype).

## Q5 — What do you do with my data?
A: Pointer — full text in WALL-P2-PRIVACY-DATAFLOW-MAC-21. Short version:
your project files stay in your workspace; execution logs exist so every step
is auditable; nothing is published externally without an explicit gate.
CLAIM=data handling · CURRENTLY_PROVEN=PARTIAL (workspace/state layout real;
customer deployment nonexistent) · SAFE_TO_PUBLISH_NOW=YES with "design" label.

## Q6 — How is this different from a chatbot agent?
A: Chatbots answer; Courier is built to *continue*: persisted state, independent
verification of each result, bounded retries, resume instead of replay.
CLAIM=continue-vs-answer · CURRENTLY_PROVEN=PARTIAL (mechanisms exist in
tree/branches; end-to-end unproven) · SAFE_TO_PUBLISH_NOW=YES as architecture
description, NO as proven outcome.

## MANDATORY HONEST-LIMITS BLOCK (never omitted from page)
- Zero-human A→B: proven in isolated test runs only (Gate 3 NOT_PROVEN).
- Restart recovery: in testing, not proven on the shippable tree (Gate 4 NOT_PROVEN).
- No installer, no download, no paid use today (Gate 5 NOT_STARTED, Gate 7 LOCKED).
