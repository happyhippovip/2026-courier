# MUSE-HNI-09 checkpoint — CHANGED_STATUS_REJECTION_QA (read-only)

TASK_ID=MUSE-HNI-09 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T12:38Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_09_CHANGED_STATUS_REJECTION_QA.claim.json (atomic).
REUSED: integration_contract.py:114-151 + app.py:352-411 (prior reads, not re-read);
TIMEOUT->400 mapping need (known G06, cited only).

SUBCASES (changed-status rejection; 0 executions, ledger untouched):
S1 Unknown status (TIMEOUT/PARTIAL/CANCELLED/...) -> 400 "invalid result status"
  (contract:147 via app.py:376-381). SOUND fail-closed.
S2 TIMEOUT specifically -> 400: compatible with G06 FAILED-on-timeout adapters;
  explicit TIMEOUT payload still needs FAILED mapping (known, cited only).
S3 SUCCESS + empty artifacts -> 400 (contract:150-151). SOUND.
S4 FAILED + non-empty artifacts: passes shape (:148-149), stored, routed to
  QUEUED/FAILED_TERMINAL — never RESULT_RECEIVED, never verified, never consumed
  downstream. Harmless dead weight; BOUNDARY noted, no finding.
S5 Changed status on resend vs stored result: dup-key includes status (:367) ->
  not duplicate -> 409 when processed (:369-370). Case-9 direction holds. SOUND.
S6 Lowercase "success" -> 400 (exact-membership :147). SOUND fail-closed.
S7 Missing status field -> 400 missing-field (:135-137); None==None shortcut
  impossible (stored always has status post-validation). SOUND.

VERDICT=COMPLETE (candidate-independent; 0 contradictions, 0 false-greens).
NEXT=MUSE-HNI-10 (changed-worker rejection).
