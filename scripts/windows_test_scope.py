"""Which collected tests Windows skips as UNIX-only.

The historical check matched substrings in the whole node id. That skipped
in-scope tests whose names merely mentioned muse or mac_worker. The skip now
looks at the file path only, and only at the UNIX-only files.
"""


_PATH_MARKERS = (
    "mac_worker",
    "mac_native",
    "mac_agy",
    "mac_deliver",
    "run_physical",
    "ci_acceptance_credentials",
)

_FILE_NAMES = frozenset({
    "test_muse_supervisor.py",
    "test_muse_convergence.py",
    "test_macos_muse_night_runner.py",
})


def windows_skips_as_unix_only(nodeid):
    """Return True when this node id is a UNIX-only file on Windows.

    The part after '::' is the test name and does not decide the skip.
    """
    if not isinstance(nodeid, str) or nodeid == "":
        return False
    path = nodeid.split("::", 1)[0].replace("\\", "/")
    if path == "":
        return False
    filename = path.rsplit("/", 1)[-1]
    if filename in _FILE_NAMES:
        return True
    return any(marker in path for marker in _PATH_MARKERS)
