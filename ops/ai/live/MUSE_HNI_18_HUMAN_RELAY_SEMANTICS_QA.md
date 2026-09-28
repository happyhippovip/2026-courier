# MUSE-HNI-18 checkpoint — HUMAN_RELAY_SEMANTICS_QA (read-only)

TASK_ID=MUSE-HNI-18 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T13:50Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_18_HUMAN_RELAY_SEMANTICS_QA.claim.json (atomic).
REUSED: ZERO_RELAY + B_CONTINUATION denylist (MAC_01/HNI-15 cites); resume
app.py:534-550 (prior read).

SUBCASES (human-relay semantics; 0 executions, ledger untouched):
S1 RUN1 relay metric = 2-substring denylist on self-authored log: syntactic, not
  causal; bypassable (MAC_01 cite). BOUNDARY, no new claim.
S2 force_success -> 400 "not supported; retry and verify instead" (:546-549).
  No manual SUCCESS injection; durable path only. SOUND (real server enforcement).
S3 HUMAN_REQUIRED = decision quarantine, not data path; stale-effect ambiguity
  held for owner. SOUND semantics.
S4 B_CONTINUATION 'HUMAN'-substring: same denylist class (HNI-15 S3 reuse).
S5 Relay-counter -1 default fails closed (MAC_01 cite).
S6 instruction_override on resume (:541-542): human influence exists as EXPLICIT
  logged override, not silent relay. SOUND design; only legitimate human data path.

VERDICT=COMPLETE (candidate-independent; 0 contradictions, 0 false-greens).
NEXT=MUSE-HNI-19 (runtime binding).
