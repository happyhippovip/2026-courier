#!/usr/bin/env python3
"""Ein-Befehl-Demo (DEMO / MOCK), < 60 s:

Auftrag rein -> Agenten-Mock arbeitet -> BLOCKED -> needs_you.jsonl (NEEDS_YOU)
-> simulierte Freigabe -> Wiederaufnahme + RESOLVED -> HTML-Ansicht + Pruefprotokoll (JSON + SHA-256).

Laeuft ueber den echten Pfad courier_worker.queue_feed.feed_once + scripts.ledger_v1_bridge
(Branch feat/needs-you-resolved-backfill, hier eingemergt), aber nur mit synthetischen Doubles
(scripts/demo_one_doubles.py): Controller = MockController im Prozess (kein Netzwerk), Adapter "synthetic",
Bestaetigung "person:demo" simuliert. Kein Geld, keine Modellaufrufe, keine Live-Systeme.
Alles passiert in einem frischen Temp-/Out-Ordner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    sys.path.insert(0, str(p))

BANNER = "*** DEMO / MOCK-MODUS - kein echtes Geld, keine bezahlten Modellaufrufe, keine Live-Systeme ***"
FIXED_NOW = datetime(2026, 10, 26, 9, 0, 0, tzinfo=timezone.utc)   # Foerdertermin, fuer deterministische Inbox
CONFIRMED_AT = "2026-10-26T09:00:30Z"


def _c(code, s, color):
    return f"\033[{code}m{s}\033[0m" if color else s


def run(out_dir: Path, pace: float = 0.0, color: bool = False, goal: str | None = None) -> dict:
    from courier_core.goal_contract import GoalContractStore
    from courier_worker import queue_feed
    from scripts.coordination_resume import reduce_store
    from scripts.github_coordination import FileCoordinationStore
    from demo_one_doubles import AGENT, HOST, MockController, bridge_pass, queue_seq as _queue_seq, setup
    from demo_view import load_needs_you, write as write_view

    lines: list[str] = []

    def say(s="", pause=1.0):
        lines.append(s)
        print(s, flush=True)
        if pace:
            time.sleep(pause * pace)

    def phase(name, code):
        say("")
        say(_c(code + ";1", f"==== [ {name} ] " + "=" * (40 - len(name)), color), 0.5)

    work = Path(tempfile.mkdtemp(prefix="courier_demo_one_"))
    try:
        home, queue, qledger, contract = setup(work, goal or "Foerder-Demo: synthetisches Artefakt erzeugen und pruefen")
        http = MockController()
        inbox = home / "run" / queue_feed.NEEDS_YOU_INBOX
        store = lambda: reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))

        def tick():
            queue_feed.feed_once(home, AGENT, HOST, now=FIXED_NOW)
            bridge_pass(home, http)
            http.complete_all()

        def inbox_rows():
            return [json.loads(l) for l in inbox.read_text(encoding="utf-8").splitlines()] if inbox.exists() else []

        say(_c("33;1", BANNER, color), 1.5)
        phase("GOAL", "36")
        title = goal or contract.end_result
        say(f"Auftrag:  {title}  (goal_id={contract.goal_id})")
        say("Arbeit:   WKA (Einheit a) -> WKB (Einheit b, haengt von WKA ab)")
        say("Regel:    Goal Contract braucht menschliche Bestaetigung (human gate)", 2.0)

        phase("WORKING", "34")
        for _ in range(3):
            tick()
        m = store().get_mission("WKA")
        say(f"  queue_feed + Bridge: WKA geclaimt, Ledger-Status {m['status'].value if hasattr(m['status'], 'value') else m['status']}", 1.5)
        say(f"  Blocker: {m.get('blocker')}", 1.5)
        say(f"  Controller-Posts bisher: {len(http.posts)} (nichts ausgefuehrt ohne Freigabe)", 1.5)

        phase("NEEDS YOU", "33")
        rows = inbox_rows()
        assert [r["kind"] for r in rows] == ["NEEDS_YOU"], rows
        say(f"  needs_you.jsonl: NEEDS_YOU {rows[0]['mission_id']} / {rows[0]['blocked_event_id']}")
        say(f"  Naechste Aktion: {rows[0]['next_action']}", 2.0)
        say("  (Demo: Bestaetigung durch 'person:demo' wird simuliert)", 1.5)
        GoalContractStore(home / "goal_contracts.jsonl").append(contract.confirm("person:demo", CONFIRMED_AT))
        say(_c("32", "  Goal Contract bestaetigt (MOCK).", color), 1.0)

        phase("WORKING", "34")
        for _ in range(12):
            tick()
            if all(i["status"] == "DONE" for i in queue.items()):
                break
        events = store().events
        resumes = [e.event_id for e in events if e.event_id.startswith("queue-resume-")]
        rows = inbox_rows()
        say(f"  Wiederaufnahme genau einmal: {resumes[0]}", 1.5)
        say(f"  needs_you.jsonl: {' -> '.join(r['kind'] for r in rows)}", 1.5)
        say(f"  Queue: {', '.join(f'{t} {i}' for t, i in _queue_seq(qledger))}", 1.5)

        # Pruefprotokoll (nur stabile Felder -> deterministischer Hash)
        open_rows = load_needs_you(inbox)
        status = "DONE" if all(i["status"] == "DONE" for i in queue.items()) and not open_rows else "FAILED"
        finals = sorted(e.mission_id for e in events if e.event_type.value == "FINAL")
        evidence = {
            "demo": "courier-demo-one-command", "mode": "MOCK", "goal": title,
            "board": {"status": status, "verified_results": len(finals),
                      "budget": {"eur": 0.0, "spent": 0.0, "remaining": 0.0}},
            "needs_you_jsonl": rows,
            "events": [["HUMAN_GATE", rows[0]["mission_id"], "goal_contract confirmation"]]
                      + [["RESULT_RECEIVED", m, 1] for m in finals] + [["ACCEPTED", m, 1] for m in finals],
            "ledger": [[e.mission_id, e.event_type.value, e.event_id if e.event_id.startswith("queue-") else "-"]
                       for e in events],
            "queue": [list(x) for x in _queue_seq(qledger)],
            "controller_posts": sorted(p["params"]["unit"] for p in http.posts),
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(evidence, sort_keys=True, ensure_ascii=False, indent=2).encode()
        sha = hashlib.sha256(blob).hexdigest()
        art = out_dir / "demo_one_evidence.json"
        art.write_bytes(blob)
        (out_dir / "demo_one_evidence.sha256").write_text(f"{sha}  {art.name}\n")
        shutil.copy(inbox, out_dir / "needs_you.jsonl")
        html = write_view(art, out_dir / "demo_one_view.html", out_dir / "needs_you.jsonl")

        phase("DONE" if status == "DONE" else status, "32")
        say(f"Status:        {status}  (offene NEEDS_YOU: {len(open_rows)})")
        say(f"Ergebnisse:    FINAL {', '.join(finals)}; Controller-Posts {evidence['controller_posts']} (je genau 1)")
        say(f"HTML-Ansicht:  {html}")
        say(f"Beleg:         {art}")
        say(_c("32;1", f"SHA-256:       {sha}", color))
        say(_c("33;1", BANNER, color))
        return {"status": status, "sha256": sha, "artifact": str(art), "html": str(html), "lines": lines}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Courier Ein-Befehl-Demo (MOCK)")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--goal")
    ap.add_argument("--out", default=str(ROOT / "demo_out"))
    a = ap.parse_args(argv)
    r = run(Path(a.out), 0.0 if a.fast else 1.0, not a.no_color and sys.stdout.isatty(), a.goal)
    return 0 if r["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
