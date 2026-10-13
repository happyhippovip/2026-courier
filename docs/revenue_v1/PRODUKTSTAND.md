# Revenue V1 – echter Produktstand (13.10.2026, origin/main 4b39599f2)

Grundlage: `.github/workflows/revenue_v1_baseline.yml`, `scripts/revenue_v1_safety_baseline.py` (191 Zeilen), Project-Memory `COURIER_AGENT_OPERATING_CONTEXT.md` (Abschnitt REVENUE V1 OPERATING CONTRACT).

## Was existiert
- Workflow `workflow_dispatch` mit Eingaben owner/repo/40-stelliger SHA/customer_reference/price_currency/delivery_destination; Regex-Validierung (Z. 51-62).
- Worker: sparse, depth-1, blobless Fetch nur von `.github/workflows/` am SHA (Skript Z. 22-31), `permissions: contents: read`.
- Ausgabe `report.json` + `report.md`, SHA-256 je Workflow-Datei, Result mit Hashes, `effect_classification: SAFE_READ_ONLY`.
- Verifier: Status PASS + `next_safe_state: HUMAN_REVIEW_REQUIRED`.
- Handoff: PR mit Ergebnis-JSON ins Courier-Repo, Reconciler prüft PR-/Commit-Bindung.

## Prüfregeln (vollständig, Skript Z. 41-52) – reine Textsuche pro Datei
1. `runs-on: self-hosted` → Self-hosted Runner
2. kein `timeout-minutes:` → fehlender Timeout
3. kein `permissions:` → fehlender Permissions-Block; `write-all` → zu weit
4. kein `concurrency:` → fehlender Concurrency-Block
5. `git push` → Mutationsrisiko

## Gefundene Mängel (aus Code + lokalem Lauf belegt)
- **D1 (kritisch): Nur `*.yml` wird gelesen** (`rglob("*.yml")`, Z. 37). `.yaml`-Workflows werden ignoriert. Beleg: pallets/flask @ d086db85… hat 5 `.yaml`-Workflows → `inspected_files: {}` und Bericht „No safety violations detected.“ = falsch-negativ (`demo/flask/`).
- D2: Bericht unterscheidet nicht „0 Dateien geprüft“ von „0 Befunde“.
- D3: Textsuche statt YAML-Parsing: Kommentare/Job-Ebene nicht unterschieden, ein `timeout-minutes` irgendwo genügt für die ganze Datei; `runs-on: [self-hosted, …]` wird nicht erkannt.
- D4: Wichtige Actions-Risiken fehlen ganz: `pull_request_target`, ungepinnte Actions (Tag statt SHA), Script-Injection `${{ github.event.* }}`, `secrets: inherit`, `persist-credentials`.
- D5: Verifier ist nicht unabhängig: er führt denselben `worker()`-Code erneut aus und vergleicht nur den Hash von report.json (Z. 101-107) – bestätigt Determinismus, nicht Richtigkeit.
- D6: Dateischlüssel nur `wf.name` (Unterordner-Kollision möglich).
- D7: Workflow-Beispieltext `USD 500.00` (Z. 23) widerspricht EUR 99.
- D8: Bericht ist englisch, ohne Erklärung, Schweregrad, Fix-Vorschlag oder Haftungshinweis.
- Kein pytest im Box-Python; `tests/test_revenue_v1_safety_baseline.py` nicht ausgeführt.

## Fazit
Pipeline (Intake → Worker → Verifier → HUMAN_REVIEW_REQUIRED) läuft lokal. Der Prüfinhalt ist für 99 € noch zu dünn und hat einen falsch-negativen Fehler (D1). Vor Verkauf mindestens D1, D2, D8 beheben und Bericht manuell reviewen.
