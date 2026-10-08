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
    "## Repositorygröße",
    "## Testdateien",
    "## Testergebnisse",
    "## Offene Marker",
    "## CI-Konfiguration",
    "## Projektdateien",
    "## Abhängigkeiten",
    "## Größte Dateien",
    "## Hinweise auf Geheimnisse",
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
        ("no extension", 1, 1),
    ]
    assert "- Files: 4" in text
    assert "- Lines: 6" in text
    assert text.index("| Markdown |") < text.index("| Python |") < text.index("| Text |")
    assert "_Repository size_" in text


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
    assert "- Test files: 3" in text
    assert "- Test functions: 5" in text
    assert "test_skip.py" not in text
    assert "_Test files (static scan)_" in text


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
    assert "- Passed: 4" in text
    assert "- Failed: 1" in text
    assert "- Skipped: 2" in text
    assert "- Errors: 3" in text
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
    assert "could not be parsed" in text
    assert "- Passed: n/a" in text
    assert secret not in text
    assert "JSONDecodeError" not in text
    assert "Expecting" not in text
    assert data["score"]["value"] == 15

    weird = tmp_path / "list.json"
    weird.write_text("[1, 2]", encoding="utf-8")
    assert analyze(repo, weird)["pytest"]["status"] == "unexpected"
    assert "unexpected shape" in build_report(repo, weird)

    missing = analyze(repo, tmp_path / "missing.json")
    assert missing["pytest"]["status"] == "unreadable"
    assert "could not be read" in build_report(repo, tmp_path / "missing.json")

    empty = analyze(repo, None)
    assert empty["pytest"]["status"] == "not_supplied"
    assert "not supplied" in build_report(repo)


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
    assert "- Total: 4" in text
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
    assert "- Configs: 6" in text
    assert "- Jobs: 10" in text
    assert "_Continuous integration_" in text


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
    assert "- README: present (README.md)" in text
    assert "- LICENSE: absent" in text
    assert "- .gitignore: present (.gitignore)" in text


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
    assert by_path["package.json"]["pinned"] == 2
    assert by_path["package.json"]["unpinned"] == 1
    assert by_path["package-lock.json"]["note"] == "lockfile"
    assert "node_modules/pkg/package.json" not in by_path
    assert data["dependencies"]["unpinned"] == 4
    assert data["dependencies"]["pinned"] == 4
    assert data["dependencies"]["ratio_pinned"] == 4
    assert data["dependencies"]["ratio_unpinned"] == 4
    text = build_report(repo)
    assert "- Unpinned dependencies: 4" in text
    assert "- Pinned dependencies: 4" in text
    assert "- Manifests: 4" in text

    broken = tmp_path / "broken-json"
    broken.mkdir()
    _write(broken, "package.json", "{not json")
    parsed = analyze(broken)
    assert parsed["dependencies"]["rows"][0]["note"] == "could not parse"
    assert "could not parse" in build_report(broken)


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
    assert "| binary |" in text or "| binary |" in text.replace("binary", "binary")
    assert "binary" in text


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
    assert "Counts and file paths only" in text
    assert "in 1 file" in text
    assert "in 1 files" not in text


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
    assert steps[0].startswith("1. Remove secret-shaped strings")
    assert "hunter2hunter2" not in "\n".join(steps)
    assert "_Top 5 next steps_" in text

    clean = build_report(_perfect(tmp_path))
    clean_steps = [line for line in clean.splitlines() if line[:3] in {f"{n}. " for n in range(1, 6)}]
    assert len(clean_steps) == 5
    assert any("pytest JSON" in line for line in clean_steps)


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
    assert "File cap hit" in text

    monkeypatch.setattr(report, "MAX_FILES", 5000)
    monkeypatch.setattr(report, "MAX_FILE_READ_BYTES", 8)
    _write(repo, "big.txt", "TODO\n" * 20)
    partial = analyze(repo)
    assert partial["lines_partial_files"] >= 1
    assert "prefix" in build_report(repo)


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


def test_customer_doc_has_no_secret_material():
    doc = (ROOT / "docs" / "REPO_REALITY_CHECK.md").read_text(encoding="utf-8")
    assert "python -m courier_core.repo_reality_report" in doc
    assert "Sample report" in doc
    assert "Repositorygröße" in doc
    for banned in ("ghp_", "AKIA", "PRIVATE KEY", "hunter2", "/home/", "/Users/", "ubuntu"):
        assert banned not in doc


def _perfect(tmp_path: Path) -> Path:
    repo = tmp_path / "perfect"
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
