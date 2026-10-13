"""NEEDS-YOU-Quelle der Statusanzeige: needs_you.jsonl hat Vorrang, Demo-Beleg ist Fallback."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from demo_view import load_needs_you, write  # noqa: E402

ROWS = [
    {"kind": "NEEDS_YOU", "mission_id": "M-2", "blocked_event_id": "e-9", "blocker": "Budget-Freigabe fehlt",
     "at": "2026-10-13T14:05:00Z", "next_action": "confirm or amend the goal contract; Courier resumes once on its own"},
    {"kind": "NEEDS_YOU", "mission_id": "M-1", "blocked_event_id": "e-3", "blocker": "Veroeffentlichung <b>nur</b> mit OK",
     "at": "2026-10-13T14:00:00Z", "next_action": "Vertrag bestaetigen"},
]


def _evidence(tmp: Path) -> Path:
    out = tmp / "ev"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_60s.py"), "--fast", "--no-color", "--out", str(out)],
                   check=True, capture_output=True, timeout=60)
    return out / "demo_60s_evidence.json"


def _home(tmp: Path, text: str) -> Path:
    p = tmp / "home" / "run" / "needs_you.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _lines(rows):
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def test_jsonl_has_priority(tmp_path):
    ev = _evidence(tmp_path)
    html = write(ev, tmp_path / "v.html", _home(tmp_path, _lines(ROWS))).read_text(encoding="utf-8")
    assert "NEEDS-YOU-Quelle: needs_you.jsonl" in html
    assert "M-1: Veroeffentlichung &lt;b&gt;nur&lt;/b&gt; mit OK" in html
    assert "Naechste Aktion: Vertrag bestaetigen" in html and "M-2: Budget-Freigabe fehlt" in html
    assert html.index("M-1:") < html.index("M-2:")  # nach Zeit sortiert
    assert "T3: publication" not in html and "Fallback" not in html


def test_fallback_when_missing_or_empty(tmp_path):
    ev = _evidence(tmp_path)
    for p in (tmp_path / "nope" / "needs_you.jsonl", _home(tmp_path, ""), None):
        html = write(ev, tmp_path / "v.html", p).read_text(encoding="utf-8")
        assert "Demo-Beleg (Fallback" in html and "T3: publication" in html


def test_broken_lines_skipped(tmp_path):
    text = ("{kaputt\n" + _lines(ROWS[:1]) + "[1,2]\n\n" + '{"kind":"OTHER","mission_id":"X"}\n'
            + _lines(ROWS[:1]) + '{"kind":"NEEDS_YOU"}\n' + '{"kind": "NEEDS_YOU", "mission_id": "M-3"')
    rows = load_needs_you(_home(tmp_path, text))
    assert [r["mission_id"] for r in rows] == ["M-2"]  # Duplikat und kaputte Zeilen weg
    only_broken = load_needs_you(_home(tmp_path, "{kaputt\nnull\n"))
    assert only_broken == []


def test_deterministic_regardless_of_line_order(tmp_path):
    ev = _evidence(tmp_path)
    a = write(ev, tmp_path / "a.html", _home(tmp_path / "a", _lines(ROWS))).read_text(encoding="utf-8")
    b = write(ev, tmp_path / "b.html", _home(tmp_path / "b", _lines(ROWS[::-1]))).read_text(encoding="utf-8")
    assert a == b


def test_cli_home_option(tmp_path):
    _home(tmp_path, _lines(ROWS))
    out = tmp_path / "cli"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_60s.py"), "--fast", "--no-color", "--html",
                    "--out", str(out), "--home", str(tmp_path / "home")], check=True, capture_output=True, timeout=60)
    assert "M-2: Budget-Freigabe fehlt" in (out / "needs_you_view.html").read_text(encoding="utf-8")
