# SHARD 14 — Provider Abstraction (Fallback vs Idempotency/UNKNOWN)

SHARD=14
STATUS=COMPLETE (5 Subcases, 0 Executions, 0 Edits, Ledger frozen)
SOURCE=scripts/mac_worker/daemon.py + scripts/integration_contract.py

SUBCASES_DONE=5:
1. Identitätsbindung provider-unabhängig: Payload trägt immer
   task-dispatch_id/attempt_id (daemon.py:539-546); Server-Tupel prüft
   goal/task/attempt/dispatch/worker (contract:138-140); "provider"-Label
   ist informativ, nicht bindend. Mode-Wechsel bricht Idempotency NICHT.
2. Kein stiller Cross-Provider-Fallback: Mode einmal pro Task gewählt
   (Z. 519-534); Fehlerpfade liefern FAILED + execution_mode (Z. 298,
   321, 327); Retry nur als frischer Server-Attempt. Fail-closed.
3. UNKNOWN fail-closed in 3 Schichten: SUCCESS ohne Evidence→FAILED
   (collect_artifact_evidence, Z. 231-248); fehlender Status→FAILED
   (Z. 549); Server akzeptiert nur SUCCESS/FAILED (RESULT_STATES),
   UNKNOWN→400. Kein UNKNOWN-Durchmarsch möglich.
4. MuseAdmissionBlocked: Requeue CLAIMED + Poll-Sleep + continue
   (Z. 530-534) — kein Busy-Spin, kein Fallback mit Doppel-Execution.
5. Unerwartete Exception (nicht-Admission): propagiert in outer-except,
   nur geloggt; kein erfundenes Result; Task bleibt DISPATCHED bis
   reclaim-Quarantäne (300 s). Fail-closed; Liveness via reclaim —
   Design, kein Defect.

CONFIRMED_SOURCE_DEFECTS=0. EVIDENCE_GAPS=0.
DISPROVEN="Provider-Fallback verletzt Idempotency/UNKNOWN" (Konstruktion
  schließt es aus: Bindung serverseitig, Status dreifach fail-closed).
FIX_PACKETS=0. NEXT_OWNER=—.
DO_NOT_REPEAT_FINGERPRINT=muse-shard14-provider-idem-e11749b6
