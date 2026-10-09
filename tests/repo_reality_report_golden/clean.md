# Repo Reality Check

Read-only scan of one local checkout. No network calls. Customer code was not executed. Pytest counts are included only when a pytest JSON file is supplied.

## Kurzfassung
_Executive summary_

Der Checkout enthält 6 Dateien und 11 Zeilen.
Statisch gezählt wurden 1 Testdatei, 1 Testfunktion und 0 Test-Hilfsdateien; Pytest-JSON nicht geliefert, 0 Zählwerte.
CI: 1 Konfiguration und 1 Job.
Abhängigkeiten: 1 Manifest, 1 von 1 geparsten Eintrag mit exakter Version.
Geheimnis-Risiko: 0 Treffer in Produktionscode und 0 Treffer in Tests, Fixtures oder Docs.
Repo-Hygiene: 0 fehlende LICENSE, 0 Binär- oder Archivdateien über 1048576 Bytes, 0 scratch/attic-Verzeichnisse, 0 JSON/JSONL-Dateien über 1048576 Bytes, 0 verstreute Testdateien.

| Bereich | Ampel | Gemessen |
| --- | --- | --- |
| Tests | Gelb | 1 Testdatei, 1 Testfunktion, Pytest nicht geliefert |
| CI | Grün | 1 Konfiguration, 1 Job |
| Abhängigkeiten | Grün | 1 Manifest, 0 ungepinnt von 1 |
| Geheimnis-Risiko | Grün | 0 Produktions-Treffer, 0 Treffer in Tests/Fixtures/Docs |
| Repo-Hygiene | Grün | 0 Auffälligkeiten, 0 Marker, 0 fehlende LICENSE, 0 Binärdateien, 0 scratch/attic-Verzeichnisse, 0 JSON/JSONL-Dateien, 0 verstreute Testdateien |

## Repositorygröße
_Repository size_

- Files: 6
- Lines: 11

| Language | Files | Lines |
| --- | --- | --- |
| Markdown | 1 | 1 |
| Python | 1 | 2 |
| Text | 1 | 1 |
| YAML | 1 | 5 |
| no extension | 2 | 2 |

## Testdateien
_Test files (static scan)_

- Test files: 1
- Test functions: 1
- Test-Hilfsdateien: 0

| File | Test functions |
| --- | --- |
| tests/test_app.py | 1 |

### Test-Hilfsdateien
_Test helper files_

No test helper files.

## Testergebnisse
_Pytest results (pytest-json-report)_

- Status: not supplied
- Passed: n/a
- Failed: n/a
- Skipped: n/a
- Errors: n/a

## Offene Marker
_TODO, FIXME, and HACK_

- TODO: 0
- FIXME: 0
- HACK: 0
- Total: 0

No markers.

## CI-Konfiguration
_Continuous integration_

- Configs: 1
- Jobs: 1

| Kind | File | Jobs |
| --- | --- | --- |
| GitHub Actions | .github/workflows/ci.yml | 1 |

## Projektdateien
_README, LICENSE, and gitignore_

- README: present (README.md)
- LICENSE: present (LICENSE)
- .gitignore: present (.gitignore)

## Abhängigkeiten
_Dependency manifests_

- Manifests: 1
- Unpinned dependencies: 0
- Pinned dependencies: 1
- Pin rule: requirements and PEP 621 count as pinned with `==` or `===`; package.json counts a bare major.minor.patch; Poetry, Cargo, and Composer count a leading `=`.

| Manifest | Kind | Pinned | Unpinned | Note |
| --- | --- | --- | --- | --- |
| requirements.txt | requirements | 1 | 0 | - |

## Größte Dateien
_Largest files_

| Bytes | Lines | File |
| --- | --- | --- |
| 59 | 5 | .github/workflows/ci.yml |
| 24 | 2 | tests/test_app.py |
| 13 | 1 | requirements.txt |
| 10 | 1 | LICENSE |
| 7 | 1 | README.md |
| 6 | 1 | .gitignore |

## Hinweise auf Geheimnisse
_Secrets-risk patterns_

Counts and file paths only. Matched text is not included.

- Production hits: 0 in 0 files
- Tests, fixtures, and docs hits: 0 in 0 files
- Production hits set the secrets-risk component to 0. Hits only in tests, fixtures, or docs cost 2 points.

### Production code

No secrets-risk patterns.

### Tests, fixtures, and docs

No secrets-risk patterns.

## Repo-Hygiene
_Repository hygiene_

- LICENSE: present (LICENSE)
- Binaries and archives over 1048576 bytes: 0
- Scratch or attic directories: 0
- JSON or JSONL over 1048576 bytes: 0
- Stray test files: 0

No large binaries, scratch directories, large JSON files, or stray tests.

## Realitätswert
_Reality score_

Score: 100 / 100

Formula: 100 awarded - 0 deducted = 100, clamped to 100.

| Component | Weight | Awarded | Rule | Observation |
| --- | --- | --- | --- | --- |
| README | 10 | 10 | README file at the checkout root | present (README.md) |
| LICENSE | 5 | 5 | LICENSE file at the checkout root | present (LICENSE) |
| .gitignore | 8 | 8 | .gitignore at the checkout root | present (.gitignore) |
| Test files | 12 | 12 | at least one test file | 1 file |
| Test functions | 8 | 8 | at least one test function | 1 function |
| CI config | 10 | 10 | at least one CI config | 1 config |
| CI jobs | 5 | 5 | at least one CI job | 1 job |
| Dependency manifest | 8 | 8 | at least one dependency manifest | 1 manifest |
| Pinned dependencies | 14 | 14 | share of parsed dependencies with an exact version pin | 1 pinned of 1 |
| Marker hygiene | 10 | 10 | one point off per 5 TODO, FIXME, or HACK markers, floor 0 | 0 markers |
| Secrets-risk hygiene | 10 | 10 | production secrets-risk hits score 0; hits only in tests, fixtures, or docs cost 2 | none |

| Deduction | Points | Rule | Observation |
| --- | --- | --- | --- |
| pytest failures and errors | 0 | 3 points each for failed and error, capped at 15; unusable JSON is 5 | not supplied; no deduction |

## Nächste fünf Schritte
_Top 5 next steps_

1. Pass a pytest JSON report with --pytest-json. Status: not supplied. Parsed counts: 0.
2. Keep the measured test baseline: 1 test file and 1 test function.
3. CI measurement: 1 config and 1 job.
4. Dependency pin share: 1 pinned of 1 parsed, across 1 manifests.
5. Secrets-risk measurement: 0 production hits and 0 hits in tests, fixtures, or docs.

## Grenzen
_Limits_

- Max files: 5000
- Max bytes read per file: 262144
- Symlinks are skipped.
- Directories skipped: `.cache`, `.eggs`, `.env`, `.git`, `.gradle`, `.mypy_cache`, `.next`, `.nuxt`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.venv`, `.virtualenv`, `__pycache__`, `build`, `coverage`, `dist`, `env`, `htmlcov`, `node_modules`, `site-packages`, `target`, `vendor`, `venv`, `virtualenv`
- A test file matches test_*.py, *_test.py, *.test.js, *.spec.js, or *_test.go, and either contains at least one test function or lives under test, tests, or __tests__.
- Test-Hilfsdateien are conftest.py anywhere, plus fake/fakes and builder/builders files under a test directory. They are not test files.
- Stray tests are test-named files at the checkout root or under scripts/. They are a hygiene finding.
- Test files and test functions are counted with text patterns. Files are not imported.
- Marker words are the uppercase tokens TODO, FIXME, and HACK.
- Pytest is not run. Pass, fail, and skip come from the optional JSON file.
- Secrets-risk hits in tests, fixtures, docs, test-named files, or doc names such as README cost 2 points. Production hits set that component to 0. Match text is discarded.
- Binaries and archives over 1048576 bytes, and JSON, JSONL, or NDJSON over 1048576 bytes, are hygiene findings.
- Scratch directory names: attic, scratch, scratches, scratchpad.
- Ampel Tests: Rot when test files or test functions are 0; Grün when both are positive and pytest JSON has 0 failed and 0 errors; otherwise Gelb.
- Ampel CI: Rot at 0 configs; Gelb when configs exist and jobs are 0; Grün when jobs are positive.
- Ampel Abhängigkeiten: Rot at 0 manifests; Grün when every parsed dependency is pinned; otherwise Gelb.
- Ampel Geheimnis-Risiko: Rot when production hits are positive; Gelb when only tests, fixtures, or docs have hits; Grün at 0 hits.
- Ampel Repo-Hygiene: Rot when a large binary/archive, a large JSON/JSONL file, or a scratch/attic directory is present, or when 3 or more hygiene flags are set; Gelb for 1 or 2 other flags; Grün at 0 flags. Flags: missing README, LICENSE, or .gitignore; 5 or more markers; large binaries; large JSON/JSONL; scratch/attic; stray tests.
- A score is a sum of the weights above. It is not a security verdict.
