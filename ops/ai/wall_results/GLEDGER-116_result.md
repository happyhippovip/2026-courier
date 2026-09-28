# GLEDGER-116 Result — Provider Route Fields

TASK_ID=GLEDGER-116
STATUS=PROVEN (by reused durable evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=Wall role rules (WINDOWS/MAC/GOOGLE/MUSE/CODEX/OPUS assignments); WORKER_IDS capability map (GLEDGER-102); auth patterns observed (Bearer headers in tests; no credential material); subscription-first router docs (allowed-inputs list); proof bundle (provider GOOGLE on port 8081; production 8080 untouched)

## Route record (normative)
REQUIRED: `provider` (enum: WINDOWS_ANTIGRAVITY, MAC_MUSE, MAC_GOOGLE, WINDOWS_GOOGLE, CODEX, OPUS — the lane, not the model string), `host` (MAC|WINDOWS), `capability` (github|mac|windows|linux → canonical worker_id), `auth_mode` (REFERENCE only: e.g. `bearer-env`, `subscription-session` — a pointer to where auth lives, never the material), `route_decision` (why this provider: role rule + capacity + generation binding).
OPTIONAL: model/capability descriptors (free text, informational — must never affect identity or equivalence), cost-center reference (opaque id only).
FORBIDDEN (normative redaction boundary, shared with GLEDGER-121): secrets, raw credentials, auth cookies/tokens, raw card/bank data, API keys, keychain references — none of these may appear in Ledger, results, claims, or evidence files. A route record containing credential material is VOID and must be redacted + re-issued (old fingerprint marked CONTRADICTED per GLEDGER-115, never edited in place).

## Route decision rules (normative)
- Role rules bind provider to task class (writer: Windows Antigravity only; physical proof: authorized phase only; review: Codex Phase-2 only; harvest/support: Google/Muse read-only). A route violating role rules is rejected before execution.
- MAX_HEAVY_JOBS=1 per host gates physical/test execution routing; read-only work routes anywhere.
- Model/capability strings are informational: two results differing ONLY in model descriptor but identical in all GLEDGER-107 identity fields are duplicate-equivalent (model is not identity).

MISSING=None.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-117 (cost/quota references route records); GLEDGER-121 (shared redaction boundary).
DO_NOT_REPEAT_FINGERPRINT=gledger-116-provider-route-fields-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-12b53651f04ff23b

DO_NOT_REPEAT_FINGERPRINT=sha256-e5a365e2b1f77db8
