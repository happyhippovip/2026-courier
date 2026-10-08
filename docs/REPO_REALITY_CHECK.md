# Repo Reality Check

A local markdown report for one checkout. The scan reads files that are already on disk.

## What the customer gets

One markdown file. Headings are German, with a short English subtitle under each heading. The first section is the summary.

- **Kurzfassung** (Executive summary): six German sentences and an Ampel table for Tests, CI, Abhängigkeiten, Geheimnis-Risiko, and Repo-Hygiene. Every sentence and every Ampel cell uses a count from the scan. Grün, Gelb, and Rot follow the rules printed under Grenzen.
- **Repositorygröße** (Repository size): file count, and line counts grouped by language. Language comes from the filename extension. Extensions that are not in the known map collapse into one Sonstige row. The number in parentheses is how many of those extensions were found. The files and lines in that row are the sums.
- **Testdateien** (Test files): a file counts only when its name matches `test_*.py`, `*_test.py`, `*.test.js`, `*.spec.js`, or `*_test.go`, and it either contains at least one test function or lives under `test`, `tests`, or `__tests__`. `conftest.py`, fake/fakes, and builder/builders files are listed separately as Test-Hilfsdateien and are not test files.
- **Testergebnisse** (Pytest results): passed, failed, skipped, and error counts when a pytest JSON file is supplied.
- **Offene Marker** (TODO, FIXME, and HACK): counts, plus the files with the most markers.
- **CI-Konfiguration** (Continuous integration): which CI configs are present and how many jobs they declare. Recognized files include GitHub Actions, GitLab CI, CircleCI, Azure Pipelines, Bitbucket Pipelines, Travis CI, and a Jenkinsfile.
- **Projektdateien** (README, LICENSE, and gitignore): whether each of those files is present at the checkout root. A missing LICENSE stays in this section.
- **Abhängigkeiten** (Dependency manifests): manifests that were found, and how many dependencies are unpinned.
- **Größte Dateien** (Largest files): the largest files by byte size.
- **Hinweise auf Geheimnisse** (Secrets-risk patterns): pattern counts and file paths, split into production code and tests, fixtures, or docs. Production hits set that score component to 0. Hits only in tests, fixtures, or docs cost 2 points. Matched text is not in the report.
- **Repo-Hygiene** (Repository hygiene): missing LICENSE, committed binaries and archives over 1048576 bytes, JSON, JSONL, or NDJSON over 1048576 bytes, directories named attic, scratch, scratches, or scratchpad, and test-named files at the checkout root or under `scripts/`.
- **Realitätswert** (Reality score): a number from 0 to 100. The report lists every component weight, the points awarded, and any deductions.
- **Nächste fünf Schritte** (Top 5 next steps): five actions ordered by impact. Each line cites the count or path that produced it.

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

An exact pin is `==` or `===` in requirements and PEP 621 lists, a bare `major.minor.patch` in `package.json`, and a leading `=` for Poetry, Cargo, and Composer. Lockfiles are listed and are not counted as unpinned.

A test-named file outside a tests directory counts only when the scan finds at least one test function in it. The same file at the checkout root or under `scripts/` is also a stray-test hygiene finding. A test-named file with no test function still counts when it lives under `test`, `tests`, or `__tests__`.

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

The report below was generated from a small synthetic fixture:

- `README.md`, `LICENSE`, and `.gitignore` at the fixture root
- `requirements.txt` with one exact pin and one unpinned requirement
- `src/app.py` with one uppercase TODO
- `tests/test_app.py` with two test functions
- `tests/conftest.py`, listed as a Test-Hilfsdatei
- `.github/workflows/ci.yml` with one job
- `data/notes.txt`
- `config/app.env` with one synthetic assigned token (the value is not in the report)
- a pytest JSON summary of 3 passed, 1 failed, and 1 skipped

```markdown
# Repo Reality Check

Read-only scan of one local checkout. No network calls. Customer code was not executed. Pytest counts are included only when a pytest JSON file is supplied.

## Kurzfassung
_Executive summary_

Der Checkout enthält 10 Dateien und 25 Zeilen.
Statisch gezählt wurden 1 Testdatei, 2 Testfunktionen und 1 Test-Hilfsdatei; Pytest-JSON 3 bestanden, 1 fehlgeschlagen, 1 übersprungen, 0 Fehler.
CI: 1 Konfiguration und 1 Job.
Abhängigkeiten: 1 Manifest, 1 von 2 geparsten Einträgen mit exakter Version.
Geheimnis-Risiko: 1 Treffer in Produktionscode und 0 Treffer in Tests, Fixtures oder Docs.
Repo-Hygiene: 0 fehlende LICENSE, 0 Binär- oder Archivdateien über 1048576 Bytes, 0 scratch/attic-Verzeichnisse, 0 JSON/JSONL-Dateien über 1048576 Bytes, 0 verstreute Testdateien.

| Bereich | Ampel | Gemessen |
| --- | --- | --- |
| Tests | Gelb | 1 Testdatei, 2 Testfunktionen, Pytest 1 fehlgeschlagen, 0 Fehler |
| CI | Grün | 1 Konfiguration, 1 Job |
| Abhängigkeiten | Gelb | 1 Manifest, 1 ungepinnt von 2 |
| Geheimnis-Risiko | Rot | 1 Produktions-Treffer, 0 Treffer in Tests/Fixtures/Docs |
| Repo-Hygiene | Grün | 0 Auffälligkeiten, 0 fehlende LICENSE, 0 Binärdateien, 0 scratch/attic-Verzeichnisse, 0 JSON/JSONL-Dateien, 0 verstreute Testdateien |

## Repositorygröße
_Repository size_

- Files: 10
- Lines: 25

| Language | Files | Lines |
| --- | --- | --- |
| Markdown | 1 | 3 |
| Python | 3 | 10 |
| Text | 2 | 4 |
| YAML | 1 | 5 |
| no extension | 2 | 2 |
| Sonstige (1) | 1 | 1 |

## Testdateien
_Test files (static scan)_

- Test files: 1
- Test functions: 2
- Test-Hilfsdateien: 1

| File | Test functions |
| --- | --- |
| tests/test_app.py | 2 |

### Test-Hilfsdateien
_Test helper files_

| File |
| --- |
| tests/conftest.py |

## Testergebnisse
_Pytest results (pytest-json-report)_

- Status: parsed
- Passed: 3
- Failed: 1
- Skipped: 1
- Errors: 0

## Offene Marker
_TODO, FIXME, and HACK_

- TODO: 1
- FIXME: 0
- HACK: 0
- Total: 1

| File | TODO | FIXME | HACK | Total |
| --- | --- | --- | --- | --- |
| src/app.py | 1 | 0 | 0 | 1 |

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
- Unpinned dependencies: 1
- Pinned dependencies: 1
- Pin rule: requirements and PEP 621 count as pinned with `==` or `===`; package.json counts a bare major.minor.patch; Poetry, Cargo, and Composer count a leading `=`.

| Manifest | Kind | Pinned | Unpinned | Note |
| --- | --- | --- | --- | --- |
| requirements.txt | requirements | 1 | 1 | - |

## Größte Dateien
_Largest files_

| Bytes | Lines | File |
| --- | --- | --- |
| 51 | 5 | .github/workflows/ci.yml |
| 51 | 5 | tests/test_app.py |
| 38 | 4 | src/app.py |
| 33 | 1 | config/app.env |
| 25 | 2 | requirements.txt |
| 13 | 3 | README.md |
| 11 | 2 | data/notes.txt |
| 10 | 1 | LICENSE |
| 10 | 1 | tests/conftest.py |
| 6 | 1 | .gitignore |

## Hinweise auf Geheimnisse
_Secrets-risk patterns_

Counts and file paths only. Matched text is not included.

- Production hits: 1 in 1 file
- Tests, fixtures, and docs hits: 0 in 0 files
- Production hits set the secrets-risk component to 0. Hits only in tests, fixtures, or docs cost 2 points.

### Production code

| File | Hits |
| --- | --- |
| config/app.env | 1 |

### Tests, fixtures, and docs

No secrets-risk patterns.

| Pattern | Hits |
| --- | --- |
| assigned_secret | 1 |

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

Score: 80 / 100

Formula: 83 awarded - 3 deducted = 80, clamped to 80.

| Component | Weight | Awarded | Rule | Observation |
| --- | --- | --- | --- | --- |
| README | 10 | 10 | README file at the checkout root | present (README.md) |
| LICENSE | 5 | 5 | LICENSE file at the checkout root | present (LICENSE) |
| .gitignore | 8 | 8 | .gitignore at the checkout root | present (.gitignore) |
| Test files | 12 | 12 | at least one test file | 1 file |
| Test functions | 8 | 8 | at least one test function | 2 functions |
| CI config | 10 | 10 | at least one CI config | 1 config |
| CI jobs | 5 | 5 | at least one CI job | 1 job |
| Dependency manifest | 8 | 8 | at least one dependency manifest | 1 manifest |
| Pinned dependencies | 14 | 7 | share of parsed dependencies with an exact version pin | 1 pinned of 2 |
| Marker hygiene | 10 | 10 | one point off per 5 TODO, FIXME, or HACK markers, floor 0 | 1 marker |
| Secrets-risk hygiene | 10 | 0 | production secrets-risk hits score 0; hits only in tests, fixtures, or docs cost 2 | 1 production hit in 1 file |

| Deduction | Points | Rule | Observation |
| --- | --- | --- | --- |
| pytest failures and errors | 3 | 3 points each for failed and error, capped at 15; unusable JSON is 5 | 1 failed, 0 errors |

## Nächste fünf Schritte
_Top 5 next steps_

1. Remove 1 secrets-risk hit in production code (1 file: config/app.env).
2. Fix 1 failed and 0 error pytest results, then pass a fresh pytest JSON file.
3. Pin 1 unpinned dependency (1 pinned of 2 parsed).
4. Keep the measured test baseline: 1 test file and 2 test functions.
5. CI measurement: 1 config and 1 job.

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
```
