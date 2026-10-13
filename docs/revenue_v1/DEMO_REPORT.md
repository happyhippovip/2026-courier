# Demo-Läufe (echt, lokal, 13.10.2026 ca. 15:40 CEST)
Befehl: `python3 scripts/revenue_v1_safety_baseline.py worker task.json work_dir` und `... verify task.json work_dir result.json`, Skript-Stand origin/main 4b39599f2. Kein Kunde, `customer_reference: DEMO-NO-CUSTOMER`.

## Lauf A – psf/requests @ 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60 (Beispielbericht)
Worker PASS, Verifier PASS → HUMAN_REVIEW_REQUIRED. 8 Workflow-Dateien geprüft, 13 Befunde (8× fehlender concurrency-Block, 5× fehlendes timeout-minutes). Dateien: `demo/requests/` (report.md, report.json, result.json, verified.json, task.json).
report.json sha256 laut result: siehe `demo/requests/result.json`.

## Lauf B – pallets/flask @ d086db856be187255b8ec61ef409357393020f32 (Fehlerbeleg)
Worker PASS, Verifier PASS, aber `inspected_files: {}` – die 5 Workflows heißen `*.yaml` und werden nicht gelesen. Bericht „No safety violations detected.“ ist falsch-negativ. Dateien: `demo/flask/`.
