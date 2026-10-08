"""Regression: generate_openapi is import-safe, CWD-independent, and parses routes."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_openapi import build_spec, main

APP = '''@app.route('/v1/health')
def h(): pass

@app.route('/v1/tasks', methods=['GET', 'POST'])
def t(): pass

@app.route('/v1/tasks/<task_id>', methods=["GET"])
def one(): pass
'''


@pytest.fixture
def approot(tmp_path):
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "app.py").write_text(APP, encoding="utf-8")
    (tmp_path / "static").mkdir()
    return tmp_path


def test_build_spec_parses_methods_and_params():
    spec = build_spec(APP)
    assert set(spec["paths"]) == {"/v1/health", "/v1/tasks", "/v1/tasks/{task_id}"}
    assert set(spec["paths"]["/v1/health"]) == {"get"}  # default method
    assert set(spec["paths"]["/v1/tasks"]) == {"get", "post"}
    assert spec["paths"]["/v1/tasks/{task_id}"]["get"]["responses"]["200"]


def test_main_writes_spec_under_given_root(approot):
    assert main(root=approot) == 3
    written = json.loads((approot / "static" / "openapi.json").read_text(encoding="utf-8"))
    assert set(written["paths"]) == {"/v1/health", "/v1/tasks", "/v1/tasks/{task_id}"}


def test_main_ignores_caller_cwd(approot, tmp_path, monkeypatch):
    # Regression: paths were CWD-relative, so running from another
    # directory crashed (or read/wrote the wrong tree).
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert main(root=approot) == 3
    assert not (elsewhere / "static").exists()


def test_import_has_no_side_effects(tmp_path, monkeypatch):
    # Regression: the old module regenerated the spec at import time.
    monkeypatch.chdir(tmp_path)
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "go_import_check",
        str(Path(__file__).resolve().parents[1] / "scripts" / "generate_openapi.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not (tmp_path / "static").exists()
    assert not list(tmp_path.iterdir())
