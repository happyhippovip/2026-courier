# Repo Reality Check

A local markdown report for one checkout. The scan reads files that are already on disk.

## What the customer gets

One markdown file, written in German. The first section is the summary.

- **Kurzfassung** (Executive summary): six sentences and an Ampel table for Tests, CI, Abhängigkeiten, Geheimnis-Risiko, and Repo-Hygiene. Every sentence and every Ampel cell uses a count from the scan. Grün, Gelb, and Rot follow the rules printed under Grenzen.
- **Repositorygröße** (Repository size): file count, and line counts grouped by language. Language comes from the filename extension. Extensions that are not in the known map collapse into one Sonstige row. The number in parentheses is how many of those extensions were found. The files and lines in that row are the sums.
- **Testdateien** (Test files): a test-named file (`test_*.py`, `*_test.py`, `*.test.*` or `*.spec.*` for JS/TS, `*_test.go`) counts when it contains at least one test function or lives under `test`, `tests`, or `__tests__`. JS/TS files in those directories count when they call `it()` or `test()`. Rust files count when they contain `#[test]` or `#[cfg(test)]`, or live under `tests`. Fixture directories never count. `conftest.py`, fake/fakes, and builder/builders files are listed separately as Test-Hilfsdateien and are not test files.
- **Testergebnisse** (Pytest results): passed, failed, skipped, and error counts when a pytest JSON file is supplied.
- **Offene Marker** (TODO, FIXME, and HACK): counts, plus the files with the most markers.
- **CI-Konfiguration** (Continuous integration): which CI configs are present and how many jobs they declare. Recognized files include GitHub Actions, GitLab CI, CircleCI, Azure Pipelines, Bitbucket Pipelines, Travis CI, and a Jenkinsfile.
- **Projektdateien** (README, LICENSE, and gitignore): whether each of those files is present at the checkout root. A missing LICENSE stays in this section.
- **Abhängigkeiten** (Dependency manifests): manifests that were found, and how many dependencies have neither an exact version nor a lockfile.
- **Größte Dateien** (Largest files): the largest files by byte size.
- **Hinweise auf Geheimnisse** (Secrets-risk patterns): pattern counts and file paths, split into production code and tests, fixtures, examples, or docs. Production hits set that score component to 0. Hits only in tests, fixtures, examples, or docs cost 2 points. GitHub Actions expressions such as `${{ secrets.NAME }}` are not counted. Matched text is not in the report.
- **Repo-Hygiene** (Repository hygiene): missing LICENSE, committed binaries and archives over 1 MB, JSON, JSONL, or NDJSON over 1 MB, directories named attic, scratch, scratches, or scratchpad, and test-named files at the checkout root or under `scripts/` (Go `*_test.go` next to the code is normal and not a finding).
- **Realitätswert** (Reality score): a number from 0 to 100. The report lists every component weight, the points awarded, and any deductions. A high score means the repository structure is complete, not that its tests passed; without real test results the Tests light stays Gelb.
- **Nächste fünf Schritte** (Top 5 next steps): five actions, findings first. Advice depends on the languages found; pytest advice appears only when Python tests exist.

The report ends with **Grenzen** (Limits): skipped directories, the file cap, and the per-file read cap.

## How a run works

The checkout is already on disk. When pass, fail, and skip counts are wanted, pytest is run separately and this tool only reads the JSON file that run produced (`pytest-json-report` shape).

```
python -m courier_core.repo_reality_report <repo_path> [--pytest-json FILE] [--out report.md]
python -m courier_core.repo_reality_report --github owner/repo[@ref] [--out report.md]
```

- `<repo_path>` is a local directory.
- `--pytest-json` is optional. Without it, the pytest section says the results were not supplied.
- `--out` writes the markdown to a file. Without it, the markdown goes to stdout.
- A local directory scan does not open network connections. `--github` downloads one public tarball; see below.
- The process does not execute files from the checkout and does not import them.
- The same tree and the same JSON produce the same markdown. Paths in the report are relative to the checkout root.
- Directories named `.git`, `node_modules`, virtual environments, and build output are skipped. The full skip list is printed in the report.
- The scan stops after 5000 files and reads at most 256 KiB of each file. Symlinks are skipped.

A missing checkout directory stops the command. A pytest JSON file that is missing, unreadable, or not valid JSON does not stop the command. That section says what happened, and the score table lists a deduction for unusable JSON. A parser error is not copied into the report, so a broken JSON file cannot echo its contents.

An exact pin is `==` or `===` in requirements and PEP 621 lists, a bare `major.minor.patch` in `package.json`, and a leading `=` for Poetry, Cargo, and Composer. A manifest counts as fully pinned when its ecosystem lockfile (Cargo.lock, package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, uv.lock, Pipfile.lock, go.sum, Gemfile.lock, composer.lock) sits in the same directory or above.

A test-named file outside a tests directory counts only when the scan finds at least one test function in it. The same file at the checkout root or under `scripts/` is also a hygiene finding, except Go `*_test.go` files. A test-named file with no test function still counts when it lives under `test`, `tests`, or `__tests__`.

## Public GitHub checkout

```
python -m courier_core.repo_reality_report --github owner/repo[@ref] --out report.md
```

- The tarball comes from codeload.github.com over HTTPS, using the Python standard library, with a 30 second timeout.
- A download larger than 50 MB is aborted. Extraction stops at 20,000 archive entries and 200 MB of file bytes.
- The archive is unpacked into a fresh temporary directory. Absolute paths, paths that contain `..`, device files, and symlinks or hardlinks that point outside that directory are rejected. Links that stay inside the checkout are not written; the scan does not follow them. The temporary directory is removed when the command finishes.
- The report header records the commit SHA and the sha256 of the downloaded tarball. When the archive's top directory does not already end with the full SHA, the commit is read from the public GitHub commit API.
- Nothing in the archive is executed.
- A missing or private repository exits 2 with a not-found message. No credentials are sent.

## Sample report

The report below is the unedited output for the public repository psf/requests at commit `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`, generated with `python -m courier_core.repo_reality_report --github psf/requests@611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`. No pytest JSON was supplied, so the tests were not run and the Tests light is Gelb.

````markdown
# Repo Reality Check

Nur lesende Prüfung eines öffentlichen GitHub-Tarballs. Der Code des Repos wurde nicht ausgeführt. Testergebnisse erscheinen nur, wenn eine Pytest-JSON-Datei mitgeliefert wurde.

- Quelle: github.com/psf/requests@611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
- Commit: 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
- Tarball-Prüfsumme (sha256): 83a67e83356762c4dfac7e75387826178fbf1041e2d2cd57259f4a5593474aa3

## Kurzfassung

Der Checkout enthält 128 Dateien und 20768 Zeilen.
Statisch gezählt: 9 Testdateien, 347 Testfunktionen und 1 Test-Hilfsdatei; die Tests wurden nicht ausgeführt.
CI: 8 Konfigurationen und 13 Jobs.
Abhängigkeiten: 3 Manifeste, 2 von 14 Einträgen exakt gepinnt oder per Lockfile gesperrt.
Geheimnis-Risiko: 0 Treffer im Produktionscode, 4 in Tests, Fixtures, Beispielen oder Doku.
Repo-Hygiene: LICENSE vorhanden, keine weiteren Auffälligkeiten.

| Bereich | Ampel | Gemessen |
| --- | --- | --- |
| Tests | Gelb | 9 Testdateien, 347 Testfunktionen, nicht ausgeführt |
| CI | Grün | 8 Konfigurationen, 13 Jobs |
| Abhängigkeiten | Gelb | 3 Manifeste, 12 von 14 ohne exakte Version oder Lockfile |
| Geheimnis-Risiko | Gelb | 0 im Produktionscode, 4 in Tests/Fixtures/Beispielen/Doku |
| Repo-Hygiene | Gelb | 1 Auffälligkeit: 7 Marker |

## Repositorygröße

- Dateien: 128
- Zeilen: 20768
- Nur teilweise gelesen (größer als 256 KB): 3

| Sprache | Dateien | Zeilen |
| --- | --- | --- |
| CSS | 1 | 12 |
| HTML | 1 | 33 |
| INI | 1 | 18 |
| Markdown | 13 | 2524 |
| Python | 37 | 12032 |
| TOML | 1 | 125 |
| Text | 2 | 10 |
| YAML | 12 | 470 |
| ohne Endung | 18 | 603 |
| reStructuredText | 16 | 2939 |
| Sonstige (12) | 26 | 2002 |

## Testdateien

- Testdateien: 9
- Testfunktionen: 347
- Test-Hilfsdateien: 1

| Datei | Testfunktionen |
| --- | --- |
| tests/test_adapters.py | 1 |
| tests/test_help.py | 3 |
| tests/test_hooks.py | 2 |
| tests/test_lowlevel.py | 13 |
| tests/test_packages.py | 3 |
| tests/test_requests.py | 237 |
| tests/test_structures.py | 13 |
| tests/test_testserver.py | 11 |
| tests/test_utils.py | 64 |

### Test-Hilfsdateien

| Datei |
| --- |
| tests/conftest.py |

## Testergebnisse

- Status: nicht mitgeliefert
- Bestanden, fehlgeschlagen, übersprungen, Fehler: keine Angabe

## Offene Marker

- TODO: 7
- FIXME: 0
- HACK: 0
- Gesamt: 7

| Datei | TODO | FIXME | HACK | Gesamt |
| --- | --- | --- | --- | --- |
| src/requests/_types.py | 2 | 0 | 0 | 2 |
| src/requests/models.py | 2 | 0 | 0 | 2 |
| src/requests/adapters.py | 1 | 0 | 0 | 1 |
| src/requests/hooks.py | 1 | 0 | 0 | 1 |
| tests/test_testserver.py | 1 | 0 | 0 | 1 |

## CI-Konfiguration

- Konfigurationen: 8
- Jobs: 13

| Art | Datei | Jobs |
| --- | --- | --- |
| GitHub Actions | .github/workflows/close-issues.yml | 2 |
| GitHub Actions | .github/workflows/codeql-analysis.yml | 1 |
| GitHub Actions | .github/workflows/lint.yml | 1 |
| GitHub Actions | .github/workflows/lock-issues.yml | 1 |
| GitHub Actions | .github/workflows/publish.yml | 3 |
| GitHub Actions | .github/workflows/run-tests.yml | 3 |
| GitHub Actions | .github/workflows/typecheck.yml | 1 |
| GitHub Actions | .github/workflows/zizmor.yml | 1 |

## Projektdateien

- README: vorhanden (README.md)
- LICENSE: vorhanden (LICENSE)
- .gitignore: vorhanden (.gitignore)

## Abhängigkeiten

- Manifeste: 3
- Ohne exakte Version und ohne Lockfile: 12
- Exakt gepinnt oder per Lockfile gesperrt: 2
- Regel: requirements und PEP 621 gelten mit `==` oder `===` als gepinnt, package.json mit einer reinen Version major.minor.patch, Poetry, Cargo und Composer mit führendem `=`. Liegt ein passendes Lockfile (Cargo.lock, package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, uv.lock, Pipfile.lock, go.sum, Gemfile.lock, composer.lock) im selben oder einem übergeordneten Ordner, gelten alle Einträge des Manifests als gepinnt.

| Manifest | Art | Gepinnt | Ungepinnt | Hinweis |
| --- | --- | --- | --- | --- |
| docs/requirements.txt | requirements | 1 | 0 | - |
| pyproject.toml | pyproject | 0 | 6 | - |
| requirements-dev.txt | requirements | 1 | 6 | - |

## Größte Dateien

| Bytes | Zeilen | Datei |
| --- | --- | --- |
| 2189478 | 1306 (Anfang) | ext/requests-logo.ai |
| 883794 | 1 (Anfang) | ext/requests-logo.svg |
| 306086 | binär | docs/_static/requests-sidebar.png |
| 192073 | binär | ext/requests-logo-compressed.png |
| 192073 | binär | ext/requests-logo.png |
| 108534 | 3094 | tests/test_requests.py |
| 64563 | 2102 | HISTORY.md |
| 41903 | 1137 | docs/user/advanced.rst |
| 41462 | 1184 | src/requests/models.py |
| 36061 | 1155 | src/requests/utils.py |

## Hinweise auf Geheimnisse

Nur Anzahl und Dateipfad. Der gefundene Text wird nicht übernommen.

- Treffer im Produktionscode: 0 in 0 Dateien
- Treffer in Tests, Fixtures, Beispielen und Doku: 4 in 4 Dateien
- Treffer im Produktionscode setzen die Geheimnis-Komponente auf 0. Treffer nur in Tests, Fixtures, Beispielen oder Doku kosten 2 Punkte und sind ein Hinweis zum Prüfen.

### Produktionscode

Keine Treffer.

### Tests, Fixtures, Beispiele und Doku

| Datei | Treffer |
| --- | --- |
| tests/certs/expired/ca/ca-private.key | 1 |
| tests/certs/expired/server/server.key | 1 |
| tests/certs/mtls/client/client.key | 1 |
| tests/certs/valid/server/server.key | 1 |

| Muster | Treffer |
| --- | --- |
| private_key | 4 |

## Repo-Hygiene

- LICENSE: vorhanden (LICENSE)
- Binär- oder Archivdateien über 1 MB: 0
- scratch/attic-Ordner: 0
- JSON/JSONL-Dateien über 1 MB: 0
- Testdateien außerhalb eines Testordners: 0

Keine großen Binär- oder JSON-Dateien, keine scratch-Ordner und keine Testdateien außerhalb eines Testordners.

## Realitätswert

Score: 85 / 100

Berechnung: 85 Punkte vergeben, 0 abgezogen = 85, auf 0 bis 100 begrenzt: 85.

| Komponente | Gewicht | Vergeben | Regel | Beobachtung |
| --- | --- | --- | --- | --- |
| README | 10 | 10 | README-Datei im Wurzelverzeichnis | vorhanden (README.md) |
| LICENSE | 5 | 5 | LICENSE-Datei im Wurzelverzeichnis | vorhanden (LICENSE) |
| .gitignore | 8 | 8 | .gitignore im Wurzelverzeichnis | vorhanden (.gitignore) |
| Testdateien | 12 | 12 | mindestens eine Testdatei | 9 Dateien |
| Testfunktionen | 8 | 8 | mindestens eine Testfunktion | 347 Funktionen |
| CI-Konfiguration | 10 | 10 | mindestens eine CI-Konfiguration | 8 Konfigurationen |
| CI-Jobs | 5 | 5 | mindestens ein CI-Job | 13 Jobs |
| Abhängigkeits-Manifest | 8 | 8 | mindestens ein Abhängigkeits-Manifest | 3 Manifeste |
| Gepinnte Abhängigkeiten | 14 | 2 | Anteil der Abhängigkeiten mit exakter Version oder Lockfile | 2 von 14 gepinnt |
| Marker-Hygiene | 10 | 9 | 1 Punkt Abzug je 5 TODO-, FIXME- oder HACK-Marker, nicht unter 0 | 7 Marker |
| Geheimnis-Hygiene | 10 | 8 | Treffer im Produktionscode ergeben 0; Treffer nur in Tests, Fixtures, Beispielen oder Doku kosten 2 | 0 im Produktionscode; 4 in Tests, Fixtures, Beispielen oder Doku in 4 Dateien |

| Abzug | Punkte | Regel | Beobachtung |
| --- | --- | --- | --- |
| Pytest: Fehlschläge und Fehler | 0 | je 3 Punkte pro Fehlschlag oder Fehler, höchstens 15; unbrauchbares JSON kostet 5 | nicht mitgeliefert, kein Abzug |

## Nächste fünf Schritte

1. 12 Abhängigkeiten haben weder eine exakte Version noch ein Lockfile (2 von 14 gepinnt). Für Anwendungen ein Lockfile committen oder exakt pinnen; bei Bibliotheken sind Versionsbereiche üblich.
2. 4 Geheimnis-Treffer in Tests, Fixtures, Beispielen oder Doku kurz prüfen (4 Dateien). Im Produktionscode wurde nichts gefunden.
3. 7 TODO-, FIXME- und HACK-Marker sichten, beginnend mit src/requests/_types.py (2).
4. Pytest-Ergebnisse mitliefern (pytest-json-report, Option --pytest-json), dann zeigt der Report bestandene und fehlgeschlagene Tests.
5. Testbasis halten: 9 Testdateien mit 347 Testfunktionen bei jedem Push in der CI ausführen.

## Grenzen

- Höchstens 5000 Dateien; je Datei werden höchstens 256 KB gelesen.
- Symbolische Links werden übersprungen.
- Übersprungene Ordner: `.cache`, `.eggs`, `.env`, `.git`, `.gradle`, `.mypy_cache`, `.next`, `.nuxt`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.venv`, `.virtualenv`, `__pycache__`, `build`, `coverage`, `dist`, `env`, `htmlcov`, `node_modules`, `site-packages`, `target`, `vendor`, `venv`, `virtualenv`
- Als Testdatei gilt: test_*.py, *_test.py, *.test.* und *.spec.* (JS/TS) sowie *_test.go, wenn die Datei mindestens eine Testfunktion enthält oder in test/, tests/ oder __tests__/ liegt. Außerdem JS/TS-Dateien in diesen Ordnern mit mindestens einem it()- oder test()-Aufruf, Rust-Dateien mit #[test] oder #[cfg(test)] und Rust-Dateien in tests/. Fixture-Ordner zählen nicht.
- Testfunktionen werden per Textmuster gezählt (Python `def test_*`, JS/TS `it(`/`test(`, Go `func Test*`, Rust `#[test]`). Dateien werden nicht importiert. Rust-Tests aus eigenen Makros und Tests in anderen Sprachen (z. B. Java, Ruby, PHP) werden nicht erkannt.
- Test-Hilfsdateien sind conftest.py sowie fake/fakes- und builder/builders-Dateien in einem Testordner. Sie zählen nicht als Testdateien.
- Testdateien direkt im Wurzelverzeichnis oder in scripts/ sind ein Hygiene-Hinweis. Go-Testdateien neben dem Code sind üblich und zählen nicht dazu.
- Marker sind die großgeschriebenen Wörter TODO, FIXME und HACK.
- Tests werden nicht ausgeführt. Bestanden, fehlgeschlagen und übersprungen stammen nur aus der optionalen Pytest-JSON-Datei.
- Geheimnis-Treffer in Tests, Fixtures, testdata/, Beispielen (examples/, example/), Doku oder Dateien wie README kosten 2 Punkte. Treffer im Produktionscode setzen die Komponente auf 0. GitHub-Actions-Ausdrücke wie `${{ secrets.NAME }}` zählen nicht. Der gefundene Text wird verworfen.
- Binär- und Archivdateien über 1 MB sowie JSON-, JSONL- und NDJSON-Dateien über 1 MB sind Hygiene-Hinweise.
- Als scratch-Ordner gelten: attic, scratch, scratches, scratchpad.
- Ampel Tests: Rot bei 0 Testdateien oder 0 Testfunktionen; Grün, wenn beide vorhanden sind und das Pytest-Ergebnis 0 Fehlschläge und 0 Fehler zeigt; sonst Gelb.
- Ampel CI: Rot ohne Konfiguration; Gelb, wenn Konfigurationen keinen Job enthalten; Grün mit mindestens einem Job.
- Ampel Abhängigkeiten: Rot ohne Manifest; Grün, wenn jede erkannte Abhängigkeit gepinnt oder per Lockfile gesperrt ist; sonst Gelb.
- Ampel Geheimnis-Risiko: Rot bei Treffern im Produktionscode; Gelb bei Treffern nur in Tests, Fixtures, Beispielen oder Doku; Grün ohne Treffer.
- Ampel Repo-Hygiene: Rot bei großen Binär- oder JSON-Dateien, scratch/attic-Ordnern oder ab 3 Auffälligkeiten; Gelb bei 1 oder 2; Grün bei 0. Auffälligkeiten: fehlende README, LICENSE oder .gitignore, 5 oder mehr Marker, große Binärdateien, große JSON-Dateien, scratch/attic-Ordner, Testdateien außerhalb eines Testordners.
- Der Wert ist die Summe der Gewichte oben. Er ist kein Sicherheitsurteil.
````
