# WAVE C CONVERGENCE — MUSE_C2_LAPIS_DUBHE session inventory (read-only)

BASE: HNI-07..19 + D/F/I/K/V + Wave-B RUN2 packet + BLOCKED markers (65-96, 97-144).
0 source edits, 0 runs, 0 ledger writes, 0 gate revalidations all session.

CONFIRMED_FINAL (deduped, owner-tagged):
C1 RUN2 global-count gap (S4) + missing run1→run2 binding (S2) → RUN2-contract
  owner/Central Writer, BEFORE_RUN2. Packet: MUSE_WAVEB_RUN2_CONTRACT_PACKET.md.
C2 Restart hash unbound to SHA (S5) → same owner, BEFORE_RUN2 unless dirs
  SHA-segregated by path (then implicit).
C3 RUN1 hash-glob excludes *.txt (MAC_01 3c, carried peer finding) → RUN1-contract
  owner, BEFORE_RUN1 (owner decision, pre-existing).
C4 Intake Q1/Q2 still present (W) → intake writer lane, candidate-independent,
  NOT codex-gating (gate = Windows durability).
C5 Doc-staleness: SRC-TRUTH "never writes verified_at" (F) + G195 VERIFIED /
  verified_at (peer) → respective authors, one-line updates each.
C6 HNI-14 minimal-set 3/6 → RUN-evidence owner, informational doc note.
DISPROVEN (do not reopen): K plan/tasks divergence; VALIDATED_PENDING_VERIFY,
  SUBMITTED, READY, VERIFIED as courier task states; zero-retry path;
  double-advance on re-verify; replay-out-of-quarantine; B-never-starts-passes
  (r2_b==0 passes count — that is C1, not disproven; listed here to prevent
  misclassification as NO_ISSUE).
MUST_FIX_BEFORE_CODEX: none from this session (all items post-gate or doc-level).
MUST_FIX_BEFORE_RUN1: C3 only (carried peer item).
CAN_DEFER: C2-conditional, C6, RUN2-S3 KeyError robustness, order-text python note.
STOP_DOING: PRE_CODEX revalidation; physical RUNs; ledger; source edits;
  HNI-07..19/MT-01..05/DIRECT/FUTURE re-checks; intake W re-proof; G195/G233 edits
  (peer-owned); new broad families.
OPUS_QUESTION (single): Accept Wave-B RUN2 packet items (1)(2) as BEFORE_RUN2
  requirements and confirm (3)-defer condition (SHA-segregated evidence dirs)?
  If YES → Central Writer implements; if NO → record rationale, close C2.
CODEX-INPUT: nothing codex-gating from this session (no MUST_FIX_BEFORE_CODEX).
MAC-HANDOFF: HNI-19/20 checkpoints + WHATS_LEFT_CURRENT.md; next legal = HNI-20
  (process isolation) then HNI-21/22; wall claims for 07..19 filed under
  MUSE_C2_LAPIS_DUBHE.
FAMILY_COMPLETE=YES (convergence frozen; no new findings invented).
