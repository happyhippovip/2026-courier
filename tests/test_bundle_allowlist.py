"""The customer runtime ships by explicit allowlist; everything else is refused."""
import json

import pytest

from scripts import bundle_allowlist_check as checker
from scripts.bundle_allowlist_check import check, load_allowlist, manifest_from_dir, manifest_paths, pattern_to_regex

RUNTIME = ["Courier.exe", "install.ps1", "uninstall.ps1", "python/python.exe", "python/Lib/site-packages/x/README.md",
           "courier_core/serve.py", "courier_worker/host.py", "courier_hub/static/app.js", "adapters/synthetic.py"]


@pytest.fixture(scope="module")
def allowlist():
    return load_allowlist()


def reasons(report):
    return {violation["path"]: violation for violation in report["violations"]}


def test_a_clean_runtime_bundle_passes(allowlist):
    report = check(RUNTIME, allowlist)
    assert report == {"ok": True, "checked": len(RUNTIME), "violation_count": 0, "violations_by_class": {},
                      "violations": []}


def test_anything_not_named_is_refused(allowlist):
    report = check(RUNTIME + ["server/app.py", "dashboard/server.py", "studio/index.html", "static/x.css"], allowlist)
    assert not report["ok"] and report["violations_by_class"] == {"unlisted": 4}
    assert reasons(report)["server/app.py"]["reason"] == "not on the allowlist"


@pytest.mark.parametrize("path, expected_class", [
    ("scripts/consume_chief_command.py", "fleet-tooling"),
    ("ops/ai/packets/handoff.md", "fleet-tooling"),
    (".github/workflows/ci.yml", "fleet-tooling"),
    ("memory/CONFIDENTIAL_STRATEGY.md", "internal-strategy"),
    ("docs/v1/INTEGRATION_LOG.md", "internal-strategy"),
    ("CHIEF_BRAIN_STATE.md", "internal-strategy"),
    ("tests/test_x.py", "test-material"),
    ("acceptance/registry.yaml", "test-material"),
    ("runtime/central_state.json", "runtime-state"),
    ("events/chief-brain/memories.json", "runtime-state"),
    ("config/providers.json", "internal-config"),
    ("scripts/provider_hub/slots.json", "fleet-tooling"),
    ("courier_worker/slots.json", "internal-config"),
    ("agent_handoff_ledger.json", "internal-config"),
])
def test_fleet_strategy_state_and_config_never_ship(allowlist, path, expected_class):
    report = check([path], allowlist)
    assert not report["ok"] and report["violations"][0]["class"] == expected_class


@pytest.mark.parametrize("path", ["courier_core/.env", "python/.env.local", "courier_worker/run/controller.token",
                                  "courier_hub/auth.json", "adapters/credentials-prod.json", "python/.git/config"])
def test_deny_wins_over_a_broad_allow(allowlist, path):
    report = check([path], allowlist)
    assert not report["ok"] and report["violations"][0]["reason"].startswith("denied by")


def test_root_only_patterns_do_not_reach_into_allowed_folders(allowlist):
    assert check(["python/Lib/site-packages/x/README.md"], allowlist)["ok"]
    assert not check(["README.md"], allowlist)["ok"]
    assert pattern_to_regex("*.md").match("notes.md") and not pattern_to_regex("*.md").match("a/notes.md")
    assert pattern_to_regex("**/.env").match(".env") and pattern_to_regex("**/.env").match("a/b/.env")


@pytest.mark.parametrize("path", ["../outside.txt", "courier_core/../../x", "/etc/passwd", "C:\\Windows\\x.dll",
                                  "c:/Users/x", "./Courier.exe", ""])
def test_paths_that_leave_the_bundle_are_refused(allowlist, path):
    report = check([path], allowlist)
    assert not report["ok"] and report["violations"][0]["class"] == "unsafe-path"


def test_matching_ignores_case_and_backslashes(allowlist):
    assert check(["COURIER_CORE\\Serve.py", "courier.EXE"], allowlist)["ok"]
    assert reasons(check(["Scripts\\run_physical.py"], allowlist))["Scripts/run_physical.py"]["class"] == "fleet-tooling"


def test_every_violation_is_reported_and_an_empty_manifest_fails(allowlist):
    report = check(["scripts/a.py", "server/app.py", "courier_core/serve.py", "memory/x.md"], allowlist)
    assert report["violation_count"] == 3 and report["checked"] == 4
    empty = check([], allowlist)
    assert not empty["ok"] and empty["violations"][0]["reason"] == "empty manifest"


def test_manifest_shapes(tmp_path):
    assert manifest_paths(["a/b.py"]) == ["a/b.py"]
    assert manifest_paths([{"path": "a\\b.py", "sha256": "x"}]) == ["a/b.py"]
    assert manifest_paths({"files": [{"path": "a/b.py"}]}) == ["a/b.py"]
    listing = tmp_path / "files.txt"
    listing.write_text("Courier.exe\n\npython/python.exe\n", encoding="utf-8")
    assert checker.read_manifest(listing) == ["Courier.exe", "python/python.exe"]


def test_directory_scan_writes_a_manifest_and_sets_the_exit_code(tmp_path, capsys):
    bundle = tmp_path / "bundle"
    (bundle / "courier_core").mkdir(parents=True)
    (bundle / "courier_core" / "serve.py").write_text("x = 1\n", encoding="utf-8")
    (bundle / "Courier.exe").write_bytes(b"MZ")
    manifest = manifest_from_dir(bundle)
    assert [entry["path"] for entry in manifest["files"]] == ["Courier.exe", "courier_core/serve.py"]
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])
    out = tmp_path / "manifest.json"
    assert checker.main(["--from-dir", str(bundle), "--write-manifest", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == manifest

    (bundle / "scripts").mkdir()
    (bundle / "scripts" / "courier_github_dispatcher.py").write_text("", encoding="utf-8")
    capsys.readouterr()
    assert checker.main(["--from-dir", str(bundle)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["violations_by_class"] == {"fleet-tooling": 1}


def test_an_allowlist_without_allow_patterns_is_refused(tmp_path):
    broken = tmp_path / "allow.yaml"
    broken.write_text(json.dumps({"allow": [], "deny": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_allowlist(broken)
