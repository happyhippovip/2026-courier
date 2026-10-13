#!/usr/bin/env python3
"""Erzeugt docs/demo/demo_one.gif (+ optional .mp4) reproduzierbar aus der Ein-Befehl-Demo (MOCK).

1. scripts/demo_one.py --fast erzeugt Beleg + needs_you.jsonl (deterministisch).
2. Pro Stufe wird mit demo_view.render() eine HTML erzeugt; noch nicht erreichte Kacheln sind abgeblendet,
   eine Stufenzeile zeigt die aktuelle Phase. MOCK-Banner ist in jeder Stufe sichtbar.
3. Headless Chrome screenshottet jede Stufe (1200x676); Pillow baut die GIF, ffmpeg (falls da) die MP4.

Benoetigt: Python 3.12, Pillow, google-chrome/chromium; ffmpeg optional. Aufruf:
  python3 scripts/make_demo_gif.py [--no-mp4]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
W, H = 1200, 676
OUT = ROOT / "docs" / "demo"

# (Stufenzeile, sichtbare Kacheln, NEEDS-YOU-Zeilen aus jsonl, Board-Status, Sekunden)
STAGES = [
    ("1/5 GOAL &ndash; Auftrag rein", 1, 0, "WORKING", 2.0),
    ("2/5 WORKING &ndash; Agenten-Mock arbeitet, WKA wird BLOCKED", 2, 0, "WORKING", 2.5),
    ("3/5 NEEDS YOU &ndash; Freigabe durch Mensch noetig", 3, 1, "NEEDS_YOU", 3.0),
    ("4/5 RESOLVED &ndash; Freigabe (simuliert), genau eine Wiederaufnahme", 3, 2, "WORKING", 2.5),
    ("5/5 DONE &ndash; geprueftes Ergebnis mit SHA-256-Beleg", 4, 2, "DONE", 4.0),
]


def chrome() -> str:
    for c in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(c):
            return c
    sys.exit("headless Chrome/Chromium nicht gefunden")


def stage_html(ev: dict, sha: str, rows: list[dict], name: str, title: str, tiles: int, n_rows: int, status: str) -> str:
    from demo_view import load_needs_you, load_resolved, render
    tmp = Path(tempfile.mkdtemp())
    try:
        p = tmp / "needs_you.jsonl"
        p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows[:n_rows]), encoding="utf-8")
        e = json.loads(json.dumps(ev))
        e["board"]["status"] = status
        if tiles < 2:
            e["events"] = []
        elif n_rows < 2:     # vor der Freigabe: nur Claim + BLOCKED, noch keine Ergebnisse
            e["events"] = [["CLAIM", "WKA", "(queue_feed)"], ["BLOCKED", "WKA", "Goal Contract unbestaetigt"],
                           ["WAIT", "WKB", "wartet auf WKA"]]
        needs = load_needs_you(p) if n_rows else []
        resolved = load_resolved(p) if n_rows else []
        if n_rows == 0:      # vor NEEDS YOU: Kachel leer, kein Fallback-Text
            e["events"] = [x for x in e["events"] if x[0] != "HUMAN_GATE"]
        html = render(e, sha, needs, "needs_you.jsonl", resolved=resolved, evidence_name=name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    dim = "".join(f".tile:nth-child({i}){{opacity:.12}}" for i in range(tiles + 1, 5))
    extra = (f"<style>{dim}body{{font-size:16px}}.stage{{font-size:26px;font-weight:800;color:#fff;"
             "margin:0 0 14px}}.tile{{min-height:250px}}" + ("" if tiles == 4 else ".ev{visibility:hidden}")
             + ("" if n_rows else ".src{visibility:hidden}") + "</style>")
    html = html.replace("</head>", extra + "</head>")
    return html.replace('<div class="src">', f'<div class="stage">{title}</div><div class="src">', 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mp4", action="store_true")
    a = ap.parse_args(argv)
    from PIL import Image

    work = Path(tempfile.mkdtemp(prefix="demo_gif_"))
    try:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_one.py"), "--fast", "--no-color",
                        "--out", str(work / "run")], check=True, capture_output=True)
        art = work / "run" / "demo_one_evidence.json"
        ev = json.loads(art.read_text(encoding="utf-8"))
        sha = (work / "run" / "demo_one_evidence.sha256").read_text().split()[0]
        rows = [json.loads(l) for l in (work / "run" / "needs_you.jsonl").read_text(encoding="utf-8").splitlines()]
        frames, durations = [], []
        for i, (title, tiles, n_rows, status, secs) in enumerate(STAGES):
            h = work / f"s{i}.html"
            h.write_text(stage_html(ev, sha, rows, art.name, title, tiles, n_rows, status), encoding="utf-8")
            png = work / f"s{i}.png"
            subprocess.run([chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                            f"--window-size={W},{H}", "--force-device-scale-factor=1", f"--screenshot={png}",
                            h.as_uri()], check=True, capture_output=True)
            frames.append(Image.open(png).convert("RGB"))
            durations.append(int(secs * 1000))
        OUT.mkdir(parents=True, exist_ok=True)
        pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
        gif = OUT / "demo_one.gif"
        pal[0].save(gif, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)
        print(f"{gif} {gif.stat().st_size} bytes {sum(durations) / 1000:.1f}s")
        if not a.no_mp4 and shutil.which("ffmpeg"):
            lst = work / "list.txt"
            lst.write_text("".join(f"file '{work}/s{i}.png'\nduration {d / 1000}\n" for i, d in enumerate(durations))
                           + f"file '{work}/s{len(durations) - 1}.png'\n")
            mp4 = OUT / "demo_one.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                            "-vf", "fps=10,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
                            "-t", f"{sum(durations) / 1000}", "-movflags", "+faststart", "-fflags", "+bitexact", "-map_metadata", "-1", str(mp4)],
                           check=True)
            print(f"{mp4} {mp4.stat().st_size} bytes")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
