import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("COURIER_API_KEY", "test-secret")
os.environ.setdefault("COURIER_VERIFIER_API_KEY", "verifier-secret")


def pytest_configure(config):
    """Windows fix for Pytest teardown PermissionError (WinError 5 on directory junctions / locked temp files)."""
    if sys.platform == "win32":
        try:
            import _pytest.pathlib

            orig_cleanup_symlinks = _pytest.pathlib.cleanup_dead_symlinks

            def safe_cleanup_dead_symlinks(root):
                try:
                    orig_cleanup_symlinks(root)
                except (PermissionError, OSError):
                    pass

            _pytest.pathlib.cleanup_dead_symlinks = safe_cleanup_dead_symlinks

            orig_cleanup_numbered = _pytest.pathlib.cleanup_numbered_dir

            def safe_cleanup_numbered_dir(root, prefix, keep, lock_timeout):
                try:
                    orig_cleanup_numbered(root, prefix, keep, lock_timeout)
                except (PermissionError, OSError):
                    pass

            _pytest.pathlib.cleanup_numbered_dir = safe_cleanup_numbered_dir
        except (ImportError, AttributeError):
            pass
