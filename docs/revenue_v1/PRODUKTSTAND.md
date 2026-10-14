# Revenue V1 – echter Produktstand (14.10.2026, Branch `revenue-v1-deliverable` @ 67984bbac1)

Grundlage: `.github/workflows/revenue_v1_baseline.yml`, `scripts/revenue_v1_safety_baseline.py`, Project-Memory `COURIER_AGENT_OPERATING_CONTEXT.md` (Abschnitt REVENUE V1 OPERATING CONTRACT).

## Was existiert
- Workflow `workflow_dispatch` mit Eingaben owner/repo/40-stelliger SHA/customer_reference/price_currency/delivery_destination; Regex-Validierung (Z. 51-62).
- Worker: sparse, depth-1, blobless Fetch nur von `.github/workflows/` am SHA (Skript Z. 22-31), `permissions: contents: read`.
- Ausgabe `report.json` + `report.md` + `report_de.md`, SHA-256 je Workflow-Datei, Result mit Hashes, `effect_classification: SAFE_READ_ONLY`.
- Verifier: unabhängiger Verifier (D5) + Status; `next_safe_state: HUMAN_REVIEW_REQUIRED`.
- Handoff: PR mit Ergebnis-JSON ins Courier-Repo, Reconciler prüft PR-/Commit-Bindung.

## Prüfregeln (Kern; strukturbasiert per YAML wenn PyYAML verfügbar, sonst Text-Fallback)
1. Self-hosted Runner (`runs-on`)
2. fehlendes `timeout-minutes` (pro Job; Reusable-Workflow-Jobs ausgenommen)
3. fehlendes/zu weites `permissions` (`write-all`)
4. fehlendes `concurrency`
5. `git push` → Mutationsrisiko
6. zusätzlich (D4 teilweise): `pull_request_target`, ungepinnte Actions, Script-Injection über `${{ github.event.* }}` in `run:`

## Gefundene Mängel (aus Code + lokalem Lauf belegt)
- **D1 (BEHOBEN, Fix `481fd0bafe`): Nur `*.yml` wurde gelesen** – `.yaml`-Workflows wurden ignoriert (falsch-negativ). Jetzt: `rglob("*.yml")` und `rglob("*.yaml")`. Beleg aktuell: pallets/flask @ d086db85… → 5 `.yaml`-Dateien in `demo/flask/` mit Befunden (nicht mehr `inspected_files: {}`). Historischer Fehlbeleg: Erstlauf vor dem Fix.
- **D2 (BEHOBEN, Fix `481fd0bafe`):** 0 Dateien → `worker_status`/`verifier_status` WARN, `warning: NO_FILES_INSPECTED`, klarer Hinweis in report.md und report_de.md (unterscheidet „0 geprüft“ von „0 Befunde“).
- D3 (BEHOBEN: strukturbasierte Prüfung per PyYAML je Job/Step/Trigger, `on`→True berücksichtigt, Reusable-Workflow-Jobs beim Timeout ausgenommen; Fallback auf Textsuche bei fehlendem PyYAML oder kaputtem YAML, je Datei `parse_modes` yaml/text im report.json und im report_de.md): vorher Textsuche statt YAML-Parsing: Kommentare/Job-Ebene nicht unterschieden, ein `timeout-minutes` irgendwo genügt für die ganze Datei; `runs-on: [self-hosted, …]` wird nicht erkannt.
- D4 (BEHOBEN für pull_request_target, ungepinnte Actions, Script-Injection über `${{ github.event.* }}` in run:; weiterhin offen: `secrets: inherit`, `persist-credentials`): teilweise behoben; Rest offen wie genannt.
- D5 (BEHOBEN: eigenes Modul `scripts/revenue_v1_independent_verifier.py`, eigener Fetch + `git show SHA:pfad`, eigene Regelimplementierung, Hash-Abgleich, fail-closed, Identität mit Name/Version/sha256; siehe INDEPENDENT_VERIFIER.md): vorher war der Verifier nicht unabhängig (gleicher `worker()`-Code + Hash-Vergleich).
- D6 (BEHOBEN: Schlüssel ist jetzt der Pfad relativ zu `.github/workflows/`, z. B. `sub/ci.yml`): Dateischlüssel war nur `wf.name` (Unterordner-Kollision möglich).
- D7 (PATCH VORBEREITET, nicht angewendet – fehlender workflow-Scope): Workflow-Beispieltext (bisher USD-Betrag) → `EUR 99 (Einführungspreis, nicht validiert)`, siehe WORKFLOW_PATCH.md.
- **D8 (BEHOBEN, Fix `0115348fb6`):** zusätzlich `report_de.md` mit Erklärung, Schweregrad, Fix-Hinweis + YAML-Beispiel und Haftungs-/Review-Hinweis; englische report.md/report.json-Ausgabe unverändert im Regelinhalt.
- Tests: siehe Suite `tests/test_revenue_v1_safety_baseline.py` und independent-verifier-Tests.

## Regression D1 / D2 / D8 (belegt 14.10.2026)
Jeweils: aktueller Test gegen Skript-Stand vor dem Fix-Commit → FAIL; gegen aktuellen Stand → PASS.

| Mangel | Test | Pre-fix-Commit | Rot | Grün |
|--------|------|-----------------|-----|------|
| D1 | `TestRevenueSafetyBaseline.test_analyze_workflows_reads_yaml_extension` | `be5c2fbf2e` (Parent von `481fd0bafe`) | FAIL (`ci.yaml` fehlt in `inspected_files`) | PASS |
| D2 | `TestRevenueSafetyBaseline.test_worker_clean` | `be5c2fbf2e` (Parent von `481fd0bafe`) | FAIL (`worker_status` PASS statt WARN) | PASS |
| D8 | `TestRevenueSafetyBaseline.test_worker_writes_report_de_and_keeps_existing_outputs` | `481fd0bafe` (Parent von `0115348fb6`) | FAIL (`report_de.md` fehlt) | PASS |

## Fazit
Pipeline (Intake → Worker → Verifier → HUMAN_REVIEW_REQUIRED) läuft lokal. **D1, D2 und D8 sind behoben** (Regressionstabelle oben); sie sind kein Verkaufs-Blocker mehr. Der Prüfinhalt bleibt für 99 € begrenzt (u. a. D4 teilweise offen: `secrets: inherit` / `persist-credentials`; D7 Workflow-Patch nicht angewendet; PyYAML nicht in Laufzeit-Deps / Workflow installiert → Fallback `text`). Vor Auslieferung an Kunden: Bericht manuell reviewen.

## Abhängigkeit PyYAML (geprüft 13.10.2026)
- `pyproject.toml`: `PyYAML==6.0.3` steht nur unter `[project.optional-dependencies] test`, nicht in den Laufzeit-Abhängigkeiten.
- Bisher importierte kein anderes Courier-Skript `yaml` (außer gebündelten Libs unter `scripts/windows_worker/dist`).
- Der Workflow `revenue_v1_baseline.yml` installiert nichts und ruft `python3` direkt auf. Ob PyYAML auf dem Runner-Image vorhanden ist, wurde nicht geprüft; fehlt es, laufen alle Dateien im Prüfmodus `text` (sichtbar im Bericht). Worker und Verifier laufen im selben Image, die Hash-Prüfung bleibt also konsistent.
- Empfehlung (Workflow-Änderung, braucht workflow-Scope): `pip install PyYAML==6.0.3` vor Worker und Verifier, analog zu WORKFLOW_PATCH.md.
- Box-System-Python hat kein PyYAML; Demos und Tests liefen in `/workspace/.venv-rv1`.

## CI-Befund courier_motor.yml (13.10.2026, nur gelesen)
Alle Push-Runs von `.github/workflows/courier_motor.yml` auf `revenue-v1-deliverable` (be5c2fbf … 110c981b) und auf `main` (seit 4b39599f / bc385fea) enden mit `failure` ohne Jobs und ohne Log („log not found“). Ursache: Datei ist ungültiges YAML, weil Commit a3a77c7e6 (#57) die Zeile `on:` gelöscht hat. Nicht durch Revenue-V1-Änderungen verursacht. Fix nur als Workflow-Änderung möglich → WORKFLOW_PATCH.md, Punkt 5.
