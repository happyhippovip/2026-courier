"""Fail-closed regression gate: a skipped known failure is not a pass,
and FLAKY requires both a pass and a fail of the same node.
"""
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / ".github" / "ci" / "check_regressions.py"
GOLDEN = "tests/golden/test_gate_fixture.py::test_holds"
KNOWN_FAIL = "tests/test_example.py::test_negative_fails_closed"
FLAKY = "tests/test_muse_supervisor.py::test_stop_prevents_restart"
NEW = "tests/test_example.py::test_brand_new"
SCOPED = "tests/test_mac_worker_contract.py::test_success_is_bound_and_accepted"


def _gate():
    spec = importlib.util.spec_from_file_location("check_regressions_fail_closed", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_gate(tmp_path, outcomes, known, platform="Linux"):
    outcomes_path = tmp_path / "outcomes.json"
    known_path = tmp_path / "known.json"
    outcomes_path.write_text(json.dumps({"exitstatus": 1, "outcomes": outcomes}), encoding="utf-8")
    known_path.write_text(json.dumps({platform: known}), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _gate().main([
            "--outcomes", str(outcomes_path),
            "--known", str(known_path),
            "--platform", platform,
        ])
    return rc, buf.getvalue()


def test_skipped_known_failure_is_not_a_gate_pass(tmp_path):
    rc, text = run_gate(
        tmp_path,
        {GOLDEN: "passed", KNOWN_FAIL: "skipped"},
        {"failing": [KNOWN_FAIL], "flaky": []},
    )
    assert rc == 1
    assert "GATE PASS" not in text
    assert "KNOWN FAILURE SKIPPED" in text
    assert KNOWN_FAIL in text


def test_single_failure_on_the_flaky_list_fails_the_gate(tmp_path):
    rc, text = run_gate(
        tmp_path,
        {GOLDEN: "passed", FLAKY: "failed"},
        {"failing": [], "flaky": [FLAKY]},
    )
    assert rc == 1
    assert "GATE PASS" not in text
    assert "FLAKY " not in text
    assert FLAKY in text


def test_flaky_only_when_the_same_node_passed_and_failed(tmp_path):
    rc, text = run_gate(
        tmp_path,
        {GOLDEN: "passed", FLAKY: ["passed", "failed"]},
        {"failing": [], "flaky": [FLAKY]},
    )
    assert rc == 0
    assert "FLAKY " in text
    assert FLAKY in text
    assert "GATE PASS" in text


def test_new_failure_still_fails_the_gate(tmp_path):
    rc, text = run_gate(
        tmp_path,
        {GOLDEN: "passed", NEW: "failed"},
        {"failing": [], "flaky": []},
    )
    assert rc == 1
    assert "NEW FAILURE" in text
    assert NEW in text


def test_known_failure_that_actually_failed_stays_tolerated(tmp_path):
    rc, text = run_gate(
        tmp_path,
        {GOLDEN: "passed", KNOWN_FAIL: "failed"},
        {"failing": [KNOWN_FAIL], "flaky": []},
    )
    assert rc == 0
    assert "GATE PASS" in text
    assert "KNOWN FAILURE SKIPPED" not in text


def test_out_of_scope_failure_does_not_fail_the_gate(tmp_path):
    rc, text = run_gate(
        tmp_path,
        {GOLDEN: "passed", SCOPED: "failed"},
        {
            "failing": [],
            "flaky": [],
            "out_of_scope": {"patterns": ["tests/test_mac_*"], "reason": "POSIX-only"},
        },
        platform="Windows",
    )
    assert rc == 0
    assert "OUT OF SCOPE" in text
    assert SCOPED in text


def test_skipped_known_failure_still_fails_when_other_tests_pass(tmp_path):
    rc, text = run_gate(
        tmp_path,
        {GOLDEN: "passed", KNOWN_FAIL: "skipped", NEW: "passed"},
        {"failing": [KNOWN_FAIL], "flaky": [FLAKY]},
    )
    assert rc == 1
    assert "KNOWN FAILURE SKIPPED" in text
    assert "GATE PASS" not in text
