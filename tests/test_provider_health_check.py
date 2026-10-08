"""Regression: provider_health_check stub must never report success."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "provider_health_check.py"


def test_stub_fails_closed():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode != 0
    assert "STUB" in proc.stderr
    assert "valid" not in proc.stdout.lower()


def test_import_has_no_side_effects(capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("phc_stub", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert module.main() == 2
