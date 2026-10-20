import json
from pathlib import Path

from tests.conftest import windows_collect_skips

ROOT = Path(__file__).resolve().parents[1]
KNOWN_PATH = ROOT / ".github" / "ci" / "known_failures.json"
KNOWN = json.loads(KNOWN_PATH.read_text(encoding="utf-8")) if KNOWN_PATH.exists() else {"Windows": {"failing": [], "flaky": []}}


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
    assert windows_collect_skips("tests/test_mac_worker_future.py::test_new", KNOWN) is False


def test_windows_skip_still_hides_unscoped_platform_tests():
    assert windows_collect_skips("tests/test_run_physical_demo.py::test_x", KNOWN) is True
    assert windows_collect_skips("tests/test_muse_supervisor.py::test_not_in_baseline", KNOWN) is True
    assert windows_collect_skips("tests/test_server_integration_contract.py::test_ok", KNOWN) is False
