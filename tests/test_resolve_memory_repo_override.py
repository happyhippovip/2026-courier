"""COURIER_MEMORY_REPO env override for the memory resolver default path."""
import importlib

import scripts.resolve_project_memory as mod


def test_default_memory_repo_honors_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("COURIER_MEMORY_REPO", str(tmp_path))
    importlib.reload(mod)
    assert mod.DEFAULT_MEMORY_REPO_PATH == tmp_path
