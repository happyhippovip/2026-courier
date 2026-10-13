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
- **D1 (BEHOBEN im Branch revenue-v1-deliverable): Nur `*.yml` wird gelesen** (`rglob("*.yml")`, Z. 37). `.yaml`-Workflows werden ignoriert. Beleg: pallets/flask @ d086db85… hat 5 `.yaml`-Workflows → `inspected_files: {}` und Bericht „No safety violations detected.“ = falsch-negativ (`demo/flask/`).
- D2 (BEHOBEN: 0 Dateien → worker/verifier_status WARN, `warning: NO_FILES_INSPECTED`, Hinweis im report.md): Bericht unterschied nicht „0 Dateien geprüft“ von „0 Befunde“.
- D3 (BEHOBEN: strukturbasierte Prüfung per PyYAML je Job/Step/Trigger, `on`→True berücksichtigt, Reusable-Workflow-Jobs beim Timeout ausgenommen; Fallback auf Textsuche bei fehlendem PyYAML oder kaputtem YAML, je Datei `parse_modes` yaml/text im report.json und im report_de.md): vorher Textsuche statt YAML-Parsing: Kommentare/Job-Ebene nicht unterschieden, ein `timeout-minutes` irgendwo genügt für die ganze Datei; `runs-on: [self-hosted, …]` wird nicht erkannt.
- D4 (BEHOBEN für pull_request_target, ungepinnte Actions, Script-Injection über `${{ github.event.* }}` in run:; weiterhin offen: `secrets: inherit`, `persist-credentials`): Wichtige Actions-Risiken fehlen ganz: `pull_request_target`, ungepinnte Actions (Tag statt SHA), Script-Injection `${{ github.event.* }}`, `secrets: inherit`, `persist-credentials`.
- D5 (BEHOBEN: eigenes Modul `scripts/revenue_v1_independent_verifier.py`, eigener Fetch + `git show SHA:pfad`, eigene Regelimplementierung, Hash-Abgleich, fail-closed, Identität mit Name/Version/sha256; siehe INDEPENDENT_VERIFIER.md): vorher war der Verifier nicht unabhängig: er führt denselben `worker()`-Code erneut aus und vergleicht nur den Hash von report.json (Z. 101-107) – bestätigt Determinismus, nicht Richtigkeit.
- D6 (BEHOBEN: Schlüssel ist jetzt der Pfad relativ zu `.github/workflows/`, z. B. `sub/ci.yml`): Dateischlüssel war nur `wf.name` (Unterordner-Kollision möglich).
- D7 (PATCH VORBEREITET, nicht angewendet – fehlender workflow-Scope): Workflow-Beispieltext (bisher USD-Betrag) → `EUR 99 (Einführungspreis, nicht validiert)`, siehe WORKFLOW_PATCH.md.
- D8 (BEHOBEN): zusätzlich `report_de.md` mit Erklärung, Schweregrad, Fix-Hinweis + YAML-Beispiel und Haftungs-/Review-Hinweis; report.md/report.json unverändert.
- Tests: `tests/test_revenue_v1_safety_baseline.py` in venv ausgeführt: 49 passed (37 baseline + 12 independent verifier).

## Fazit
Pipeline (Intake → Worker → Verifier → HUMAN_REVIEW_REQUIRED) läuft lokal. Der Prüfinhalt ist für 99 € noch zu dünn und hat einen falsch-negativen Fehler (D1). Vor Verkauf mindestens D1, D2, D8 beheben und Bericht manuell reviewen.

## Abhängigkeit PyYAML (geprüft 13.10.2026)
- `pyproject.toml`: `PyYAML==6.0.3` steht nur unter `[project.optional-dependencies] test`, nicht in den Laufzeit-Abhängigkeiten.
- Bisher importierte kein anderes Courier-Skript `yaml` (außer gebündelten Libs unter `scripts/windows_worker/dist`).
- Der Workflow `revenue_v1_baseline.yml` installiert nichts und ruft `python3` direkt auf. Ob PyYAML auf dem Runner-Image vorhanden ist, wurde nicht geprüft; fehlt es, laufen alle Dateien im Prüfmodus `text` (sichtbar im Bericht). Worker und Verifier laufen im selben Image, die Hash-Prüfung bleibt also konsistent.
- Empfehlung (Workflow-Änderung, braucht workflow-Scope): `pip install PyYAML==6.0.3` vor Worker und Verifier, analog zu WORKFLOW_PATCH.md.
- Box-System-Python hat kein PyYAML; Demos und Tests liefen in `/workspace/.venv-rv1`.

## CI-Befund courier_motor.yml (13.10.2026, nur gelesen)
Alle Push-Runs von `.github/workflows/courier_motor.yml` auf `revenue-v1-deliverable` (be5c2fbf … 110c981b) und auf `main` (seit 4b39599f / bc385fea) enden mit `failure` ohne Jobs und ohne Log („log not found“). Ursache: Datei ist ungültiges YAML, weil Commit a3a77c7e6 (#57) die Zeile `on:` gelöscht hat. Nicht durch Revenue-V1-Änderungen verursacht. Fix nur als Workflow-Änderung möglich → WORKFLOW_PATCH.md, Punkt 5.
