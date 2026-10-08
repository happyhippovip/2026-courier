# Repo Reality Check

A local markdown report for one checkout. The scan reads files that are already on disk.

## What the customer gets

One markdown file. Headings are German, with a short English subtitle under each heading.

- **Repositorygröße** (Repository size): file count, and line counts grouped by language. Language comes from the filename extension.
- **Testdateien** (Test files): how many test files and test functions a static text scan found.
- **Testergebnisse** (Pytest results): passed, failed, skipped, and error counts when a pytest JSON file is supplied.
- **Offene Marker** (TODO, FIXME, and HACK): counts, plus the files with the most markers.
- **CI-Konfiguration** (Continuous integration): which CI configs are present and how many jobs they declare. Recognized files include GitHub Actions, GitLab CI, CircleCI, Azure Pipelines, Bitbucket Pipelines, Travis CI, and a Jenkinsfile.
- **Projektdateien** (README, LICENSE, and gitignore): whether each of those files is present at the checkout root.
- **Abhängigkeiten** (Dependency manifests): manifests that were found, and how many dependencies are unpinned.
- **Größte Dateien** (Largest files): the largest files by byte size.
- **Hinweise auf Geheimnisse** (Secrets-risk patterns): pattern counts and file paths. Matched text is not in the report.
- **Realitätswert** (Reality score): a number from 0 to 100. The report lists every component weight, the points awarded, and any deductions.
- **Nächste fünf Schritte** (Top 5 next steps): five actions derived from the findings, in a fixed priority order.

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
- `.github/workflows/ci.yml` with one job
- `data/notes.txt`
- `config/app.env` with one synthetic assigned token (the value is not in the report)
- a pytest JSON summary of 3 passed, 1 failed, and 1 skipped

```markdown
# Repo Reality Check

Read-only scan of one local checkout. No network calls. Customer code was not executed. Pytest counts are included only when a pytest JSON file is supplied.

## Repositorygröße
_Repository size_

- Files: 9
- Lines: 27

| Language | Files | Lines |
| --- | --- | --- |
| Markdown | 1 | 3 |
| Other (.env) | 1 | 1 |
| Python | 2 | 9 |
| Text | 2 | 6 |
| YAML | 1 | 5 |
| no extension | 2 | 3 |

## Testdateien
_Test files (static scan)_

- Test files: 1
- Test functions: 2

| File | Test functions |
| --- | --- |
| tests/test_app.py | 2 |

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
| 69 | 5 | tests/test_app.py |
| 61 | 4 | src/app.py |
| 60 | 3 | README.md |
| 59 | 5 | .github/workflows/ci.yml |
| 51 | 1 | config/app.env |
| 42 | 1 | LICENSE |
| 25 | 2 | requirements.txt |
| 23 | 4 | data/notes.txt |
| 19 | 2 | .gitignore |

## Hinweise auf Geheimnisse
_Secrets-risk patterns_

Counts and file paths only. Matched text is not included.

- Files: 1
- Pattern hits: 2

| File | Hits |
| --- | --- |
| config/app.env | 2 |

| Pattern | Hits |
| --- | --- |
| assigned_secret | 1 |
| github_token | 1 |

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
| Secrets-risk hygiene | 10 | 0 | no secrets-risk pattern hits | 2 hits in 1 file |

| Deduction | Points | Rule | Observation |
| --- | --- | --- | --- |
| pytest failures and errors | 3 | 3 points each for failed and error, capped at 15; unusable JSON is 5 | 1 failed, 0 errors |

## Nächste fünf Schritte
_Top 5 next steps_

1. Remove secret-shaped strings from the listed files and load those values from outside the checkout, then re-run this report.
2. Fix the failing tests recorded in the pytest JSON, then pass a fresh JSON file.
3. Pin dependency versions to exact releases in the manifests, then re-count unpinned entries.
4. Re-run the report after changes. The same tree and the same JSON produce the same markdown.
5. Keep dependency folders, virtual environments, and build directories out of the tree that you scan.

## Grenzen
_Limits_

- Max files: 5000
- Max bytes read per file: 262144
- Symlinks are skipped.
- Directories skipped: `.cache`, `.eggs`, `.env`, `.git`, `.gradle`, `.mypy_cache`, `.next`, `.nuxt`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.venv`, `.virtualenv`, `__pycache__`, `build`, `coverage`, `dist`, `env`, `htmlcov`, `node_modules`, `site-packages`, `target`, `vendor`, `venv`, `virtualenv`
- Test files and test functions are counted with text patterns. Files are not imported.
- Marker words are the uppercase tokens TODO, FIXME, and HACK.
- Pytest is not run. Pass, fail, and skip come from the optional JSON file.
- Secrets-risk checks keep a pattern name, a count, and a path. Match text is discarded.
- A score is a sum of the weights above. It is not a security verdict.
```
