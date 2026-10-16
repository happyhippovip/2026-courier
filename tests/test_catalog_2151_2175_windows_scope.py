"""Catalog 2151-2160: Windows skip scope is the test file, not the function name.

A node id that merely contains 'muse' or 'mac_worker' in the test name stays
in the run. UNIX-only files stay skipped. No network and no spend.
"""
import inspect

from scripts.windows_test_scope import windows_skips_as_unix_only
from tests import conftest


def test_ledger_muse_case_is_not_a_unix_file():
    nodeid = "tests/test_coordination_ledger.py::test_muse_agent_ids_supported"
    assert windows_skips_as_unix_only(nodeid) is False


def test_hook_bridge_file_is_not_a_unix_file():
    assert windows_skips_as_unix_only(
        "tests/test_muse_hook_bridge.py::test_session_start"
    ) is False


def test_mac_worker_mentioned_only_in_the_function_name_stays_in_scope():
    assert windows_skips_as_unix_only(
        "tests/test_artifact_upload_flow.py::test_mac_worker_uploads_and_verifier_reconciles"
    ) is False


def test_same_contract_surface_is_not_skipped_for_the_word_mac():
    assert windows_skips_as_unix_only(
        "tests/test_runtime_surfaces.py::test_10_mac_and_windows_follow_the_same_contract"
    ) is False


def test_unix_only_files_stay_skipped():
    skipped = [
        "tests/test_mac_worker_contract.py::test_success_is_bound_and_accepted",
        "tests/test_mac_native_heartbeat.py::test_beat",
        "tests/test_mac_agy_orphan_marker.py::test_mark",
        "tests/test_mac_deliver_heartbeat.py::test_beat",
        "tests/test_muse_supervisor.py::test_stop_prevents_restart",
        "tests/test_muse_convergence.py::test_collects",
        "tests/test_run_physical.py::test_run_physical_success",
        "tests/test_run_physical_restart.py::test_run_physical_restart_run1_fail",
        "tests/test_ci_acceptance_credentials.py::test_acceptance_missing_keys_fail_closed_without_starting_server",
        "tests/ops/test_macos_muse_night_runner.py::test_installer_hands_path_to_launchd",
        "tests\\test_mac_worker_recovery.py::test_restart_after_started_execution_does_not_execute_again",
    ]
    assert [nodeid for nodeid in skipped if not windows_skips_as_unix_only(nodeid)] == []


def test_scope_decision_is_stable_across_repeated_calls():
    nodeid = "tests/test_coordination_ledger.py::test_muse_agent_ids_supported"
    assert windows_skips_as_unix_only(nodeid) == windows_skips_as_unix_only(nodeid)
    assert windows_skips_as_unix_only("") is False
    assert windows_skips_as_unix_only(None) is False


def test_collection_hook_asks_the_path_scope():
    source = inspect.getsource(conftest.pytest_collection_modifyitems)
    assert "windows_skips_as_unix_only" in source
