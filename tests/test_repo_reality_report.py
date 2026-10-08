"""Local Repo Reality Check. Fixtures live under tmp_path. No network."""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from courier_core import repo_reality_report as report
from courier_core.repo_reality_report import analyze, build_report, main

ROOT = Path(__file__).resolve().parents[1]
HEADINGS = (
    "## Kurzfassung",
    "## Repositorygröße",
    "## Testdateien",
    "## Testergebnisse",
    "## Offene Marker",
    "## CI-Konfiguration",
    "## Projektdateien",
    "## Abhängigkeiten",
    "## Größte Dateien",
    "## Hinweise auf Geheimnisse",
    "## Repo-Hygiene",
    "## Realitätswert",
    "## Nächste fünf Schritte",
    "## Grenzen",
)


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    return repo


def _score(text: str) -> int:
    line = next(item for item in text.splitlines() if item.startswith("Score: "))
    return int(line.split()[1])


def test_repository_size_and_languages(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "src/app.py", "x = 1\n")
    _write(repo, "README.md", "# Title\n\nBody\n")
    _write(repo, "notes.txt", "hi")
    _write(repo, "Makefile", "all:\n")
    data = analyze(repo)
    text = build_report(repo)
    assert data["files"] == 4
    assert data["lines"] == 6
    assert [(row["name"], row["files"], row["lines"]) for row in data["languages"]] == [
        ("Markdown", 1, 3),
        ("Python", 1, 1),
        ("Text", 1, 1),
        ("ohne Endung", 1, 1),
    ]
    assert "- Dateien: 4" in text
    assert "- Zeilen: 6" in text
    assert text.index("| Markdown |") < text.index("| Python |") < text.index("| Text |")
    assert "_Repository size_" not in text


def test_test_file_and_function_counts(tmp_path):
    repo = _repo(tmp_path)
    _write(
        repo,
        "tests/test_app.py",
        "def test_one():\n    pass\n\nasync def test_two():\n    pass\n\ndef helper():\n    pass\n",
    )
    _write(repo, "src/app.py", "def test_not_counted():\n    pass\n")
    _write(repo, "web/demo.test.js", "test('a', () => {})\nit('b', () => {})\n")
    _write(repo, "lib/widget_test.go", "func TestAdd(t *testing.T) {\n}\nfunc helper() {}\n")
    _write(repo, "node_modules/left/test_skip.py", "def test_hidden():\n    pass\n")
    data = analyze(repo)
    assert data["test_files"] == 3
    assert data["test_functions"] == 5
    assert data["test_file_rows"] == [
        {"path": "lib/widget_test.go", "functions": 1},
        {"path": "tests/test_app.py", "functions": 2},
        {"path": "web/demo.test.js", "functions": 2},
    ]
    text = build_report(repo)
    assert "- Testdateien: 3" in text
    assert "- Testfunktionen: 5" in text
    assert "test_skip.py" not in text
    assert "| Datei | Testfunktionen |" in text


def test_pytest_summary_counts(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "README.md", "# Demo\n")
    payload = {
        "summary": {"passed": 4, "failed": 1, "skipped": 2, "error": 3, "total": 10},
        "tests": [{"nodeid": "hidden", "outcome": "passed"}],
    }
    blob = tmp_path / "pytest.json"
    blob.write_text(json.dumps(payload), encoding="utf-8")
    data = analyze(repo, blob)
    text = build_report(repo, blob)
    assert data["pytest"] == {"status": "ok", "passed": 4, "failed": 1, "skipped": 2, "errors": 3}
    assert "- Bestanden: 4" in text
    assert "- Fehlgeschlagen: 1" in text
    assert "- Übersprungen: 2" in text
    assert "- Fehler: 3" in text
    assert "hidden" not in text
    assert str(blob) not in text


def test_pytest_counts_tests_array_without_summary(tmp_path):
    repo = _repo(tmp_path)
    secret = "ghp_" + "C" * 36
    payload = {
        "tests": [
            {"nodeid": "t::a", "outcome": "passed", "call": {"longrepr": secret}},
            {"nodeid": "t::b", "outcome": "failed"},
            {"nodeid": "t::c", "outcome": "skipped"},
            {"nodeid": "t::d", "outcome": "error"},
            {"nodeid": "t::e", "outcome": "xfailed"},
        ]
    }
    blob = tmp_path / "pytest.json"
    blob.write_text(json.dumps(payload), encoding="utf-8")
    data = analyze(repo, blob)
    text = build_report(repo, blob)
    assert data["pytest"]["passed"] == 1
    assert data["pytest"]["failed"] == 1
    assert data["pytest"]["skipped"] == 1
    assert data["pytest"]["errors"] == 1
    assert secret not in text
    assert secret not in json.dumps(data)


def test_malformed_and_unreadable_pytest_json(tmp_path):
    repo = _repo(tmp_path)
    secret = "ghp_" + "D" * 36
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json " + secret, encoding="utf-8")
    data = analyze(repo, bad)
    text = build_report(repo, bad)
    assert data["pytest"]["status"] == "malformed"
    assert "kein gültiges JSON" in text
    assert "fehlgeschlagen, übersprungen, Fehler: keine Angabe" in text
    assert secret not in text
    assert "JSONDecodeError" not in text
    assert "Expecting" not in text
    assert data["score"]["value"] == 15

    weird = tmp_path / "list.json"
    weird.write_text("[1, 2]", encoding="utf-8")
    assert analyze(repo, weird)["pytest"]["status"] == "unexpected"
    assert "unerwartetes Format" in build_report(repo, weird)

    missing = analyze(repo, tmp_path / "missing.json")
    assert missing["pytest"]["status"] == "unreadable"
    assert "Datei nicht lesbar" in build_report(repo, tmp_path / "missing.json")

    empty = analyze(repo, None)
    assert empty["pytest"]["status"] == "not_supplied"
    assert "- Status: nicht mitgeliefert" in build_report(repo)


def test_marker_counts_and_top_files(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "src/a.py", "TODO\nTODO\nFIXME\n")
    _write(repo, "src/b.py", "HACK\n")
    _write(repo, "src/c.py", "todo later\n")
    data = analyze(repo)
    text = build_report(repo)
    assert data["markers"]["todo"] == 2
    assert data["markers"]["fixme"] == 1
    assert data["markers"]["hack"] == 1
    assert data["markers"]["total"] == 4
    assert [row["path"] for row in data["markers"]["top_files"]] == ["src/a.py", "src/b.py"]
    assert "- TODO: 2" in text
    assert "- FIXME: 1" in text
    assert "- HACK: 1" in text
    assert "- Gesamt: 4" in text
    marker_section = text.split("## Offene Marker", 1)[1].split("## CI-Konfiguration", 1)[0]
    assert text.index("| src/a.py |") < text.index("| src/b.py |")
    assert "src/c.py" not in marker_section


def test_ci_configs_and_job_counts(tmp_path):
    repo = _repo(tmp_path)
    _write(
        repo,
        ".github/workflows/ci.yml",
        "name: CI\non:\n  push:\njobs:\n  test:\n    runs-on: ubuntu-latest\n  lint:\n    runs-on: ubuntu-latest\n",
    )
    _write(
        repo,
        ".gitlab-ci.yml",
        "stages:\n  - test\nunit:\n  script:\n    - pytest\nlint:\n  script:\n    - echo lint\n",
    )
    _write(repo, ".circleci/config.yml", "jobs:\n  build:\n    docker:\n      - image: base\n")
    _write(repo, "azure-pipelines.yml", "jobs:\n- job: One\n  steps: []\n- job: Two\n  steps: []\n")
    _write(repo, "Jenkinsfile", "pipeline {\n  stages {\n    stage('Build') {}\n    stage('Test') {}\n  }\n}\n")
    _write(repo, ".travis.yml", "language: python\nscript:\n  - pytest\n")
    data = analyze(repo)
    assert data["ci"]["rows"] == [
        {"kind": "Azure Pipelines", "path": "azure-pipelines.yml", "jobs": 2},
        {"kind": "CircleCI", "path": ".circleci/config.yml", "jobs": 1},
        {"kind": "GitHub Actions", "path": ".github/workflows/ci.yml", "jobs": 2},
        {"kind": "GitLab CI", "path": ".gitlab-ci.yml", "jobs": 2},
        {"kind": "Jenkins", "path": "Jenkinsfile", "jobs": 2},
        {"kind": "Travis CI", "path": ".travis.yml", "jobs": 1},
    ]
    assert data["ci"]["configs"] == 6
    assert data["ci"]["jobs"] == 10
    text = build_report(repo)
    assert "- Konfigurationen: 6" in text
    assert "- Jobs: 10" in text
    assert "| Art | Datei | Jobs |" in text


def test_project_files(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "README.md", "# Demo\n")
    _write(repo, ".gitignore", "venv/\n")
    _write(repo, "docs/README.md", "# nested\n")
    data = analyze(repo)
    text = build_report(repo)
    assert data["project_files"]["readme"] == {"present": True, "path": "README.md"}
    assert data["project_files"]["license"] == {"present": False, "path": None}
    assert data["project_files"]["gitignore"] == {"present": True, "path": ".gitignore"}
    assert "- README: vorhanden (README.md)" in text
    assert "- LICENSE: fehlt" in text
    assert "- .gitignore: vorhanden (.gitignore)" in text


def test_dependency_pin_counts(tmp_path):
    repo = _repo(tmp_path)
    _write(
        repo,
        "requirements.txt",
        "flask==1.2.3\nrequests>=2.0\nnumpy\n# comment\n-r base.txt\n",
    )
    _write(
        repo,
        "pyproject.toml",
        "[project]\nname = \"demo\"\nversion = \"0.1.0\"\ndependencies = [\n  \"flask==2.0.0\",\n  \"requests>=2\",\n]\n",
    )
    _write(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"left-pad": "^1.0.0", "exact-thing": "1.2.3"},
                "devDependencies": {"tool": "1.0.0"},
            }
        ),
    )
    _write(repo, "package-lock.json", "{\"lock\": true}\n")
    _write(
        repo,
        "node_modules/pkg/package.json",
        json.dumps({"dependencies": {"loose": "*"}}),
    )
    data = analyze(repo)
    by_path = {row["path"]: row for row in data["dependencies"]["rows"]}
    assert by_path["requirements.txt"]["pinned"] == 1
    assert by_path["requirements.txt"]["unpinned"] == 2
    assert by_path["pyproject.toml"]["pinned"] == 1
    assert by_path["pyproject.toml"]["unpinned"] == 1
    # package-lock.json next to package.json locks every entry, including "^1.0.0".
    assert by_path["package.json"]["pinned"] == 3
    assert by_path["package.json"]["unpinned"] == 0
    assert by_path["package.json"]["locked_by"] == "package-lock.json"
    assert by_path["package-lock.json"]["note"] == "Lockfile"
    assert "locked_by" not in by_path["requirements.txt"]
    assert "node_modules/pkg/package.json" not in by_path
    assert data["dependencies"]["unpinned"] == 3
    assert data["dependencies"]["pinned"] == 5
    assert data["dependencies"]["ratio_pinned"] == 5
    assert data["dependencies"]["ratio_unpinned"] == 3
    text = build_report(repo)
    assert "- Ohne exakte Version und ohne Lockfile: 3" in text
    assert "- Exakt gepinnt oder per Lockfile gesperrt: 5" in text
    assert "- Manifeste: 4" in text
    assert "gesperrt durch package-lock.json" in text

    broken = tmp_path / "broken-json"
    broken.mkdir()
    _write(broken, "package.json", "{not json")
    parsed = analyze(broken)
    assert parsed["dependencies"]["rows"][0]["note"] == "nicht lesbar"
    assert "nicht lesbar" in build_report(broken)


def test_go_cargo_and_setup_cfg_pins(tmp_path):
    repo = _repo(tmp_path)
    _write(
        repo,
        "go.mod",
        "module localmod\n\ngo 1.22\n\nrequire (\n\tlocal/mod v1.2.3\n)\nrequire local/tool v0.1.0\n",
    )
    _write(
        repo,
        "Cargo.toml",
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n\n[dependencies]\nleft = \"1.2.3\"\nexact = \"=1.2.3\"\n",
    )
    _write(repo, "setup.cfg", "[options]\ninstall_requires =\n    flask==1.0\n    requests\n")
    by_path = {row["path"]: row for row in analyze(repo)["dependencies"]["rows"]}
    assert (by_path["go.mod"]["pinned"], by_path["go.mod"]["unpinned"]) == (2, 0)
    assert (by_path["Cargo.toml"]["pinned"], by_path["Cargo.toml"]["unpinned"]) == (1, 1)
    assert (by_path["setup.cfg"]["pinned"], by_path["setup.cfg"]["unpinned"]) == (1, 1)


def test_largest_files_sorted(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "small.txt", "a\n")
    _write(repo, "mid.txt", "bbbb\n")
    (repo / "tie-b.bin").write_bytes(b"\0" * 4)
    (repo / "tie-a.bin").write_bytes(b"\0" * 4)
    data = analyze(repo)
    assert [row["path"] for row in data["largest"]] == ["mid.txt", "tie-a.bin", "tie-b.bin", "small.txt"]
    text = build_report(repo)
    assert text.index("| mid.txt |") < text.index("| tie-a.bin |") < text.index("| tie-b.bin |")
    assert "| binär |" in text


def test_secrets_values_never_appear(tmp_path):
    repo = _repo(tmp_path)
    token = "ghp_" + "B" * 36
    password = "hunter2hunter2"
    aws = "AKIA" + "0" * 16
    header = "-----BEGIN " + "PRIVATE KEY-----"
    _write(
        repo,
        "config/app.env",
        f'TOKEN = "{token}"\npassword = "{password}"\n{aws}\n{header}\n',
    )
    data = analyze(repo)
    text = build_report(repo)
    dumped = json.dumps(data)
    for secret in (token, password, aws, header):
        assert secret not in text
        assert secret not in dumped
    assert "config/app.env" in text
    assert data["secrets"]["files"] == 1
    assert data["secrets"]["hits"] >= 4
    assert {row["pattern"] for row in data["secrets"]["pattern_rows"]} >= {
        "assigned_secret",
        "aws_access_key",
        "github_token",
        "private_key",
    }
    assert "Nur Anzahl und Dateipfad" in text
    assert "in 1 Datei" in text
    assert "in 1 Dateien" not in text


def test_score_bounds_weights_and_exact_values(tmp_path):
    empty = _repo(tmp_path)
    empty_data = analyze(empty)
    assert empty_data["score"]["value"] == 20
    assert _score(build_report(empty)) == 20

    perfect = _perfect(tmp_path)
    perfect_data = analyze(perfect)
    assert perfect_data["score"]["value"] == 100
    perfect_text = build_report(perfect)
    assert "Score: 100 / 100" in perfect_text
    assert sum(row["weight"] for row in perfect_data["score"]["components"]) == 100
    for row in perfect_data["score"]["components"]:
        assert f"| {row['label']} | {row['weight']} | {row['awarded']} |" in perfect_text
        assert row["rule"] in perfect_text
        assert 0 <= row["awarded"] <= row["weight"]

    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps({"summary": {"passed": 1, "failed": 6, "skipped": 0}}), encoding="utf-8")
    failed_data = analyze(perfect, failed)
    assert failed_data["score"]["deducted"] == 15
    assert failed_data["score"]["value"] == 85

    for repo, blob in ((empty, None), (perfect, failed)):
        data = analyze(repo, blob)
        value = data["score"]["value"]
        assert 0 <= value <= 100
        assert value == max(0, min(100, data["score"]["awarded"] - data["score"]["deducted"]))


def test_score_clamps_at_zero(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "src/notes.py", "TODO\n" * 50 + 'password = "hunter2hunter2"\n')
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    data = analyze(repo, bad)
    assert data["score"]["raw"] < 0
    assert data["score"]["value"] == 0
    assert _score(build_report(repo, bad)) == 0


def test_top_5_next_steps_follow_findings(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "config/app.env", 'password = "hunter2hunter2"\n')
    text = build_report(repo)
    steps = [line for line in text.splitlines() if line[:3] in {f"{n}. " for n in range(1, 6)}]
    assert len(steps) == 5
    assert steps[0].startswith("1. 1 mögliche Geheimnis-Treffer im Produktionscode")
    assert "config/app.env" in steps[0]
    assert "hunter2hunter2" not in "\n".join(steps)
    assert "_Top 5 next steps_" not in text

    clean = build_report(_perfect(tmp_path))
    clean_steps = [line for line in clean.splitlines() if line[:3] in {f"{n}. " for n in range(1, 6)}]
    assert len(clean_steps) == 5
    assert any("Pytest-Ergebnisse mitliefern" in line for line in clean_steps)


def test_skips_vendor_venv_git_build_and_symlinks(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "src/app.py", "x = 1\n")
    _write(repo, "node_modules/pkg/index.js", "TODO\n")
    _write(repo, ".venv/lib/test_hidden.py", "def test_hidden():\n    pass\n")
    _write(repo, ".git/config", "TODO\n")
    _write(repo, "env/lib/x.py", "TODO\n")
    _write(repo, "build/out.py", "FIXME\n")
    outside = tmp_path / "outside.txt"
    outside.write_text("TODO secret-shaped\n", encoding="utf-8")
    (repo / "link.txt").symlink_to(outside)
    data = analyze(repo)
    assert data["files"] == 1
    assert data["markers"]["total"] == 0
    assert data["test_functions"] == 0
    text = build_report(repo)
    assert "outside.txt" not in text
    assert "secret-shaped" not in text
    assert ".git" in text  # the skipped-directory list names the folder
    assert "node_modules" in text


def test_deterministic_output_and_no_local_path(tmp_path):
    repo = _perfect(tmp_path)
    first = build_report(repo)
    second = build_report(repo)
    assert first == second
    assert str(repo) not in first
    assert str(tmp_path) not in first
    for heading in HEADINGS:
        assert heading in first


def test_file_cap_and_read_cap(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    for name in ("a.txt", "b.txt", "c.txt"):
        _write(repo, name, "x\n")
    monkeypatch.setattr(report, "MAX_FILES", 2)
    data = analyze(repo)
    text = build_report(repo)
    assert data["files"] == 2
    assert data["scan_capped"] is True
    assert "Dateigrenze erreicht" in text

    monkeypatch.setattr(report, "MAX_FILES", 5000)
    monkeypatch.setattr(report, "MAX_FILE_READ_BYTES", 8)
    _write(repo, "big.txt", "TODO\n" * 20)
    partial = analyze(repo)
    assert partial["lines_partial_files"] >= 1
    assert "(Anfang)" in build_report(repo)


def test_does_not_execute_customer_code_or_open_sockets(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo, "danger.py", "raise SystemExit('customer-code-ran')\n")

    def _boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr(socket, "socket", _boom)
    text = build_report(repo)
    assert "customer-code-ran" not in text


def test_cli_out_stdout_and_missing_repo(tmp_path, capsys):
    repo = _repo(tmp_path)
    _write(repo, "README.md", "# Demo\n")
    out = tmp_path / "report.md"
    assert main([str(repo), "--out", str(out)]) == 0
    written = out.read_text(encoding="utf-8")
    assert written.startswith("# Repo Reality Check\n")
    assert "Score:" in written

    assert main([str(repo)]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("# Repo Reality Check\n")
    assert main([str(tmp_path / "missing")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_module_entrypoint(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "README.md", "# Demo\n")
    out = tmp_path / "report.md"
    proc = subprocess.run(
        [sys.executable, "-m", "courier_core.repo_reality_report", str(repo), "--out", str(out)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Score:" in out.read_text(encoding="utf-8")
    assert str(repo) not in out.read_text(encoding="utf-8")


def test_executive_summary_uses_measured_counts(tmp_path):
    repo = _perfect(tmp_path)
    data = analyze(repo)
    text = build_report(repo)
    assert data["summary_sentences"] == [
        "Der Checkout enthält 6 Dateien und 11 Zeilen.",
        "Statisch gezählt: 1 Testdatei, 1 Testfunktion und 0 Test-Hilfsdateien; die Tests wurden nicht ausgeführt.",
        "CI: 1 Konfiguration und 1 Job.",
        "Abhängigkeiten: 1 Manifest, 1 von 1 Eintrag exakt gepinnt oder per Lockfile gesperrt.",
        "Geheimnis-Risiko: 0 Treffer im Produktionscode, 0 in Tests, Fixtures, Beispielen oder Doku.",
        "Repo-Hygiene: LICENSE vorhanden, keine weiteren Auffälligkeiten.",
    ]
    assert [row["area"] for row in data["ampel"]] == [
        "Tests",
        "CI",
        "Abhängigkeiten",
        "Geheimnis-Risiko",
        "Repo-Hygiene",
    ]
    assert [row["light"] for row in data["ampel"]] == ["Gelb", "Grün", "Grün", "Grün", "Grün"]
    summary = text.split("## Kurzfassung", 1)[1].split("## Repositorygröße", 1)[0]
    sentences = [line for line in summary.splitlines() if line.endswith(".")]
    assert sentences == data["summary_sentences"]
    assert 3 <= len(sentences) <= 6
    assert "| Tests | Gelb |" in text
    assert "nicht ausgeführt" in text
    assert text.index("## Kurzfassung") < text.index("## Repositorygröße")

    empty = analyze(_repo(tmp_path))
    lights = {row["area"]: row["light"] for row in empty["ampel"]}
    assert lights == {
        "Tests": "Rot",
        "CI": "Rot",
        "Abhängigkeiten": "Rot",
        "Geheimnis-Risiko": "Grün",
        "Repo-Hygiene": "Rot",
    }


def test_secrets_split_production_and_fixture_score(tmp_path):
    repo = _perfect(tmp_path)
    value = "example-token-value"
    _write(repo, "src/settings.py", f'api_key = "{value}"\n')
    _write(repo, "tests/fixtures/sample.env", f'password = "{value}"\n')
    _write(repo, "docs/guide.md", f'secret = "{value}"\n')
    _write(repo, "README.md", f'token = "{value}"\n')
    data = analyze(repo)
    text = build_report(repo)
    assert value not in text
    assert value not in json.dumps(data)
    assert data["secrets"]["production_hits"] == 1
    assert data["secrets"]["production_rows"] == [{"path": "src/settings.py", "hits": 1, "bucket": "production"}]
    assert data["secrets"]["non_production_hits"] == 3
    assert [row["path"] for row in data["secrets"]["non_production_rows"]] == [
        "README.md",
        "docs/guide.md",
        "tests/fixtures/sample.env",
    ]
    secrets_row = next(row for row in data["score"]["components"] if row["id"] == "secrets")
    assert secrets_row["awarded"] == 0
    assert "Treffer im Produktionscode" in secrets_row["observation"]
    assert {row["light"] for row in data["ampel"] if row["area"] == "Geheimnis-Risiko"} == {"Rot"}

    fixture_only = _perfect(tmp_path, "fixture-only")
    _write(fixture_only, "tests/fixtures/sample.env", f'password = "{value}"\n')
    fixture_data = analyze(fixture_only)
    fixture_row = next(row for row in fixture_data["score"]["components"] if row["id"] == "secrets")
    assert fixture_data["secrets"]["production_hits"] == 0
    assert fixture_data["secrets"]["non_production_hits"] == 1
    assert fixture_row["awarded"] == 8
    assert fixture_data["score"]["value"] == 98
    fixture_text = build_report(fixture_only)
    assert "### Tests, Fixtures, Beispiele und Doku" in fixture_text
    assert "kosten 2 Punkte" in fixture_text
    assert value not in fixture_text
    lights = {row["area"]: row["light"] for row in fixture_data["ampel"]}
    assert lights["Geheimnis-Risiko"] == "Gelb"


def test_helpers_and_stray_tests_are_separate(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "tests/test_app.py", "def test_one():\n    pass\n")
    _write(repo, "tests/test_empty.py", "# placeholder\n")
    _write(repo, "tests/conftest.py", "import os\n")
    _write(repo, "tests/_fakes.py", "class Fake:\n    pass\n")
    _write(repo, "tests/builders.py", "def build():\n    return 1\n")
    _write(repo, "tests/unit/conftest.py", "x = 1\n")
    _write(repo, "src/app.py", "def test_not_counted():\n    pass\n")
    _write(repo, "src/builders.py", "def build():\n    return 1\n")
    _write(repo, "test_scratch.py", "def test_root():\n    pass\n")
    _write(repo, "scripts/test_tool.py", "def test_script():\n    pass\n")
    _write(repo, "scripts/check.py", "def test_not_named():\n    pass\n")
    _write(repo, "web/demo.test.js", "test('a', () => {})\n")
    data = analyze(repo)
    assert data["test_file_rows"] == [
        {"path": "scripts/test_tool.py", "functions": 1},
        {"path": "test_scratch.py", "functions": 1},
        {"path": "tests/test_app.py", "functions": 1},
        {"path": "tests/test_empty.py", "functions": 0},
        {"path": "web/demo.test.js", "functions": 1},
    ]
    assert data["test_functions"] == 4
    assert data["test_helpers"] == [
        "tests/_fakes.py",
        "tests/builders.py",
        "tests/conftest.py",
        "tests/unit/conftest.py",
    ]
    assert data["hygiene"]["stray_tests"] == [
        {"path": "scripts/test_tool.py", "functions": 1},
        {"path": "test_scratch.py", "functions": 1},
    ]
    text = build_report(repo)
    assert "### Test-Hilfsdateien" in text
    assert "tests/conftest.py" in text
    assert "src/builders.py" not in text.split("### Test-Hilfsdateien", 1)[1].split("## ", 1)[0]
    assert "src/app.py" not in text.split("## Testdateien", 1)[1].split("## Testergebnisse", 1)[0]
    assert "- Testdateien außerhalb eines Testordners: 2" in text


def test_hygiene_findings_use_sizes_and_keep_missing_license(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "scratch/note.txt", "hi\n")
    _write(repo, "Attic/old.txt", "x\n")
    (repo / "payload.zip").write_bytes(b"\0" * (1024 * 1024 + 1))
    (repo / "small.zip").write_bytes(b"PK\x03\x04")
    (repo / "exact.zip").write_bytes(b"\0" * (1024 * 1024))
    (repo / "data").mkdir()
    (repo / "data" / "events.jsonl").write_bytes(b"{" + b"a" * (1024 * 1024))
    (repo / "data" / "tiny.json").write_text("{}\n", encoding="utf-8")
    data = analyze(repo)
    assert data["project_files"]["license"]["present"] is False
    assert data["hygiene"]["large_binaries"] == [{"path": "payload.zip", "bytes": 1048577}]
    assert data["hygiene"]["scratch_dirs"] == ["Attic", "scratch"]
    assert data["hygiene"]["large_json"] == [{"path": "data/events.jsonl", "bytes": 1048577}]
    assert "binaries" in data["hygiene"]["flags"]
    assert "license" in data["hygiene"]["flags"]
    text = build_report(repo)
    assert "- LICENSE: fehlt" in text
    assert "payload.zip" in text
    assert "1048577" in text
    assert "small.zip" not in text.split("## Repo-Hygiene", 1)[1].split("## Realitätswert", 1)[0]
    assert "exact.zip" not in text.split("## Repo-Hygiene", 1)[1].split("## Realitätswert", 1)[0]
    hygiene_light = next(row["light"] for row in data["ampel"] if row["area"] == "Repo-Hygiene")
    assert hygiene_light == "Rot"
    steps = [line for line in text.splitlines() if line[:2] in {f"{n}." for n in range(1, 6)}]
    assert any("payload.zip" in line and "1,0 MB" in line for line in steps)
    assert any("events.jsonl" in line and "1,0 MB" in line for line in steps)
    assert all("LICENSE" not in line for line in steps)


def test_languages_collapse_other_extensions(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "src/app.py", "x = 1\n")
    _write(repo, "Makefile", "all:\n")
    _write(repo, "a.xyz", "yy\n")
    _write(repo, "b.qqq", "z\n")
    _write(repo, "c.xyz", "www\n")
    data = analyze(repo)
    assert data["languages"] == [
        {"name": "Python", "files": 1, "lines": 1},
        {"name": "ohne Endung", "files": 1, "lines": 1},
        {"name": "Sonstige (2)", "files": 3, "lines": 3},
    ]
    text = build_report(repo)
    assert "Other (" not in text
    assert "| ohne Endung | 1 | 1 |" in text
    assert "| Sonstige (2) | 3 | 3 |" in text
    assert text.index("| Python |") < text.index("| ohne Endung |") < text.index("| Sonstige (2) |")


def test_same_tree_stays_deterministic_with_hygiene(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "tests/fixtures/sample.env", 'password = "example-token-value"\n')
    _write(repo, "notes.xyz", "alpha\n")
    _write(repo, "more.qqq", "beta\n")
    _write(repo, "scratch/a.txt", "c\n")
    first = build_report(repo)
    second = build_report(repo)
    assert first == second


def test_customer_doc_has_no_secret_material():
    doc = (ROOT / "docs" / "REPO_REALITY_CHECK.md").read_text(encoding="utf-8")
    assert "python -m courier_core.repo_reality_report" in doc
    assert "Sample report" in doc
    assert "Repositorygröße" in doc
    for banned in ("ghp_", "AKIA", "PRIVATE KEY", "hunter2", "/home/", "/Users/", "ubuntu"):
        assert banned not in doc


# --- Regression tests for the 2026-10-08 sample review (express, ripgrep, cobra, itsdangerous) ---


def test_js_tests_in_test_dirs_count_without_test_suffix(tmp_path):
    """Mocha style: test/app.js with it() calls counts; support and fixture files do not."""
    repo = _repo(tmp_path)
    _write(repo, "test/app.router.js", "describe('r', function () {\n  it('routes', function () {})\n  it.skip('later', function () {})\n})\n")
    _write(repo, "test/acceptance/auth.js", "it('logs in', () => {})\n")
    _write(repo, "tests/unit/math.ts", "test('adds', () => {})\n")
    _write(repo, "__tests__/ui.jsx", "test.each([1])('renders', () => {})\n")
    _write(repo, "test/support/utils.js", "module.exports = function helper() {}\n")
    _write(repo, "test/fixtures/app.js", "it('fixture, not a test', () => {})\n")
    _write(repo, "lib/router.js", "it('not under a test dir', () => {})\n")
    _write(repo, "web/demo.spec.ts", "it('spec', () => {})\n")
    data = analyze(repo)
    assert [row["path"] for row in data["test_file_rows"]] == [
        "__tests__/ui.jsx",
        "test/acceptance/auth.js",
        "test/app.router.js",
        "tests/unit/math.ts",
        "web/demo.spec.ts",
    ]
    assert data["test_functions"] == 6
    assert data["hygiene"]["stray_tests"] == []


def test_rust_tests_dir_and_test_attributes(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "Cargo.toml", "[package]\nname = \"demo\"\n")
    _write(repo, "tests/feature.rs", "rgtest!(f1, |dir, cmd| {});\n")
    _write(repo, "tests/misc.rs", "#[test]\nfn one() {}\n\n#[tokio::test]\nasync fn two() {}\n")
    _write(repo, "crates/core/src/lib.rs", "pub fn x() {}\n#[cfg(test)]\nmod tests {\n    #[test]\n    fn unit() {}\n}\n")
    _write(repo, "crates/core/src/cfg_only.rs", "#[cfg(test)]\nmod tests {}\n")
    _write(repo, "src/main.rs", "fn main() {}\n")
    data = analyze(repo)
    assert [row["path"] for row in data["test_file_rows"]] == [
        "crates/core/src/cfg_only.rs",
        "crates/core/src/lib.rs",
        "tests/feature.rs",
        "tests/misc.rs",
    ]
    assert data["test_functions"] == 3
    lights = {row["area"]: row["light"] for row in data["ampel"]}
    assert lights["Tests"] == "Gelb"
    assert not any("Testdatei anlegen" in step for step in data["next_steps"])


def test_go_tests_next_to_code_are_not_stray(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "go.mod", "module demo\n\ngo 1.22\n")
    _write(repo, "args_test.go", "func TestArgs(t *testing.T) {}\n")
    _write(repo, "cmd/run_test.go", "func TestRun(t *testing.T) {}\n")
    _write(repo, "test_root.py", "def test_root():\n    pass\n")
    data = analyze(repo)
    assert {row["path"] for row in data["test_file_rows"]} == {"args_test.go", "cmd/run_test.go", "test_root.py"}
    assert data["hygiene"]["stray_tests"] == [{"path": "test_root.py", "functions": 1}]
    assert "stray" in data["hygiene"]["flags"]
    text = build_report(repo)
    assert "args_test.go" not in text.split("## Repo-Hygiene", 1)[1].split("## Realitätswert", 1)[0]


def test_examples_docs_fixtures_and_testdata_are_not_production_secrets(tmp_path):
    repo = _perfect(tmp_path)
    value = "demo-cookie-secret-value"
    for rel in (
        "examples/auth/index.js",
        "example/app.py",
        "docs/setup.md",
        "test/fixtures/keys.js",
        "pkg/testdata/conf.yaml",
        "fixtures/seed.env",
    ):
        _write(repo, rel, f'secret: "{value}"\n')
    data = analyze(repo)
    assert data["secrets"]["production_hits"] == 0
    assert data["secrets"]["non_production_hits"] == 6
    lights = {row["area"]: row["light"] for row in data["ampel"]}
    assert lights["Geheimnis-Risiko"] == "Gelb"
    text = build_report(repo)
    assert value not in text
    assert "examples/auth/index.js" in text.split("### Tests, Fixtures, Beispiele und Doku", 1)[1]
    _write(repo, "src/server.js", f'secret: "{value}"\n')
    assert analyze(repo)["secrets"]["production_hits"] == 1


def test_github_actions_expressions_are_not_secrets(tmp_path):
    repo = _perfect(tmp_path)
    _write(
        repo,
        ".github/workflows/labeler.yml",
        'jobs:\n  triage:\n    steps:\n    - uses: actions/labeler@v5\n      with:\n'
        '        repo-token: "${{ github.token }}"\n        token: "${{ secrets.DEPLOY_TOKEN }}"\n',
    )
    data = analyze(repo)
    assert data["secrets"]["hits"] == 0
    _write(repo, "config/app.yml", 'token: "real-looking-token-value"\n')
    assert analyze(repo)["secrets"]["production_hits"] == 1


@pytest.mark.parametrize(
    ("lockfile", "manifest", "manifest_text"),
    [
        ("Cargo.lock", "crates/core/Cargo.toml", '[dependencies]\nserde = "1.0"\nregex = "1"\n'),
        ("package-lock.json", "package.json", '{"dependencies": {"a": "^1.0.0", "b": "~2.0.0"}}'),
        ("yarn.lock", "package.json", '{"dependencies": {"a": "^1.0.0", "b": "~2.0.0"}}'),
        ("pnpm-lock.yaml", "package.json", '{"dependencies": {"a": "^1.0.0", "b": "~2.0.0"}}'),
        ("poetry.lock", "pyproject.toml", '[tool.poetry.dependencies]\npython = "^3.10"\nflask = "^2.0"\nrequests = "^2"\n'),
        ("uv.lock", "pyproject.toml", '[project]\nname = "d"\ndependencies = [\n  "flask>=2",\n  "requests",\n]\n'),
        ("go.sum", "go.mod", "module m\n\nrequire (\n\tx/y v1.2.3\n\tz/w latest\n)\n"),
        ("Gemfile.lock", "Gemfile", "gem 'rails', '~> 7.0'\ngem 'puma'\n"),
    ],
)
def test_lockfiles_count_as_pinned(tmp_path, lockfile, manifest, manifest_text):
    repo = _repo(tmp_path)
    _write(repo, manifest, manifest_text)
    unlocked = analyze(repo)["dependencies"]
    assert unlocked["unpinned"] >= 1
    _write(repo, lockfile, "# lock\n")
    deps = analyze(repo)["dependencies"]
    row = next(item for item in deps["rows"] if item["path"] == manifest)
    assert row["unpinned"] == 0
    assert row["locked_by"] == lockfile
    assert deps["unpinned"] == 0
    assert deps["locked_manifests"] == 1
    lights = {item["area"]: item["light"] for item in analyze(repo)["ampel"]}
    assert lights["Abhängigkeiten"] == "Grün"


def test_lockfile_in_other_folder_or_ecosystem_does_not_pin(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "web/package.json", '{"dependencies": {"a": "^1.0.0"}}')
    _write(repo, "api/package-lock.json", "{}\n")
    _write(repo, "requirements.txt", "flask\n")
    _write(repo, "uv.lock", "# lock\n")
    deps = analyze(repo)["dependencies"]
    assert deps["unpinned"] == 2
    assert deps["locked_manifests"] == 0


def test_locked_manifest_without_entries_gets_full_pin_points(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "pyproject.toml", '[project]\nname = "d"\nversion = "1"\n')
    _write(repo, "uv.lock", "# lock\n")
    data = analyze(repo)
    pin = next(row for row in data["score"]["components"] if row["id"] == "pinning")
    assert pin["awarded"] == pin["weight"]
    assert "Lockfile" in pin["observation"]


def test_next_steps_are_language_aware_and_never_keep_zero_baseline(tmp_path):
    go_repo = _repo(tmp_path)
    _write(go_repo, "README.md", "# Demo\n")
    _write(go_repo, "LICENSE", "x\n")
    _write(go_repo, ".gitignore", "bin/\n")
    _write(go_repo, "go.mod", "module m\n\nrequire x/y v1.2.3\n")
    _write(go_repo, "go.sum", "x/y v1.2.3 h1:abc\n")
    _write(go_repo, "main_test.go", "func TestMain(t *testing.T) {}\n")
    _write(go_repo, ".github/workflows/ci.yml", "jobs:\n  test:\n    runs-on: ubuntu-latest\n")
    steps = analyze(go_repo)["next_steps"]
    assert len(steps) == 5
    assert not any("Pytest" in step or "pytest" in step for step in steps)
    assert any(step.startswith("Testbasis halten: 1 Testdatei") for step in steps)

    no_tests = tmp_path / "no-tests"
    no_tests.mkdir()
    _write(no_tests, "index.js", "module.exports = 1\n")
    steps = analyze(no_tests)["next_steps"]
    assert not any("Testbasis" in step for step in steps)
    assert not any("Pytest" in step for step in steps)
    assert any("Mindestens eine Testdatei anlegen" in step for step in steps)

    java = tmp_path / "java"
    java.mkdir()
    _write(java, "src/main/java/App.java", "class App {}\n")
    steps = analyze(java)["next_steps"]
    assert any("Keine Testdateien erkannt" in step and "Java" in step for step in steps)

    py = analyze(_perfect(tmp_path, "py"))["next_steps"]
    assert any("Pytest-Ergebnisse mitliefern" in step for step in py)


def test_report_text_is_german(tmp_path):
    repo = _perfect(tmp_path)
    (repo / "big.zip").write_bytes(b"\0" * (1024 * 1024 + 1))
    text = build_report(repo)
    for english in (
        "Read-only scan",
        "Source:",
        "Tarball sha256",
        "- Files:",
        "- Lines:",
        "Test files",
        "| Language |",
        "| File |",
        "Component",
        "Formula:",
        "clamped",
        "awarded",
        "Top 5 next steps",
        "Max files",
        "Symlinks are skipped",
        "Keep the measured test baseline",
        "fehlende LICENSE",
        "1048576 Bytes",
        "verstreute",
        "Executive summary",
    ):
        assert english not in text, english
    assert "Berechnung:" in text
    assert "Repo-Hygiene: LICENSE vorhanden; 1 Binär- oder Archivdatei über 1 MB." in text
    assert "Höchstens 5000 Dateien; je Datei werden höchstens 256 KB gelesen." in text


def _perfect(tmp_path: Path, name: str = "perfect") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "LICENSE", "synthetic\n")
    _write(repo, ".gitignore", "venv/\n")
    _write(repo, "tests/test_app.py", "def test_ok():\n    pass\n")
    _write(
        repo,
        ".github/workflows/ci.yml",
        "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
    )
    _write(repo, "requirements.txt", "flask==1.0.0\n")
    return repo
