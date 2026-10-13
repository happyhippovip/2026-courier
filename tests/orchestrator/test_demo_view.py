"""Die statische Statusanzeige wird deterministisch erzeugt und enthaelt alle Phasen."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _gen(out: Path) -> str:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_60s.py"), "--fast", "--no-color", "--html",
                    "--out", str(out)], check=True, capture_output=True, timeout=60)
    return (out / "needs_you_view.html").read_text(encoding="utf-8")


def test_view_deterministic_and_complete(tmp_path):
    a, b = _gen(tmp_path / "a"), _gen(tmp_path / "b")
    assert a == b
    for phase in ("<h2>GOAL</h2>", "<h2>WORKING</h2>", "<h2>NEEDS YOU</h2>", "<h2>DONE</h2>"):
        assert phase in a
    assert "DEMO / MOCK-MODUS" in a
    assert 'class="tile needs"' in a and "T3: publication" in a
    assert "Status: DONE" in a
    assert "<script" not in a and "http" not in a  # kein JS, keine externen Ressourcen
