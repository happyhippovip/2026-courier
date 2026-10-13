"""Cross-platform failure catalog: Windows skips only POSIX-bound files."""

from scripts.platform_skip_catalog import SKIP_REASON, windows_skip_reason


def test_cross_platform_muse_names_are_not_windows_skips():
    assert windows_skip_reason("tests/test_muse_hook_bridge.py::test_session_start") is None
    assert windows_skip_reason(
        "tests/test_coordination_ledger.py::test_muse_agent_ids_supported"
    ) is None


def test_posix_only_files_stay_in_the_windows_skip_catalog():
    skipped = [
        "tests/test_mac_worker_contract.py::test_success_is_bound_and_accepted",
        "tests/test_mac_native_heartbeat.py::test_heartbeat",
        "tests/test_mac_agy_heartbeat.py::test_heartbeat",
        "tests/test_mac_deliver_heartbeat.py::test_heartbeat",
        "tests/test_muse_supervisor.py::test_stop_prevents_restart",
        "tests/ops/test_macos_muse_night_runner.py::test_runner_invokes_muse_exec_prompt_file",
        "tests/test_run_physical.py::test_run_physical_success",
        "tests/test_run_physical_restart.py::test_run2_gate_rejects_stale_sha",
        "tests/test_ci_acceptance_credentials.py::test_workflow_uses_secret_references_not_literals",
    ]
    for nodeid in skipped:
        assert windows_skip_reason(nodeid) == SKIP_REASON, nodeid
