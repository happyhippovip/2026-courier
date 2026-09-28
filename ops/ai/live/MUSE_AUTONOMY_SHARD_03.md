# Shard 03 — Dispatch Identity (READ_ONLY_C2, no runs, no edits)

SHARD=03
STATUS=SHARD_COMPLETE
SUBCASES_DONE=6 (S1 mint uniqueness, S2 dup-key binding, S3 fresh-dispatch-on-retry,
S4 adapter-vs-contract authority, S5 dispatched_at write-only, S6 crash-after-dispatch path)
CONFIRMED_SOURCE_DEFECTS=0
EVIDENCE_GAPS=
- S5: `dispatched_at` stamped at claim (server/app.py:361, neu ggü. Vorrunde) aber
  nirgends konsumiert (0 Leser) — write-only Metadatum; kein Defekt, nur ungenutzte
  Evidence (künftige Staleness-Checks möglich).
- S6: Crash nach Dispatch → reclaim parkt HUMAN_REQUIRED (Quarantäne by design,
  effect-ambiguous); kein Auto-Redispatch → Autonomy-Grenze: unattended Betrieb
  braucht Owner-Entscheid (auto-retry vs. human resume), kein Source-Defekt.
DISPROVEN=
- Doppel-Dispatch single-proc: `serialize_state_mutation` + ein Mint-Ort
  (claim_task) → genau-einmal pro Claim. Cross-proc-Race bleibt bekannte
  RLock-Grenze (DUPLICATE_SKIP, Claim-Race-Klasse).
FIX_PACKETS=0
DUPLICATE_SKIP=S2/S3 (dup-key + fresh-dispatch: bekannte Klassen, intakt),
  S4 (Dispatch-vs-Hash-Autorität: REUSE_EVIDENCE=MUSE_MAC_05_ARTIFACT_HASH.md BACKUP),
  R1 stored-result-Residuum (MMAC-015, bekannt).
NEXT_OWNER=Central Writer nur falls S6-Policy (auto-retry) entschieden wird; sonst keiner.
DO_NOT_REPEAT=SHARD03:S1-S6; MUSE_MAC_05 BACKUP; MMAC-015 R1; Claim-Race single-proc-pin.
PHASE=CODEX_HIGH_RESULT_CURRENT.md absent → weiter Symphony-Shards.
