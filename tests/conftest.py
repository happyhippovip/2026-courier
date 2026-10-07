import sys
import pytest

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """
    Workaround for pytest issue on Windows where deleting the `pytest-current`
    symlink in the temporary directory raises PermissionError (WinError 5).
    """
    if sys.platform == "win32":
        tmp_path_factory = getattr(session.config, "_tmp_path_factory", None)
        if tmp_path_factory is not None and hasattr(tmp_path_factory, "_exit_stack"):
            try:
                tmp_path_factory._exit_stack.close()
            except PermissionError:
                pass
            # Remove all callbacks so the original pytest_sessionfinish doesn't fail
            if hasattr(tmp_path_factory._exit_stack, "pop_all"):
                tmp_path_factory._exit_stack.pop_all()
