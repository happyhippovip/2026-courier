"""Port the a58ff1f3 fail-closed proof; never launch a live acceptance server."""
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/acceptance/run_final_acceptance.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("acceptance_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthetic_acceptance_harness_refuses_default_execution(tmp_path):
    # No inherited credentials, endpoint or plugin settings.
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=tmp_path,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert completed.returncode == 2
    assert "SYNTHETIC_TEST_ONLY=YES" in completed.stdout
    assert "PHYSICAL_ACCEPTANCE=NO" in completed.stdout
    assert "TASKS_COMPLETED=" not in completed.stdout
    assert "CLEAN_IDLE=YES" not in completed.stdout
    assert not (tmp_path / "acceptance_state.json").exists()


@pytest.mark.parametrize("outcome", ["SKIP", "XFAIL", "XPASS", "ERROR", "NOT_RUN"])
def test_missing_or_nonpassing_case_cannot_produce_pass(outcome):
    h = load_harness()
    rows = [{"ID": "CV1-X", "TEST": ["tests/test_x.py::test_x"], "REQUIRED": True}]
    result = h.evaluate(rows, {"tests/test_x.py::test_x": outcome}, 0)
    assert result["CANNON_V1_REPO_STATUS"] != "PASS"
    assert result["MATRIX"][0]["STATUS"] != "PASS"


def test_failed_parameter_and_teardown_cannot_hide_behind_passed_parameter():
    h = load_harness()
    rows = [{"ID": "CV1-X", "TEST": ["tests/test_x.py::test_x"], "REQUIRED": True}]
    result = h.evaluate(rows, {"tests/test_x.py::test_x[a]": "PASS",
                               "tests/test_x.py::test_x[b]": "FAIL"}, 1)
    assert result["CANNON_V1_REPO_STATUS"] == "FAIL"
    assert result["MATRIX"][0]["STATUS"] == "FAIL"


def test_preview_and_physical_rows_never_imply_integrated_or_physical_pass():
    h = load_harness()
    rows = [
        {"ID": "preview", "TEST": ["tests/test_x.py::test_x"], "REQUIRED": False,
         "SCOPE": "PATCH_PREVIEW"},
        {"ID": "physical", "TEST": [], "REQUIRED": False,
         "PROOF_LEVEL": "PHYSICAL_WINDOWS_PROOF_REQUIRED"},
    ]
    result = h.evaluate(rows, {"tests/test_x.py::test_x": "PASS"}, 0)
    assert result["MATRIX"][0]["STATUS"] == "PREVIEW_PASS"
    assert result["MATRIX"][1]["STATUS"] == "REQUIRED"
    assert result["CANNON_V1_REPO_STATUS"] != "PASS"  # no required proofs
    assert result["PHYSICAL_ACCEPTANCE"] == "NO"


def test_test_process_failure_invalidates_all_green_rows():
    h = load_harness()
    rows = [{"ID": "CV1-X", "TEST": ["tests/test_x.py::test_x"], "REQUIRED": True}]
    result = h.evaluate(rows, {"tests/test_x.py::test_x": "PASS"}, 3)
    assert result["CANNON_V1_REPO_STATUS"] != "PASS"


def test_all_green_is_only_repo_pass_never_physical_acceptance():
    h = load_harness()
    rows = [{"ID": "CV1-X", "TEST": ["tests/test_x.py::test_x"], "REQUIRED": True}]
    result = h.evaluate(rows, {"tests/test_x.py::test_x": "PASS"}, 0)
    assert result["CANNON_V1_REPO_STATUS"] == "PASS"
    assert result["PHYSICAL_ACCEPTANCE"] == "NO"


def test_one_uncollected_selector_invalidates_other_passing_evidence():
    h = load_harness()
    rows = [{"ID": "CV1-X", "TEST": ["tests/test_x.py::test_x", "tests/test_x.py::test_y"], "REQUIRED": True}]
    result = h.evaluate(rows, {"tests/test_x.py::test_x": "PASS"}, 0)
    assert result["MATRIX"][0]["STATUS"] == "NOT_PROVEN"
    assert result["MATRIX"][0]["EVIDENCE"]["MISSING"] == ["tests/test_x.py::test_y"]


def test_teardown_error_overrides_passed_test_call():
    plugin = load_harness().Results()
    plugin.pytest_runtest_logreport(SimpleNamespace(nodeid="test", when="call", passed=True, failed=False, skipped=False))
    plugin.pytest_runtest_logreport(SimpleNamespace(nodeid="test", when="teardown", passed=False, failed=True, skipped=False))
    assert plugin.outcomes == {"test": "ERROR"}


def test_manifest_has_unique_required_invariants_and_physical_gates():
    import json
    spec = json.loads(load_harness().MANIFEST.read_text())
    rows = spec["MATRIX"]
    assert len({row["ID"] for row in rows}) == len(rows)
    for group in "ABCDEFGH":
        assert any(row["INVARIANT"] == group and row["REQUIRED"] for row in rows)
    for row in rows:
        assert {"ID", "SCENARIO", "EXPECTED", "TEST", "STATUS", "EVIDENCE", "PROOF_LEVEL"} <= row.keys()
        if row["REQUIRED"]:
            assert row["TEST"] and row["SCOPE"] != "PATCH_PREVIEW"
