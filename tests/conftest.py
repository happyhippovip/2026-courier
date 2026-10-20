import fnmatch
import json
import sys
import os
from pathlib import Path
import pytest

# Fail-closed API keys require dummy values in local testing.
if "COURIER_API_KEY" not in os.environ:
    os.environ["COURIER_API_KEY"] = "local-test-key"
if "COURIER_VERIFIER_API_KEY" not in os.environ:
    os.environ["COURIER_VERIFIER_API_KEY"] = "local-verifier-key"

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if "PYTHONPATH" in os.environ:
    if REPO_ROOT not in os.environ["PYTHONPATH"].split(os.pathsep):
        os.environ["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{os.environ['PYTHONPATH']}"
else:
    os.environ["PYTHONPATH"] = REPO_ROOT

if sys.platform == "win32":
    # Monkeypatch cleanup_dead_symlinks to ignore PermissionError on Windows during teardown
    try:
        import _pytest.pathlib
        if not hasattr(_pytest.pathlib, "_monkeypatched_cleanup"):
            original_cleanup = _pytest.pathlib.cleanup_dead_symlinks
            def safe_cleanup_dead_symlinks(root):
                try:
                    original_cleanup(root)
                except PermissionError:
                    pass
            _pytest.pathlib.cleanup_dead_symlinks = safe_cleanup_dead_symlinks
            _pytest.pathlib._monkeypatched_cleanup = True
    except Exception:
        pass

WINDOWS_SKIP_MARKERS = (
    "mac_worker",
    "mac_native",
    "mac_agy",
    "mac_deliver",
    "muse",
    "run_physical",
    "ci_acceptance",
)


def _windows_known():
    path = Path(__file__).resolve().parents[1] / ".github" / "ci" / "known_failures.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    windows = data.get("Windows") if isinstance(data, dict) else None
    return windows if isinstance(windows, dict) else {}


def windows_collect_skips(nodeid, known=None):
    """Whether Windows collection hides this node from the outcomes artifact.

    Nodes the Windows baseline still lists, and nodes matching the published
    out_of_scope patterns, stay in the run. The outcomes artifact is the CI
    record of those results. Other marker matches stay skipped.
    """
    windows = _windows_known() if known is None else (known.get("Windows") if isinstance(known, dict) else {})
    if not isinstance(windows, dict):
        windows = {}
    patterns = (windows.get("out_of_scope") or {}).get("patterns") or []
    if any(isinstance(pattern, str) and fnmatch.fnmatchcase(nodeid, pattern) for pattern in patterns):
        return False
    listed = set(windows.get("failing") or []) | set(windows.get("flaky") or [])
    if nodeid in listed:
        return False
    return any(marker in nodeid for marker in WINDOWS_SKIP_MARKERS)

def pytest_collection_modifyitems(config, items):
    if sys.platform == "win32":
        from scripts.windows_test_scope import windows_skips_as_unix_only
        skip_mac = pytest.mark.skip(reason="mac OS / UNIX specific tests not supported on Windows")
        for item in items:
            if windows_skips_as_unix_only(str(item.nodeid)):
                item.add_marker(skip_mac)


@pytest.fixture(autouse=True)
def reset_provider_circuits():
    try:
        from scripts.provider_circuit import ProviderCircuitBreaker
        ProviderCircuitBreaker._shared_circuits.clear()
    except Exception:
        pass
    yield
    try:
        from scripts.provider_circuit import ProviderCircuitBreaker
        ProviderCircuitBreaker._shared_circuits.clear()
    except Exception:
        pass
