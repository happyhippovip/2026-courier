"""Regression: courier_budget_alert stub must never report success."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "courier_budget_alert.py"


def test_stub_fails_closed():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode != 0
    assert "STUB" in proc.stderr
    assert "OK" not in proc.stdout


def test_import_has_no_side_effects(capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("cba_stub", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert module.main() == 2
