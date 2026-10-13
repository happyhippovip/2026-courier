# Demo-Läufe (echt, lokal, 13.10.2026 ca. 15:55 CEST)
Befehl: `python3 scripts/revenue_v1_safety_baseline.py worker task.json work_dir` und `... verify task.json work_dir result.json`, Skript-Stand Branch revenue-v1-deliverable (mit `.yaml`-Support, NO_FILES_INSPECTED-Warnung, deutschem Bericht `report_de.md`, neuen Regeln pull_request_target / unpinned_action / script_injection und Pfad-Schlüsseln für Unterordner). Kein Kunde, `customer_reference: DEMO-NO-CUSTOMER`.

## Lauf A – psf/requests @ 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
Worker PASS, Verifier PASS → HUMAN_REVIEW_REQUIRED. 8 Workflow-Dateien geprüft, 13 Befunde (8× fehlender concurrency-Block, 5× fehlendes timeout-minutes).
report.json sha256 216aaaf1636fa76f4125ca179ae9c51441fc63f7bf56867a9e4821138b34db93 (unverändert zum Erstlauf), report_de.md sha256 e6bad5e30c468fedac979f679d885b5cb0c56d78079d9f29630049b693cb944e. Dateien: `demo/requests/` (task.json, result.json, verified.json, report.json, report.md, report_de.md).

## Lauf B – pallets/flask @ d086db856be187255b8ec61ef409357393020f32
Erstlauf (Skript 4b39599f2): `inspected_files: {}`, Bericht „No safety violations detected.“ – falsch-negativ, weil nur `*.yml` gelesen wurde.
Aktueller Lauf: Worker PASS, Verifier PASS → HUMAN_REVIEW_REQUIRED. 5 Dateien geprüft (lock.yaml, pre-commit.yaml, publish.yaml, tests.yaml, zizmor.yaml), 5 Befunde: je 1× fehlendes `timeout-minutes`.
report.json sha256 50c874f593603bef05ce9eb33eb707ca3de0bacbbc2bfa357762635deec4ef2f, report_de.md sha256 11cb962a2a19f67e5f58a072acfb1dacbb8de768d9c3cc94930c0dfbaee4f73e. Dateien: `demo/flask/`.

## Neue Regeln (D4) in beiden Läufen: 0 Befunde – manuell gegengeprüft
- unpinned_action: alle `uses:` in beiden Repos sind auf 40-stellige SHAs festgelegt (flask 21, requests 25 Zeilen geprüft).
- pull_request_target: kommt in keinem Workflow vor.
- script_injection: `github.event.*` kommt nur in `concurrency.group` (flask), `if:` und `env:` (requests close-issues.yml) vor, nicht direkt in `run:` – daher korrekt kein Befund.
report.json beider Läufe ist byte-gleich zum vorherigen Lauf (Hashes unverändert).

Hinweis: Beide Berichte erfordern vor Auslieferung eine menschliche Durchsicht; die Regeln sind Textsuchen (siehe PRODUKTSTAND.md, D3).
