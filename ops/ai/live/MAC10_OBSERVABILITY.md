# MAC10 Observability (minimal) — Checkpoint
- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- GATE_BASE=4c1e24ccc522042af826bc4c2b595daf85d097f9
- FINAL_SHA={{FINAL_SHA}} (unresolved, PRE_CODEX=DURABILITY_PENDING — kein Binding)
- DATE=2026-09-28
- MODE=prep-only (keine Ausführung vor READY_FOR_PHYSICAL_RUN=YES)
- SOURCE=ops/ai/RUN1_RUN2_EVIDENCE_CAPTURE_DESIGN_2026-09-28.md (Datum 1–21); ops/ai/hard_no_idle50/deliverables/HNI_14_EVENT_LOG_CORRELATION.md, HNI_15_IMMUTABLE_EVENT_STREAM.md; scripts/run1_physical/STATE_LOG_ARTIFACT_ISOLATION.md

## Status
- [x] 1 Event-Set definiert (nur beweisrelevant, diese Runde)
- [x] 2 Schema-Sample (1 Zeile je Event, Platzhalter-SHA)
- [x] 3 Replay-Abfrage (Events → Verdikt, inkl. Negativfälle)

## Regel
Append-only JSONL, ein Objekt pro Zeile, Pflichtfelder `ts,run,event,task`.
Isoliert je Run (`/tmp/courier_run1_{{FINAL_SHA}}/evidence/events.jsonl`,
`/tmp/courier_run2_{{FINAL_SHA}}/evidence/events.jsonl`), nach Ausführung read-only.
Keine stdout-Dumps, keine Metrik-Streams, keine Debug-Logs — nur untenstehende Events.

## RUN_1-Events (Datum 1–12)
- `step_a.dispatched` (D8-analog): `dispatch_id,attempt=1`
- `step_a.completed` (D1+D2): `execution_count=1,result_id,status=SUCCESS` (Source-Truth: RESULT_STATES={SUCCESS,FAILED}, `scripts/integration_contract.py:25` — COMPLETED wird mit 400 rejected)
- `step_a.hash_expected` (D3): `expected_sha256` (pre-deklariert, 64-hex)
- `step_a.hash_verified` (D4+D5): `server_sha256,verdict=PASS`
- `step_a.reconciled` (D6+D7): `status=RECONCILED,reconciled_at`
- `step_b.dispatched` (D8): `dispatch_id,attempt=1,dispatched_at>=reconciled_at`
- `step_b.started` (D9): `started_at`
- `step_b.reconciled` (D10): `step_b=RECONCILED,goal=DONE`
- `run.telemetry` (D11+D12): `human_relay_count=0,failed_execution_count=0`

## RUN_2-Events (Datum 13–21)
- `run2.checkpoint` (D13+D14+D15): `attempts=1,state_file_sha256,checkpoint_id=cutpoint-step-a-done`
- `run2.restart` (D16): `signal=SIGTERM,terminated=true,pids_distinct=true`
- `run2.post_restart` (D17+D18+D19): `attempts=1,replayed=false,status=RECONCILED`
- `run2.recovery` (D20+D21): `step_b.auto_dispatched=true,step_b=RECONCILED,goal=DONE`

## Falsifiability (je Event eine Zeile)
- dispatched ohne dispatch_id / attempt>1 → FAIL (Doppelvergabe)
- completed mit count!=1 oder ohne result_id → FAIL (A-once verletzt)
- hash_expected leer / aus Worker-Payload → FAIL (kein Trusted-Hash)
- server_sha256!=expected oder verdict!=PASS → FAIL (kein Server-Bytes-Beweis)
- B dispatched vor reconciled_at → FAIL (Kausalbruch)
- telemetry relay>0 oder failed>0 → FAIL (kein Zero-Relay/Clean-Run)
- post_restart attempts!=1 oder replayed=true → FAIL (Replay nach Restart)
- goal!=DONE → FAIL (kein Abschluss)

## Rekonstruktion (später, ohne Zusatzlogs)
1. events.jsonl je Run zeilenweise prüfen (Pflichtfelder + Reihenfolge).
2. `step_b.dispatched_at >= step_a.reconciled_at` assertieren.
3. Alle FAIL-Zeilen oben negieren; genau dann Verdikt PASS.
- DO_NOT_REPEAT_FINGERPRINT=sha256-mac10-observability-eventset-01

## 2 Schema-Sample (DONE)
```jsonl
{"ts":"2026-09-28T10:00:00Z","run":"run_001","event":"step_a.hash_expected","task":"<a>","expected_sha256":"FINAL_SHA_PLACEHOLDER_EXPECTED"}
{"ts":"2026-09-28T10:00:05Z","run":"run_001","event":"step_a.completed","task":"<a>","execution_count":1,"result_id":"result-<hex>","status":"SUCCESS"}
```

## 3 Replay-Abfrage (DONE)
- SUCCESS-Path: JSONL parsen -> Events in zeitlicher Folge anwenden. Wenn alle Pflicht-Events für Run vorliegen und B_dispatched >= A_reconciled, Verdict = PASS.
- Negativfall A (Double Dispatch): Dispatch-Event hat attempt > 1 -> SOFORT FAIL.
- Negativfall B (Hash Mismatch): `server_sha256` != `expected_sha256` -> SOFORT FAIL.
