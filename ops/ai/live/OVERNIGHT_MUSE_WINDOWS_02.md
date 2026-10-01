# OVERNIGHT MUSE WINDOWS 02 — Checkpoint (READ_ONLY, kein Ledger)

Claim: first-free (01 belegt, 02 frei verifiziert). Eigene Datei, nie fremde schreiben.

## CURRENT CONTEXT (gelesen)
- CURRENT_HEAD=fix-cb1-new e57517833c57eb3dd336c92e629e4a2db53da498 (Ref unveraendert)
- GATE_STATE=VALIDATED_LOCAL_GREEN, 57/1/0, NEXT=AWAIT_MAC_CANARY (GATE_STATE_CURRENT.md)
- CHIEF_STATUS_CURRENT.md=ABSENT, CODEX_HIGH_RESULT_CURRENT.md=ABSENT,
  FINISH24_SLOT_MAP=ABSENT, ENDGAME_WAVE6=ABSENT (alle 4 Reads: Datei fehlt)
- SONNET_VERDICT=ABSENT → kein Sonnet-Review wiederholen, nur kandidat-unabhaengig
- RUN1_REAL_EVIDENCE_PRESENT=NO (`logs/server_run1.log` fehlt; M7/M8-Urteile stehen)
- RUN2_REAL_EVIDENCE_PRESENT=NO
- DRIFT (live beobachtet): app.py None-Guard + Nettoverkuerzung; daemon.py result_id-Hash +
  Timing-Rework; State +2 Test-Goals; NEU in S1: `dispatched_at` (app.py:334)

## S1 SOURCE_TRUTH — REAL_PRODUCER (diese Invocation, 3 Reads)
REAL_PRODUCER = Produktions-Pfad, der Result-Payloads erzeugt (kein Harness, kein Mock):
1. Server mintet Identitaet bei Claim: attempt/dispatch (`app.py:322-325`), `dispatched_at`
   (`:334`, NEU/ungesichtet), Single-Head-Gating + Capability-Match + stummes Cost-Deferral
   (`:271-320`, Mechanik intakt, -5 Zeilen).
2. Worker fuehrt NATIV aus (PowerShell -EncodedCommand), hasht lokale Artifact-Bytes selbst
   (`daemon.py:196-197`), berechnet DETERMINISTISCH `result_id=sha256(kanonische Identitaet)`
   (`:202-213`, NEU/ungesichtet — war uuid4), setzt provider + execution_start/end.
   Missing/empty artifacts → FAILED (`:190-200`).
3. Server validiert Form/Identitaet (`validate_durable_result`), rechnet result_id NICHT nach
   (worker-assertiert, server-akzeptiert — Provenienz-Notiz fuer FALLBACK); dann
   RESULT_RECEIVED → unabhaengiger Verifier → RECONCILED.
NICHT-Produzenten (abgegrenzt): Test-Harness (gemocktes Popen), `integration_contract` als
"Worker" (RUN-Skript-Fiktion, M7), synthetische Fixtures.
S1-DRIFT-ADD (→ M9-7-Freeze-Item, keine neue Familie): `dispatched_at`, result_id-Hash-Schema,
execution-Timing — alle ungesichtet, alle vor Evidenz zu sichten/pinnen.

## OUTPUT
WINDOW_ID=02
PRIMARY=REAL_PRODUCER
PRIMARY_STAGE_DONE=S1
PRIMARY_COMPLETE=NO
FALLBACK=RESULT_IDENTITY_PROVENANCE
FALLBACK_STAGE_DONE=
FALLBACK_COMPLETE=NO
CURRENT_CONTEXT_FINGERPRINT=HEAD_e5751783|GATE_GREEN_57-1-0_AWAIT_MAC|SONNET_ABSENT|RUN1_NO|RUN2_NO|DRIFT_app+daemon+state+dispatched_at|CTXDOCS_1of5
CONFIRMED=S1: Produzenten-Kette (Server-mintet + Worker-produziert-nativ + Server-validiert-nicht-nach); Claim-Mechanik intakt; RUN1-Log abwesend
DISPROVEN="Harness/Mock produziert Real-Results"; "result_id ist server-gemintet" (ist worker-berechnet)
UNIQUE_GAP=S1-DRIFT-ADD: 3 ungesichtete Produzenten-Deltas (dispatched_at, result_id-Hash, execution-Timing) ohne Review/Pin
MIN_TEST=(S4, nicht diese Stage)
MIN_EVIDENCE=SHA-Pin + Freeze vor Produzenten-Evidenz (M9-7)
OWNER_PACKET=SOLE_WINDOWS_WRITER (bei Bedarf): dispatched_at/result_id-Schema/Timing sichten + dokumentieren; kein Fix verlangt
WAITING_FOR=
NEXT_STAGE=S2
STOP_REASON=ONE_STAGE_PER_INVOCATION_DONE
