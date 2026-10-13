"""Ein-Befehl-Demo: deterministisch, < 60 s, alle Phasen, NEEDS_YOU dann RESOLVED, Beleg mit SHA-256."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(out: Path, fast=True):
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_one.py"), "--no-color", "--out", str(out)]
                       + (["--fast"] if fast else []), capture_output=True, text=True, timeout=90,
                       env={"PYTHONIOENCODING": "utf-8", "PATH": ""})
    return p, time.monotonic() - t0


def test_one_command_deterministic_with_resolved(tmp_path):
    a, _ = _run(tmp_path / "a")
    b, _ = _run(tmp_path / "b")
    assert a.returncode == 0, a.stderr
    assert a.stdout.replace(str(tmp_path / "a"), "X") == b.stdout.replace(str(tmp_path / "b"), "X")
    out = a.stdout
    idx = [out.index(f"[ {p} ]") for p in ("GOAL", "WORKING", "NEEDS YOU", "DONE")]
    assert idx == sorted(idx)
    assert out.count("DEMO / MOCK-MODUS") == 2
    assert "needs_you.jsonl: NEEDS_YOU -> RESOLVED" in out and "Status:        DONE" in out
    for d in ("a", "b"):
        assert (tmp_path / d / "needs_you.jsonl").read_bytes() == (tmp_path / "a" / "needs_you.jsonl").read_bytes()
    rows = [json.loads(l) for l in (tmp_path / "a" / "needs_you.jsonl").read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["NEEDS_YOU", "RESOLVED"]
    assert (rows[0]["mission_id"], rows[0]["blocked_event_id"]) == (rows[1]["mission_id"], rows[1]["blocked_event_id"])
    ev = (tmp_path / "a" / "demo_one_evidence.json").read_bytes()
    sha = hashlib.sha256(ev).hexdigest()
    assert sha == hashlib.sha256((tmp_path / "b" / "demo_one_evidence.json").read_bytes()).hexdigest()
    assert f"SHA-256:       {sha}" in out
    e = json.loads(ev)
    assert e["mode"] == "MOCK" and e["controller_posts"] == ["a", "b"]
    assert e["queue"] == [["CLAIM", "WKA"], ["RELEASE", "WKA"], ["CLAIM", "WKB"], ["RELEASE", "WKB"]]
    html = (tmp_path / "a" / "demo_one_view.html").read_text(encoding="utf-8")
    assert html == (tmp_path / "b" / "demo_one_view.html").read_text(encoding="utf-8")
    assert "0 offen, 1 erledigt" in html and "WKA erledigt" in html and "DEMO / MOCK-MODUS" in html


def test_one_command_paced_under_60s(tmp_path):
    p, dt = _run(tmp_path / "c", fast=False)
    assert p.returncode == 0, p.stderr
    assert dt < 60, dt
