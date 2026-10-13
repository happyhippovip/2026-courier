# Demo-Läufe (echt, lokal, 13.10.2026 ca. 15:50 CEST)
Befehl: `python3 scripts/revenue_v1_safety_baseline.py worker task.json work_dir` und `... verify task.json work_dir result.json`, Skript-Stand Branch revenue-v1-deliverable (mit `.yaml`-Support, NO_FILES_INSPECTED-Warnung und deutschem Bericht `report_de.md`). Kein Kunde, `customer_reference: DEMO-NO-CUSTOMER`.

## Lauf A – psf/requests @ 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
Worker PASS, Verifier PASS → HUMAN_REVIEW_REQUIRED. 8 Workflow-Dateien geprüft, 13 Befunde (8× fehlender concurrency-Block, 5× fehlendes timeout-minutes).
report.json sha256 216aaaf1636fa76f4125ca179ae9c51441fc63f7bf56867a9e4821138b34db93 (unverändert zum Erstlauf), report_de.md sha256 436bc242eee47015a662ce45b9637a453c33e559020b05577827eca258cabc9f. Dateien: `demo/requests/` (task.json, result.json, verified.json, report.json, report.md, report_de.md).

## Lauf B – pallets/flask @ d086db856be187255b8ec61ef409357393020f32
Erstlauf (Skript 4b39599f2): `inspected_files: {}`, Bericht „No safety violations detected.“ – falsch-negativ, weil nur `*.yml` gelesen wurde.
Aktueller Lauf: Worker PASS, Verifier PASS → HUMAN_REVIEW_REQUIRED. 5 Dateien geprüft (lock.yaml, pre-commit.yaml, publish.yaml, tests.yaml, zizmor.yaml), 5 Befunde: je 1× fehlendes `timeout-minutes`.
report.json sha256 50c874f593603bef05ce9eb33eb707ca3de0bacbbc2bfa357762635deec4ef2f, report_de.md sha256 c409133e1e0ac7aba40866a54dccf2f13e3748a70ffde81f04d5769f601f7615. Dateien: `demo/flask/`.

Hinweis: Beide Berichte erfordern vor Auslieferung eine menschliche Durchsicht; die Regeln sind Textsuchen (siehe PRODUKTSTAND.md, D3).
