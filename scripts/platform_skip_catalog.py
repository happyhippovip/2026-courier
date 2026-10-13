"""Which tests the Windows CI host must skip.

The catalog matches the test file path. A cross-platform test whose name
mentions "muse" stays required on Windows. POSIX-only files stay skipped.
"""

SKIP_REASON = "mac OS / UNIX specific tests not supported on Windows"

# File-path prefixes. A node id is "tests/file.py::test_name".
WINDOWS_SKIP_PATH_PREFIXES = (
    "tests/test_mac_worker_",
    "tests/test_mac_native_",
    "tests/test_mac_agy_",
    "tests/test_mac_deliver_",
    "tests/test_muse_supervisor.py",
    "tests/ops/test_macos_muse_night_runner.py",
    "tests/test_run_physical.py",
    "tests/test_run_physical_restart.py",
    "tests/test_ci_acceptance_credentials.py",
)


def windows_skip_reason(nodeid: str) -> str | None:
    path = str(nodeid).replace("\\", "/").split("::", 1)[0]
    for prefix in WINDOWS_SKIP_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return SKIP_REASON
    return None
