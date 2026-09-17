from test_tomato_two_torture import _runtime_process_is_bound_to_repo


REPO = r"C:\Users\lol\2026-workspace\2026-courier"


def test_serving_python_path_binds_runtime_when_launcher_is_external():
    observed = {
        "process_path": REPO + r"\.venv_service\Scripts\pythonw.exe",
        "parent_path": r"C:\Windows\System32\wscript.exe",
        "command_line": '"pythonw.exe" server\\run_waitress.py',
    }

    assert _runtime_process_is_bound_to_repo(observed, REPO)


def test_unrelated_process_and_launcher_fail_closed():
    observed = {
        "process_path": r"C:\Python\pythonw.exe",
        "parent_path": r"C:\Windows\System32\wscript.exe",
        "command_line": '"pythonw.exe" server\\run_waitress.py',
    }

    assert not _runtime_process_is_bound_to_repo(observed, REPO)


def test_similar_prefix_outside_repo_fails_closed():
    observed = {
        "process_path": REPO + r"-old\.venv_service\Scripts\pythonw.exe",
        "parent_path": "",
        "command_line": '"pythonw.exe" server\\run_waitress.py',
    }

    assert not _runtime_process_is_bound_to_repo(observed, REPO)


def test_repo_python_running_wrong_entrypoint_fails_closed():
    observed = {
        "process_path": REPO + r"\.venv_service\Scripts\pythonw.exe",
        "parent_path": r"C:\Windows\System32\wscript.exe",
        "command_line": '"pythonw.exe" unrelated.py',
    }

    assert not _runtime_process_is_bound_to_repo(observed, REPO)
