import json
from pathlib import Path

from tests.conftest import windows_collect_skips

KNOWN = json.loads(Path(".github/ci/known_failures.json").read_text(encoding="utf-8"))


def test_windows_known_baseline_stays_in_the_outcomes_artifact():
    """Known Windows failures and the Mac scope must be executed, not skipped.

    The outcomes artifact is the CI record. Skipping a node that the baseline
    still lists, or that Windows out_of_scope says must still run, drops it
    from that record.
    """
    windows = KNOWN["Windows"]
    for node in windows["failing"] + windows["flaky"]:
        assert windows_collect_skips(node, KNOWN) is False
    assert windows_collect_skips("tests/test_mac_future.py::test_new", KNOWN) is False


def test_windows_skip_still_hides_unscoped_platform_tests():
    assert windows_collect_skips("tests/test_run_physical_demo.py::test_x", KNOWN) is True
    assert windows_collect_skips("tests/test_server_integration_contract.py::test_ok", KNOWN) is False
