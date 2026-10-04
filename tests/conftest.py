import sys
import pytest

def pytest_collection_modifyitems(config, items):
    if sys.platform == "win32":
        skip_mac = pytest.mark.skip(reason="mac OS / UNIX specific tests not supported on Windows")
        for item in items:
            name = str(item.nodeid)
            if any(x in name for x in ["mac_worker", "mac_native", "mac_agy", "mac_deliver", "muse", "golden", "run_physical", "ci_acceptance", "script_credentials"]):
                item.add_marker(skip_mac)
