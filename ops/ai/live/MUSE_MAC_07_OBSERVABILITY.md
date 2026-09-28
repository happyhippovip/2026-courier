# MUSE MAC WINDOW 7 — Observability: RUN_1/RUN_2-Rekonstruktion aus Evidence
- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- DATE=2026-09-28
- QUELLE=ops/ai/RUN1_RUN2_EVIDENCE_CAPTURE_DESIGN_2026-09-28.md (Datum 1–21); ops/ai/live/MAC05_RUN1_EVIDENCE.md; ops/ai/live/MAC10_OBSERVABILITY.md; scripts/run1_physical/
- VERDIKT=NEIN — ein fremder Reviewer kann RUN_1/RUN_2 heute NICHT allein aus Evidence rekonstruieren (alle Proof-Artefakte PENDING: kein run1_proof.json/run2_proof.json/events.jsonl im Repo; MAC05=PREPARED_NOT_EXECUTED).

## Abdeckung Soll-Punkte
- task/attempt/dispatch: Design D1/D8/D13 definiert, aber keine durable Ablage mit IDs vorhanden.
- execution start/end: nur Worker-Log-Quelle (D9), kein Evidence-Slot mit Timestamps.
- result/artifact: Template vorhanden (RUN1_RESULT_TEMPLATE.json), keine befüllte Instanz.
- verify/reconcile: teilen sich EIN Contract (RUN1_VERIFY_RECONCILE_PROOF_CONTRACT.md) — als separate Zeitpunkte nicht unterscheidbar.
- NEXT_READY: kein Event definiert (MAC10-Eventset enthält keins).
- B dispatch/start: D8/D9 definiert, keine Instanz.
- restart/execution counts: D15–D18 definiert, keine Instanz.

## Fehlende/mehrdeutige Punkte (5)
- G1 KEINE_TIMESTAMPS_IN_RESULTS: MT-01..05 + MUSE-VERIFY-001 enthalten keine dispatched_at/reconciled_at/started_at/TIMESTAMP-Felder (grep-leer verifiziert) — Ordnung dispatch→verify→reconcile unbelegbar.
- G2 ATTEMPT_DISPATCH_IDENTITY: keine attempt-/dispatch-IDs in Results; Triple-Authority (dispatch-/uuid4-/bare-uuid4) ohne Format-Enforcement — attempt vs dispatch vs execution mehrdeutig.
- G3 VERIFY_VS_RECONCILE: MAC05-Slots 5+6 teilen einen Contract; kein getrennter Marker — Reviewer sieht nicht, ob verify ohne reconcile (S4-Fall) vorlag.
- G4 NEXT_READY_UNSICHTBAR: Scheduler-Recompute (S5-Recovery) hinterlässt kein Event; B-Autostart (D20) ohne Vorgänger-Nachweis nicht von manuellem Dispatch unterscheidbar.
- G5 RESTART_BINDUNG: D14 (pre state_file_sha256) vs D17 (post reload) ohne Gleichheits-Assertion im Design; checkpoint_id/PIDs ohne durable Ablage — No-Replay (D18) aus Evidence nicht prüfbar.

## BACKUP=Timestamp-/Ordering-Semantik
- BACKUP=NONE — kein Evidence-Backup vorhanden (kein events.jsonl, kein run1/run2_proof.json im Repo).
- SEMANTIK-MANGEL: Claims mischen `Z`-UTC (MT-02: 2026-09-28T02:11:00Z) und `+02:00`-Offsets (MUSE-02); Design fordert teils Mikrosekunden-Präzision (D7), teils ISO8601-UTC (D9) — keine einheitliche Regel, Offset-Vergleiche mehrdeutig.
- FOLGE: Selbst nach Ausführung wäre `step_b.dispatched_at >= step_a.reconciled_at` ohne normierte Zeitzone/Präzision anfechtbar → an MAC10-Eigner: ts-Norm (UTC, µs) + Pflichtfeld-Regel vor RUN_1 festschreiben.

DO_NOT_REPEAT_FINGERPRINT=sha256-muse-mac07-observability-01
