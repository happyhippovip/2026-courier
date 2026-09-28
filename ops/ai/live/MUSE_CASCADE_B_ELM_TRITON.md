# MUSE CASCADE WAVE B — Owner-Defect-Packets (aus Wave-A MUSE_WHATS_LEFT_CURRENT.md)

OWNER=MUSE elm-triton / HOST=MAC / 2026-09-28
WAVE-A-SOURCE=ops/ai/live/MUSE_WHATS_LEFT_CURRENT.md (eigene Runde: A,C,D,E,I,L,W;
keine neue Fehlersuche, keine Re-Prüfung widerlegter/bekannter Findings,
0 source edits, 0 runs, 0 PRE_CODEX-Revalidierung).
NO_ISSUE-Punkte A,E,I,L,W brauchen kein Packet (geschlossen, Refs im
Wave-A-Checkpoint). Packets nur für D (CONFIRMED_SOURCE_DEFECT) + C
(EVIDENCE_DOC_DEFECT).

## Packet B-D: Revenue-Adapter/Intake/Verifier Triple-Break

STATUS=READY_FOR_OWNER
OWNER=UNASSIGNED_ADAPTER_LANE (Fallback: CENTRAL_WRITER; candidate-independent,
kein Gate-Owner nötig)
CAUSAL_DEFECT=Drei unabhängige Brüche, jeder allein tötet den Revenue-Pfad:
D1 Adapter postet result_data/artifact_* ohne durable Felder
(scripts/revenue_worker_adapter.py:128-141) → Intake-400
(scripts/integration_contract.py:135-137; server/app.py:386-391).
D2 Intake streicht result_data (contract :171, stored app.py:393), Verifier
liest result.result_data (scripts/courier_verifier.py:121) → immer {}.
D3 Verifier-Branch hängt an task.capabilities (verifier :112), Server setzt
task["capabilities"] nie (nur Worker-Records app.py:226 + Claim-Matching
:297-301; prepare_task setzt keine).
MIN_FIX_SCOPE=Kleinste Owner-Entscheidung zuerst: reconcile ODER retire.
Reconcile = Adapter-Payload auf durable Contract formen + result_data in
required/passthrough + task-capabilities bei Claim setzen. Retire =
revenue_worker_adapter.py + Verifier-Revenue-Branch (:112-129) als Dead Code
entfernen. Kein Core-Pipeline-Touch in beiden Varianten.
MIN_RETEST=Ein Test im Stil tests/test_p3_server_idempotency.py:
geformtes Revenue-Payload an /tasks/result → 200 ACK_RESULT_RECEIVED +
gespeichertes result enthält result_data + Verifier-PASS auf
capabilities-tragendem Task. Bei retire: Nachweis, dass kein Referenzierer
mehr existiert (grep) + Suite grün.
BEFORE_CODEX=NO (Revenue-Lane, nicht Core-Pipeline; gate-unabhängig)
BEFORE_RUN1=NO (RUN_1 deckt Core-Flow; Revenue weder Input noch Proof-Anteil)
CAN_DEFER=YES (post-freeze; bis dahin Revenue-Tasks nicht dispatchen)
DO_NOT_REPEAT=muse-cascade-b-d-01

## Packet B-C: Unknown-Worker/Task Status-Split 404 vs 400

STATUS=READY_FOR_OWNER
OWNER=CENTRAL_WRITER (server/app.py, Trivialgröße)
CAUSAL_DEFECT=Unbekannter Worker: 404 an claim (server/app.py:278) und
heartbeat (:267), aber 400 "Invalid task or worker" an task_result (:424).
Beidseitig fail-closed, kein Verhaltensschaden — nur undokumentierter Split.
MIN_FIX_SCOPE=Eine Zeile: task_result auf 404 für unbekannte task/worker
normalisieren (oder Split in Contract-Doc festschreiben — dann 0 Code).
MIN_RETEST=Bestehende Endpoint-Tests + je 1 Assert unknown-worker → 404 an
allen drei Endpunkten.
BEFORE_CODEX=NO
BEFORE_RUN1=NO
CAN_DEFER=YES (kosmetisch; fail-closed heute)
DO_NOT_REPEAT=muse-cascade-b-c-01

FAMILY_COMPLETE (B-Task: 2/2 Wave-A-Findings paketiert; Rest der Wave-A-Runde
war NO_ISSUE und braucht kein Packet).
NEXT_OWNER=B-D: UNASSIGNED_ADAPTER_LANE (Fallback CENTRAL_WRITER); B-C: CENTRAL_WRITER.
