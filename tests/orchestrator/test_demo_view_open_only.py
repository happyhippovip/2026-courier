"""Statusanzeige zeigt nur offene NEEDS_YOU (ohne passenden RESOLVED)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from demo_view import load_needs_you  # noqa: E402


def _w(tmp, rows):
    p = tmp / "needs_you.jsonl"
    p.write_text("".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows), encoding="utf-8")
    return p


def ny(m, e, at="2026-10-13T14:00:00Z"):
    return {"kind": "NEEDS_YOU", "mission_id": m, "blocked_event_id": e, "blocker": "x", "at": at}


def rs(m, e):
    return {"kind": "RESOLVED", "mission_id": m, "blocked_event_id": e, "resume_event_id": f"queue-resume-{m}"}


def test_resolved_entry_hidden(tmp_path):
    rows = load_needs_you(_w(tmp_path, [ny("A", "e1"), ny("B", "e2"), rs("A", "e1")]))
    assert [r["mission_id"] for r in rows] == ["B"]


def test_resolved_needs_matching_event(tmp_path):
    # neuer Block derselben Mission (anderes blocked_event_id) bleibt offen
    rows = load_needs_you(_w(tmp_path, [ny("A", "e1"), rs("A", "e1"), ny("A", "e5", "2026-10-13T15:00:00Z"),
                                        rs("B", "e1")]))
    assert [(r["mission_id"], r["blocked_event_id"]) for r in rows] == [("A", "e5")]


def test_order_independent_and_broken_lines(tmp_path):
    rows = load_needs_you(_w(tmp_path, [rs("A", "e1"), "{kaputt", ny("A", "e1"), '{"kind":"RESOLVED"}', ny("C", "e3")]))
    assert [r["mission_id"] for r in rows] == ["C"]


def test_all_resolved_falls_back_to_demo_evidence(tmp_path):
    import subprocess
    out = tmp_path / "o"
    home = tmp_path / "h" / "run"
    home.mkdir(parents=True)
    _w(home, [ny("A", "e1"), rs("A", "e1")])
    subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_60s.py"), "--fast", "--no-color", "--html",
                    "--out", str(out), "--home", str(tmp_path / "h")], check=True, capture_output=True, timeout=60)
    html = (out / "needs_you_view.html").read_text(encoding="utf-8")
    assert "Demo-Beleg (Fallback" in html and "A: x" not in html
