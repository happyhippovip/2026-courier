import sys
import os
import pytest

# Fail-closed API keys require dummy values in local testing.
if "COURIER_API_KEY" not in os.environ:
    os.environ["COURIER_API_KEY"] = "local-test-key"
if "COURIER_VERIFIER_API_KEY" not in os.environ:
    os.environ["COURIER_VERIFIER_API_KEY"] = "local-verifier-key"

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

def pytest_collection_modifyitems(config, items):
    if sys.platform == "win32":
        skip_mac = pytest.mark.skip(reason="mac OS / UNIX specific tests not supported on Windows")
        for item in items:
            name = str(item.nodeid)
            if any(x in name for x in ["mac_worker", "mac_native", "mac_agy", "mac_deliver", "muse", "run_physical", "ci_acceptance"]):
                item.add_marker(skip_mac)

@pytest.fixture(autouse=True)
def _clear_shared_breaker():
    from scripts.provider_circuit import ProviderCircuitBreaker
    ProviderCircuitBreaker._shared_circuits = {}
