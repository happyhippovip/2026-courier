"""Regression: scripts.courier_github_dispatcher must not carry dead imports."""
import ast
import sys
import os
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts import courier_github_dispatcher as dispatcher

MODULE = Path(__file__).resolve().parent.parent / "scripts" / "courier_github_dispatcher.py"


def test_module_exposes_dispatcher_api():
    for name in ("log", "run_loop"):
        assert callable(getattr(dispatcher, name)), name
    assert dispatcher.WORKER_ID == "GITHUB-DISPATCHER"


def test_no_dead_sys_import():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "sys" not in imported, "'import sys' must stay removed (dead code)"
    assert "sys" not in used, "'sys' must not be referenced"
