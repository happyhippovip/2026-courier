import os
import pytest

def pytest_configure(config):
    if os.name == "nt":
        import _pytest.pathlib
        original_cleanup = _pytest.pathlib.cleanup_dead_symlinks
        def safe_cleanup(*args, **kwargs):
            try:
                original_cleanup(*args, **kwargs)
            except PermissionError:
                pass
        _pytest.pathlib.cleanup_dead_symlinks = safe_cleanup

def pytest_collection_modifyitems(config, items):
    if os.name == "nt":
        skip_mac = pytest.mark.skip(reason="Mac-only or legacy test skipped on Windows")
        for item in items:
            name = getattr(item.module, "__name__", "")
            if "test_mac_" in name or "test_muse_supervisor" in name or "test_artifact_upload_flow" in name or "test_dashboard_server_uncovered" in name:
                item.add_marker(skip_mac)
