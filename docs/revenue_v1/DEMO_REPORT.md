# Demo-Läufe (echt, lokal, 13.10.2026 ca. 16:00 CEST)
Befehl: `/workspace/.venv-rv1/bin/python scripts/revenue_v1_safety_baseline.py worker task.json work_dir` und `... verify task.json work_dir result.json` (venv mit PyYAML 6.x), Skript-Stand Branch revenue-v1-deliverable mit YAML-Parsing (D3). Kein Kunde, `customer_reference: DEMO-NO-CUSTOMER`. Alle Dateien beider Repos im Prüfmodus `yaml` (`parse_modes` in report.json).

## Lauf A – psf/requests @ 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
Worker PASS, Verifier PASS → HUMAN_REVIEW_REQUIRED. 8 Dateien, **14 Befunde** (8× concurrency, 6× timeout). report.json sha256 e9a1bfa5e553c689f556f68e77872aa506336627e3376a3c72a0e50790ab5a08, report_de.md sha256 7ae559a5b8ae094c41899c21a6b65cc12082980e4c3d62c3f32ae45c588adabe. Dateien: `demo/requests/`.

## Lauf B – pallets/flask @ d086db856be187255b8ec61ef409357393020f32
Worker PASS, Verifier PASS → HUMAN_REVIEW_REQUIRED. 5 Dateien, **5 Befunde** (5× timeout). report.json sha256 d7d7043a9c1a98a497de6ba34766e58b9b47b0fe38722103504feeca01c22cfd, report_de.md sha256 88b167cd24210fdcff52e00386677f5d129ec0c4d77ff2538ffef49e71412b91. Dateien: `demo/flask/`.
Historie: Erstlauf (Skript 4b39599f2) `inspected_files: {}` / „No safety violations detected.“ – falsch-negativ, weil nur `*.yml` gelesen wurde.

## Vergleich Textsuche (a811ad55) → YAML-Parsing
- requests: 13 → 14. Neu: `run-tests.yml` timeout (Jobs `no_chardet`, `urllib3`). Die Textsuche sah ein `timeout-minutes:` im Job `build` (Z. 11) und hielt die ganze Datei für ok; die YAML-Prüfung prüft pro Job (manuell bestätigt: nur `build` hat ein Zeitlimit).
- Alle timeout-Befunde nennen jetzt die betroffenen Jobs, z. B. `publish.yml` (build, publish, publish-test-pypi).
- concurrency (requests 8×), permissions, pull_request_target, unpinned_action, script_injection: unverändert (kein Wegfall, kein Zuwachs).
- flask: gleiche 5 Befunde, nur Text mit Jobnamen ergänzt.

Hinweis: Beide Berichte erfordern vor Auslieferung eine menschliche Durchsicht.
