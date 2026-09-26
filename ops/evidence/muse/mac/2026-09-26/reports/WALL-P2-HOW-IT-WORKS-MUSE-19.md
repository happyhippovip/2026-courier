# WALL-P2 HOW_IT_WORKS (PREP ONLY, no publish)

WORKER=MUSE-19 · HOST=MAC · MODE=READ_ONLY · 2026-09-26
SOURCES: docs/WEBSITE_BLUEPRINT_2026.md (§2 product proof, §4 architecture),
WALL-P2-GRANDMA-NOSPAM-MUSE-SUP.md (L1/L2 copy + intent labels),
RV14_SHORT_ANSWER.md (shortest-true-answer-first), Z13 Proof Card (card rules).
REPO UNTOUCHED. No capabilities invented. No Product Shell.

## Placement
Core of `/product`. One screen, three layers: (1) one-sentence version,
(2) the 9-step chain in plain words, (3) architecture path + status words.
Technical detail (IDs, hashes, retry policy) on demand only, never first.

## LAYER 1 — one sentence (website-ready, no qualifier needed)
"Courier picks up your work where you left off: it executes each step,
has the result checked independently, and continues with the next one."
CLAIM=plain description of intended behavior · CURRENTLY_PROVEN=N/A (copy) ·
EVIDENCE_SOURCE=RV14 rule + blueprint §2 · SAFE_TO_PUBLISH_NOW=YES.

## LAYER 2 — the 9 steps (blueprint §2 chain, customer words)
1. TASK — you give one task. 2. ADMISSION — it is accepted into the queue.
3. EXECUTE — the step runs, once, with its run recorded. 4. RESULT — the
outcome and its artifacts are posted. 5. PERSIST — the result is stored so a
restart cannot lose it. 6. VERIFY — an independent check (never the worker
itself) passes or fails it. 7. RECONCILE — a passed step advances the plan.
8. DONE — the goal closes only when every step is checked. 9. NEXT — the
following step starts on its own; you press nothing.
Status words shown beside the chain: RUNNING / WAITING / BLOCKED / UNKNOWN /
DONE (UNKNOWN pauses fail-closed rather than guessing).
CLAIM=chain behavior · CURRENTLY_PROVEN=PARTIAL (hermetic; witnessed run
pending) · EVIDENCE_SOURCE=repo control-plane paths (read-only) + RV08/Z13
rules · SAFE_TO_PUBLISH_NOW=YES only headed "how it is designed to work".

## LAYER 3 — where it runs (blueprint §4, no partnership fiction)
"Your machine → Courier Control Plane → cloud workers → model/tool providers
→ execution ledger → storage/recovery → observability. Cloud-portable; no
exclusive provider partnership is claimed."
CLAIM=architecture · CURRENTLY_PROVEN=NO (target topology) ·
EVIDENCE_SOURCE=blueprint §4 · SAFE_TO_PUBLISH_NOW=YES only labeled diagram
of intent, with "first pilots run supervised on one designated machine"
(RV01 framing) directly underneath.

## Mandatory qualifier block (prints under Layer 2, not a footnote)
"Currently demonstrated in supervised test runs; first customer pilots are
being prepared. Live numbers appear in TRUST/EVIDENCE only after a witnessed
run — until then that panel reads NOT YET MEASURED."
Without this block, Layers 1–2 are NOT cleared for publish.

## Out of scope for this task (left for later claims)
PRICING_EXPERIMENT_COPY, INSTALL_PREREQUISITES, DOWNLOAD page (claimed by
MAC-02 — untouched), FAST_TRACK_48H_EXPLANATION (source docs missing —
see TRUST-EVIDENCE unknowns).
