#!/usr/bin/env python3
"""Statische Statusanzeige (eine HTML-Datei, kein Server, kein JS, keine Pakete) fuer die 60-s-Demo (MOCK).

Liest den Demo-Beleg (demo_60s_evidence.json) und erzeugt deterministisch eine HTML-Datei mit
grossen Phasen-Kacheln GOAL / WORKING / NEEDS YOU / DONE.
Hinweis: courier_worker/queue_feed.py ist in diesem Branch nicht vorhanden; Quelle ist daher der Demo-Beleg.

  python3 scripts/demo_view.py demo_out/demo_60s_evidence.json -o demo_out/needs_you_view.html
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from html import escape
from pathlib import Path

PHASES = ("GOAL", "WORKING", "NEEDS YOU", "DONE")
CSS = """
*{box-sizing:border-box}body{margin:0;font:18px/1.4 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;background:#0f1117;color:#e8e8e8}
.mock{background:#f5c400;color:#111;font-weight:800;text-align:center;padding:10px;letter-spacing:.5px}
main{max-width:1200px;margin:0 auto;padding:24px}h1{font-size:28px;margin:0 0 4px}.sub{color:#9aa;margin-bottom:20px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.tile{border-radius:14px;padding:22px;min-height:190px;background:#1b1f2a;border:3px solid #2a3040}
.tile h2{font-size:30px;margin:0 0 10px}.tile .st{font-size:14px;text-transform:uppercase;color:#9aa}
.goal{border-color:#2bb3c0}.working{border-color:#3b7ddd}.done{border-color:#2fbf5b}
.needs{border-color:#ff7a00;background:#3a2300;box-shadow:0 0 0 4px #ff7a0066}
.needs h2{color:#ffb15c}.reason{font-size:22px;font-weight:700;color:#fff;margin-top:8px}
.done.final{background:#0f2e1a}.final .st{color:#7fe39b}
ul{margin:6px 0 0;padding-left:20px;font-size:15px}
.ev{margin-top:22px;background:#151923;border-radius:12px;padding:16px;font:14px/1.5 ui-monospace,Menlo,Consolas,monospace}
.sha{word-break:break-all;color:#7fe39b}
"""


def load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def render(ev: dict, sha: str) -> str:
    events = [tuple(e) for e in ev.get("events", [])]
    board = ev.get("board", {})
    gates = [(e[1], e[2]) for e in events if e[0] == "HUMAN_GATE"]
    work = [e for e in events if e[0] != "HUMAN_GATE"]
    label = {"RESULT_RECEIVED": "Ergebnis (Versuch {})", "ACCEPTED": "Pruefer PASS (Versuch {})",
             "REJECTED": "abgelehnt: {}"}
    li = lambda items: "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"
    reason = "; ".join(f"{t}: {', '.join(g) if isinstance(g, list) else g}" for t, g in gates)
    status = board.get("status", "?")
    tiles = [
        ("goal", "GOAL", "Ziel", li([ev.get("goal", ""), f"Budget {board.get('budget', {}).get('eur', 0):.2f} EUR (MOCK)"])),
        ("working", "WORKING", f"{len(work)} Ereignisse",
         li([f"{e[1]}: " + label.get(e[0], e[0] + " {}").format(e[2]) for e in work])),
        ("needs", "NEEDS YOU", "Freigabe durch Mensch" if gates else "keine Freigabe noetig",
         f'<div class="reason">{escape(reason) or "-"}</div>'
         '<div>Nur ein Mensch darf das freigeben. (Demo: simuliert, nichts veroeffentlicht)</div>' if gates else ""),
        ("done" + (" final" if status == "DONE" else ""), "DONE", f"Status: {status}",
         li([f"{board.get('verified_results', 0)} gepruefte Ergebnisse",
             f"Kosten {board.get('budget', {}).get('spent', 0):.2f} EUR MOCK (real 0,00 EUR)"])),
    ]
    body = "".join(f'<section class="tile {c}"><div class="st">{escape(s)}</div><h2>{t}</h2>{h}</section>'
                   for c, t, s, h in tiles)
    banner = "DEMO / MOCK-MODUS &ndash; kein echtes Geld, keine bezahlten Modellaufrufe, keine Live-Systeme"
    return ("<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width\"><title>Courier Demo (MOCK)</title>"
            f"<style>{CSS}</style></head><body><div class=\"mock\">{banner}</div><main>"
            f"<h1>Courier &ndash; 60-Sekunden-Demo</h1><div class=\"sub\">Modus: {escape(str(ev.get('mode', '?')))}"
            " &middot; Ziel &rarr; Agenten &rarr; Freigabe &rarr; gepruefter Beleg</div>"
            f"<div class=\"tiles\">{body}</div>"
            f"<div class=\"ev\">Beleg: demo_60s_evidence.json<br>SHA-256: <span class=\"sha\">{sha}</span></div>"
            f"</main><div class=\"mock\">{banner}</div></body></html>\n")


def write(evidence: Path, out: Path) -> Path:
    ev, sha = load(evidence)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(ev, sha), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("evidence", nargs="?", default="demo_out/demo_60s_evidence.json")
    ap.add_argument("-o", "--out", default="demo_out/needs_you_view.html")
    a = ap.parse_args(argv)
    print(write(Path(a.evidence), Path(a.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
