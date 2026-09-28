# MAC09 Artifact-Proof-Chain — Checkpoint (PREP ONLY, NO EXECUTION)

- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- DATE=2026-09-28
- MODE=one-point-per-round
- GATE: PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (ops/ai/GATE_STATE_CURRENT.md)
- READY_FOR_PHYSICAL_RUN=NO → keine Ausführung (kein Server-Boot, kein Verifier-Run, kein Cleanup-Exec)
- LEDGER_WORK=SKIP
- SOURCES: ops/ai/RUN1_RUN2_EVIDENCE_CAPTURE_DESIGN_2026-09-28.md (Datums 1–12), scripts/integration_contract.py:verify_result (~HEAD:60–110), scripts/courier_verifier.py:fetch_artifact/verify_artifacts, server/state/central_state.json (keys: goals/tasks/workers), server/state/artifacts/{blobs,records}

## Status (pro Runde 1 Punkt)
- [x] 1 chain-skeleton + gate-binding verifiziert (read-only)
- [ ] 2 task-owned expected hash gebunden
- [ ] 3 result-artifact kanonisch gebunden
- [ ] 4 server-bytes unabhängig nachgewiesen
- [ ] 5 verifier-evidence belegt
- [ ] 6 reconcile-evidence belegt
- [ ] 7 B-evidence + counts + timestamps belegt

## 1 DONE (Runde 1): Skelett + Gate-Bindung
- Verifiziert read-only: GATE_STATE (FINAL_SHA 34b0a426… NOT_FOUND, NEXT=ONE_GATE_PERSISTENCE_OWNER_ONLY, kein Zweit-Validator), WALL_QUEUE (MAC-HNI 1–22 + FINISH24 1–24 COMPLETED, LEDGER SKIP), live-dir enthält nur fremdes MAC07 (nicht angerührt), isolated_run1 absent, heavy-lock absent, production-state/logs fremd-dirty (nicht angerührt).
- Invariante: kein PRE_CODEX-Re-Validation, kein Ledger-Touch, keine Source-Edits.

## 2 Task-owned expected hash (OPEN)
- FIELD: run1.step_a.task_expected_sha256
- SOURCE: Goal-Contract/Task-Definition (central_state.json task.expected_artifacts / expected_sha256), NICHT Worker-Payload
- CAPTURE (bei READY, read-only): task.get("expected_artifacts",{}).get(path) lesen; 64-char lowercase-hex prüfen
- BINDING: unveränderliche Vorgabe; Worker kann nicht forgen/overriden (Design Datum 3)
- COMMAND-PUNKT: `python3 -c "import json; t=json.load(open('server/state/isolated_run1/central_state.json'))['tasks']['<a>']; print(t.get('expected_artifacts'))"`

## 3 Result artifact (OPEN)
- FIELD: run1.step_a.result_payload (result_id, status SUCCESS, artifacts[])
- SOURCE: POST /tasks/result Body in central_state.json
- CAPTURE: task["result"] extrahieren; result_id nicht-leer, kein error-Feld
- SOURCE-TRUTH (app.py task_result): nur SUCCESS landet RESULT_RECEIVED; FAILED → QUEUED (attempts<3) / FAILED_TERMINAL; RESULT_STATES={SUCCESS,FAILED} (integration_contract.py:25), "COMPLETED" ist kein Result-Status
- BINDING: _canonical_hash(result_identity) → result-{hash} (integration_contract.verify_result); Pfad-Guard: relativ, kein absolut, kein `..` (ebd.)
- COMMAND-PUNKT: run1_proof.json#step_a.result aus isoliertem State lesen (erst nach RUN_1)

## 4 Server bytes (OPEN)
- FIELD: run1.step_a.server_artifact_sha256
- SOURCE: GET /artifacts/{id} Server-Kopie, Verifier lädt Bytes + hashlib.sha256
- CAPTURE: fetch_artifact() → sha256(bytes) == task_expected_sha256 (exakt)
- FAIL: Mismatch oder 404/500 → FAIL (Design Datum 4)
- COMMAND-PUNKT: `curl -s http://127.0.0.1:8081/artifacts/<id> | sha256sum` (nur bei READY auf 8081)

## 5 Verifier evidence (OPEN)
- FIELD: run1.step_a.verification_verdict
- SOURCE: POST /tasks/verify via scripts/courier_verifier.py (verifier_id VERIFIER-CANARY-01), verify_artifacts() re-hashed Server-Kopie; nie Worker-Lokalpfad öffnen
- CAPTURE: verdict=="PASS" im Coordinator-State; upload-Pflicht für mac/windows-Artefakte
- PERSIST: run1_proof.json#step_a.verdict (Design Datum 5)

## 6 Reconcile evidence (OPEN)
- FIELD: run1.step_a.status
- SOURCE: central_state.json
- CAPTURE: status=="RECONCILED" (terminal, nur via /tasks/verify verdict PASS aus RESULT_RECEIVED); RESULT_RECEIVED/DISPATCHED/QUEUED/FAILED_VERIFICATION = nicht-terminal (Design Datum 6)
- COMMAND-PUNKT: `GET /goals/<goal_id>` auf Staging-8081 (nur bei READY)

## 7 B evidence + counts + timestamps (OPEN)
- B-legal-nach-A: step_b.dispatched_at >= step_a.reconciled_at (delta_ms>=0, Design Datum 7) — CAVEAT (konvergiert, HEAD ee2bb49b): dispatched_at EXISTIERT auf Plan-Steps (app.py:353, Epoch-Float); reconciled_at/started_at fehlen weiter → Ordering-Vergleich braucht Harness-Events (events.jsonl, self-attested), Epoch-vs-ISO-Normierung dabei festlegen
- B-dispatch: status DISPATCHED + dispatch-* UUID, attempts==1 (Datum 8)
- B-start/completion: started_at ISO8601 nach Dispatch; step_b RECONCILED + goal DONE (Datums 9–10)
- COUNTS: step_a.execution_count==1 (Datum 1); HUMAN_RELAY_COUNT==0 (Datum 11); FAILED_EXECUTION_COUNT==0 (Datum 12)
- COMMAND-PUNKTE (alle gated): Order-Assertion, dispatch_id-, started_at-, goal-completion-Lesungen aus isoliertem State/Logs

## Stale-file detection (read-only, nichts gelöscht)
- STALE-RISIKEN: production central_state.json (00:13, fremd) vs isolated_run1 absent; artifacts/blobs+records production (27.09., fremd); logs/courier_motor.err + server.err fremd-dirty; /tmp-Heavy-Lock absent=OK
- REGEL: nie Production-State/Logs/Peer-Dateien (MAC07, fremde claims/results) anfassen; nur Prefix server/state/isolated_run1 + logs/run1_server.log + run1_proof.json
- CLEANUP (GATED, nicht ausgeführt): `rm -rf server/state/isolated_run1 && mkdir -p server/state/isolated_run1/artifacts` + Lock-Release — erst bei READY_FOR_PHYSICAL_RUN=YES

## Run IDs
- run_id: observable, Pflicht (ContractError wenn leer)
- result_id: kanonisch result-{canonical_hash}, kein Worker-Override
- dispatch_id: dispatch-{uuid4}, attempt-Bindung task:attempt:N

DO_NOT_REPEAT_FINGERPRINT=sha256-mac09-artifact-chain-skeleton-01
NEXT_EXACT_ACTION=Block 2 schließen (task-owned expected hash aus isolierter Task-Definition lesen, sobald Staging-State bei READY existiert); bis dahin keine Ausführung.
