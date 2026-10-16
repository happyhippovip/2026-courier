"""Flaky, environment, and timeout results are not a verified pass.

Catalog 2176–2200. The classifier is pure: same report in, same verdict out.
"""

import json

from courier_core.test_report import (
    ENVIRONMENT,
    FLAKY,
    PRODUCT_FAIL,
    TIMEOUT,
    UNKNOWN,
    VERIFIED_PASS,
    classify_log,
)


def _classes(text, returncode=0):
    verdict = classify_log(text, returncode)
    return verdict, set(verdict.to_record()["classes"])


def test_stable_pass_summary_is_verified():
    verdict, classes = _classes("======= 1 passed in 0.01s =======\n", 0)
    assert verdict.verified is True
    assert classes == {VERIFIED_PASS}


def test_same_node_pass_and_fail_is_flaky_not_verified():
    log = "tests/test_a.py::test_one FAILED\ntests/test_a.py::test_one PASSED\n"
    verdict, classes = _classes(log, 1)
    assert verdict.verified is False
    assert FLAKY in classes
    assert VERIFIED_PASS not in classes
    assert PRODUCT_FAIL not in classes


def test_distinct_nodes_are_a_product_failure_not_a_flake():
    log = "tests/test_a.py::test_ok PASSED\ntests/test_a.py::test_bad FAILED\n"
    verdict, classes = _classes(log, 1)
    assert verdict.verified is False
    assert PRODUCT_FAIL in classes
    assert FLAKY not in classes


def test_explicit_flaky_marker_is_not_a_pass():
    verdict, classes = _classes("======= 1 passed, 1 flaky in 0.2s =======\nRERUN tests/test_a.py::test_one\n", 0)
    assert verdict.verified is False
    assert FLAKY in classes


def test_platform_skip_is_environment_not_a_pass():
    log = "tests/test_win.py::test_guard SKIPPED Windows only\n======= 1 skipped in 0.01s =======\n"
    verdict, classes = _classes(log, 0)
    assert verdict.verified is False
    assert classes == {ENVIRONMENT}


def test_import_error_is_environment_not_a_product_failure():
    log = "E   ModuleNotFoundError: No module named 'requests'\n======= 1 error in 0.2s =======\n"
    verdict, classes = _classes(log, 1)
    assert verdict.verified is False
    assert ENVIRONMENT in classes
    assert PRODUCT_FAIL not in classes
    assert TIMEOUT not in classes


def test_passed_with_skips_is_not_verified():
    verdict, classes = _classes("======= 3 passed, 1 skipped in 0.2s =======\n", 0)
    assert verdict.verified is False
    assert ENVIRONMENT in classes
    assert VERIFIED_PASS not in classes


def test_timeout_is_not_a_product_failure_or_a_pass():
    log = "E       Failed: Timeout >5.0s\nTimeoutExpired\n======= 1 failed in 5.1s =======\n"
    verdict, classes = _classes(log, 1)
    assert verdict.verified is False
    assert TIMEOUT in classes
    assert PRODUCT_FAIL not in classes
    assert VERIFIED_PASS not in classes


def test_timeout_stays_visible_beside_an_assertion():
    log = "E       AssertionError: 1 != 2\nE       Failed: Timeout >5.0s\n"
    verdict, classes = _classes(log, 1)
    assert verdict.verified is False
    assert TIMEOUT in classes and PRODUCT_FAIL in classes


def test_agent_prose_is_not_a_receipt():
    prose = "GitHub receipt VERIFIED. The model says 1 passed and the suite is clean."
    verdict, classes = _classes(prose, 0)
    assert verdict.verified is False
    assert classes == {UNKNOWN}


def test_nonzero_exit_with_only_a_pass_count_is_not_verified():
    verdict, classes = _classes("======= 1 passed in 0.01s =======\n", 1)
    assert verdict.verified is False
    assert VERIFIED_PASS not in classes


def test_garbage_never_raises_and_never_verifies():
    for text, code in ((None, 0), ("", 0), (object(), None), ("@@@", "nope")):
        verdict = classify_log(text, code)
        assert verdict.verified is False
        assert UNKNOWN in verdict.to_record()["classes"]


def test_secret_in_the_log_does_not_enter_the_verdict():
    secret = "ghp_" + "a" * 36
    log = f"E   ModuleNotFoundError: No module named 'x'\ntoken='{secret}'\n"
    verdict = classify_log(log, 1)
    encoded = verdict.to_json()
    assert secret not in encoded
    assert verdict.verified is False


def test_repeat_and_reload_do_not_promote(tmp_path):
    log = "tests/test_a.py::test_one TIMEOUT\n"
    first = classify_log(log, 1)
    second = classify_log(log, 1)
    assert first.to_json() == second.to_json()
    path = tmp_path / "verdict.json"
    path.write_text(first.to_json(), encoding="utf-8")
    loaded = type(first).from_json(path.read_text(encoding="utf-8"))
    assert loaded.to_json() == first.to_json()
    assert loaded.verified is False
    assert TIMEOUT in loaded.to_record()["classes"]


def test_tampered_verified_flag_fails_closed():
    original = classify_log("E       Failed: Timeout >5.0s\n", 1)
    record = original.to_record()
    record["verified"] = True
    loaded = type(original).from_json(json.dumps(record))
    assert loaded.verified is False
    assert TIMEOUT in loaded.to_record()["classes"]


def test_unknown_class_in_a_stored_record_is_not_a_pass():
    payload = {
        "classes": ["VERIFIED_PASS", "MADE_UP"],
        "verified": True,
        "cases": [{"nodeid": "<suite>", "klass": "VERIFIED_PASS"}],
    }
    loaded = classify_log("======= 1 passed in 0.01s =======\n", 0).from_json(json.dumps(payload))
    assert loaded.verified is False
    assert loaded.to_record()["classes"] == [UNKNOWN]
