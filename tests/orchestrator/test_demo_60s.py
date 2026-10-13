"""Die 60-s-Demo laeuft im Mock-Modus deterministisch, unter 60 s, und erzeugt einen Beleg."""
import hashlib
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "demo_60s.py"


def _run(out: Path, fast: bool) -> tuple[subprocess.CompletedProcess, float]:
    t0 = time.monotonic()
    args = [sys.executable, str(SCRIPT), "--no-color", "--out", str(out)] + (["--fast"] if fast else [])
    p = subprocess.run(args, capture_output=True, text=True, timeout=90, env={"PYTHONIOENCODING": "utf-8", "PATH": ""})
    return p, time.monotonic() - t0


def test_demo_deterministic_with_evidence(tmp_path):
    p1, _ = _run(tmp_path / "a", fast=True)
    p2, _ = _run(tmp_path / "b", fast=True)
    assert p1.returncode == 0, p1.stderr
    assert p1.stdout == p2.stdout.replace(str(tmp_path / "b"), str(tmp_path / "a"))
    for phase in ("[ GOAL ]", "[ WORKING ]", "[ NEEDS YOU ]", "[ DONE ]"):
        assert phase in p1.stdout
    assert "DEMO / MOCK" in p1.stdout
    art = tmp_path / "a" / "demo_60s_evidence.json"
    sha = hashlib.sha256(art.read_bytes()).hexdigest()
    assert sha == hashlib.sha256((tmp_path / "b" / "demo_60s_evidence.json").read_bytes()).hexdigest()
    assert (tmp_path / "a" / "demo_60s_evidence.sha256").read_text().startswith(sha)
    assert f"SHA-256:       {sha}" in p1.stdout
    assert '"mode": "MOCK"' in art.read_text()


def test_demo_paced_under_60s(tmp_path):
    p, dt = _run(tmp_path / "c", fast=False)
    assert p.returncode == 0, p.stderr
    assert dt < 60, dt
