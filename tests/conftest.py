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
