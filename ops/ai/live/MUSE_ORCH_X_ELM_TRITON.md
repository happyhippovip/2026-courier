# MUSE ORCHESTRATOR RESULT — FAMILY=X (Worker/Verifier Auth Separation)

FAMILY=X (lowest fresh item from lane NEXT_WORKBANK; placeholder <FAMILY> was unfilled)
SUBAGENTS_USED=3 (A SOURCE_TRUTH_EXTRACTOR, B ADVERSARIAL_FALSIFIER,
C EVIDENCE_MINIMALITY_REVIEWER; no nesting; all READ-ONLY, 0 edits/runs/ledger)

## Dedup + Widerspruchs-Entscheide (Parent)
- B-H1 ADOPTED as first execution of lane-planned X1 angle (no prior execution
  exists) — no duplication.
- B-H2: guard itself (verifier_id != worker_id) was known endpoint behavior;
  NEW part kept = no verifier registry (any distinct string passes). Narrowed,
  not repeated.
- B scope note (read beyond brief lines 1-80) declared openly with exact refs —
  ACCEPTED, refs verify against parent reads (modulo line shifts, content identical).
- A "not observable in window" points (register validation, blueprint route map)
  covered complementarily by B — no contradiction.
- C matrix consistent with A+B guards — no contradiction.
- Discarded: none (all claims ref-backed). No MUST items exist, so no
  Step-2-style counter-checks owed.

## SOURCE_TRUTH (A, exact)
- Worker endpoints: Bearer COURIER_API_KEY equality only (app.py:21-30);
  insecure → 503 (:23-24), else 401 (:25-27). Key from env (:12), missing →
  SystemExit (:13-14). Clients: github adapter :115-122, revenue adapter :57-61.
- Verifier endpoints: Bearer COURIER_VERIFIER_API_KEY (app.py:33-44); 401
  (:41-42); insecure OR equal-to-worker-key → 503 for everyone (:36-40).
  Client uses VERIFIER key + VERIFIER_ID=VERIFIER-01 (verifier :12-15, never
  server-validated). Blueprint keeps authorities separate (:74-77).
- Register payload (worker_id/capabilities/cost_class/platform) client-asserted
  (revenue adapter :76/:82-87); no server-side allowlist in auth layer.

## CONFIRMED_DEFECTS (B, exact paths)
- X-H1: shared worker key → arbitrary identity/lane. Path: require_auth checks
  key only (:21-30); register takes worker_id/capabilities/cost_class from body
  (:202-209 + :233-241, only check = non-empty worker_id); claim matches lanes
  against self-asserted capabilities (:281-311); cost deferral reads self-asserted
  cost_class (:240 → :317-346, "free"/"low" never deferred). Dispatch mints :348-369.
- X-H2 (narrowed): verifier independence = "pick a distinct string". Literal
  self-naming rejected (:507-509), but no verifier registry/allowlist exists;
  any non-empty string ≠ worker_id passes; independence gated solely by holding
  the verifier key (:33-44).

## DISPROVEN (B)
- H3: cross-key use (worker key on verifier endpoints and vice versa) → 401 both
  ways (:26-27 vs :41-42); equal/insecure keys → 503 fail-closed (:36-40). Routes
  enumerated (:480/:490 verifier-only; worker routes listed; only /health open :79).
- H4: verify-POST replay → idempotent (result_id equality :511-512, artifacts
  deep-equality :513-514, verdict set :515-517, non-RECEIVED → 409 :504-505,
  RECONCILED resend → ACK_DUPLICATE/409 no-write :499-503; transition :527-531).

## EVIDENCE_GAPS (none new)
C delivered a 9-case negative-test MATRIX as future-proof spec (wrong/missing
keys both authorities, insecure/equal keys, cross-key use ×2, self-verdict;
expect 401/401/401/401/503/503/401/401/400 with endpoint+line refs; harness
pattern tests/test_p3_server_idempotency.py:12-13/:35-38) — unexecuted by design.

## MINIMUM_FIX_PACKET (doc-scope; no minimal code fix exists — architecture-gated)
- X-H1-doc: document trust model (single shared worker key → lane/cost isolation
  is cooperative among key holders, enforced only at key-secrecy boundary) OR
  product-decide per-worker credentials. No code change proposed.
- X-H2-doc: document "verifier independence = distinct-string + separate key,
  no registry" OR product-decide verifier allowlist.
OWNER=CENTRAL_WRITER (both doc packets).

## MINIMUM_PROOF (C matrix, unexecuted)
9 negative cases above; green run = proof. STYLE: existing idempotency-test harness.

BEFORE_CODEX=(none — trust-model properties, no codex-blocking causal defect)
BEFORE_RUN1=(none — runs use fixed test clients)
BEFORE_RUN2=(none)
DEFER=X-H1-doc, X-H2-doc
DO_NOT_REPEAT=muse-orch-x-01 (covers A-extract, B-H1/H2/H3/H4, C-matrix)
NEXT_OWNER=CENTRAL_WRITER
FAMILY_COMPLETE=YES
