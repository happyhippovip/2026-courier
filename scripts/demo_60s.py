#!/usr/bin/env python3
"""60-Sekunden-Demo (DEMO / MOCK): Ziel -> Agenten arbeiten -> geprueftes Ergebnis mit Beleg.

Nutzt ausschliesslich den Mock-Modus des Orchestrators aus PR #542
(courier_orchestrator: MockWorker + MockPruefer). Kein echtes Geld, keine
bezahlten Modellaufrufe, kein Netzwerk, keine Live-Systeme. stdlib only.

Phasen: GOAL -> WORKING -> NEEDS YOU -> DONE
Beleg: JSON-Artefakt + SHA-256 (deterministisch, ohne Zeitstempel).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from courier_orchestrator.demo import build  # noqa: E402  (Mock-Modus aus #542)
from courier_orchestrator.models import GoalStatus, TaskStatus, to_dict  # noqa: E402

BANNER = "*** DEMO / MOCK-MODUS - kein echtes Geld, keine bezahlten Modellaufrufe, keine Live-Systeme ***"
DEFAULT_GOAL = "Landingpage-Abschnitt 'Wie Courier arbeitet'"
GATE = "publication"


def _c(code: str, s: str, color: bool) -> str:
    return f"\033[{code}m{s}\033[0m" if color else s


class Out:
    def __init__(self, pace: float, color: bool):
        self.pace, self.color, self.lines = pace, color, []

    def say(self, s: str = "", pause: float = 1.0) -> None:
        self.lines.append(s)
        print(s, flush=True)
        if self.pace:
            time.sleep(pause * self.pace)

    def phase(self, name: str, code: str) -> None:
        self.say("")
        self.say(_c(code + ";1", f"==== [ {name} ] " + "=" * (40 - len(name)), self.color), 0.5)


def run(goal_text: str, out_dir: Path, pace: float = 0.0, color: bool = False,
        approve: bool = True, interactive: bool = False) -> dict:
    o = Out(pace, color)
    o.say(_c("33;1", BANNER, color), 1.5)

    # GOAL
    o.phase("GOAL", "36")
    orch = build(actions_for_t3=(GATE,), bad_website=True)
    orch.goal.title = goal_text
    o.say(f"Ziel:    {goal_text}")
    o.say(f"Budget:  {orch.goal.budget_eur:.2f} EUR (MOCK-Rechengeld, nichts wird bezahlt)")
    o.say(f"Aufgaben: " + ", ".join(f"{t.task_id}={t.expected_output}" for t in orch.tasks), 2.0)

    # WORKING
    o.phase("WORKING", "34")
    seen = 0

    def flush_events():
        nonlocal seen
        for ev in orch.events[seen:]:
            kind, tid, info = ev
            task = next(t for t in orch.tasks if t.task_id == tid)
            w = task.assigned_worker or "-"
            msg = {"RESULT_RECEIVED": f"{tid}: Agent {w} liefert Ergebnis (Versuch {info})",
                   "REJECTED": f"{tid}: Pruefer lehnt ab ({info}) -> neuer Versuch",
                   "ACCEPTED": f"{tid}: Pruefer PASS -> Hubwriter schreibt Delta",
                   "HUMAN_GATE": f"{tid}: Freigabe noetig: {', '.join(info) if isinstance(info, tuple) else info}"}[kind]
            o.say("  " + msg, 1.5)
        seen = len(orch.events)

    card = orch.run()
    flush_events()

    # NEEDS YOU
    if orch.goal.status == GoalStatus.NEEDS_YOU:
        o.phase("NEEDS YOU", "33")
        o.say(f"{card['next_action'].replace('HUMAN: ', 'Aufgabe ')} will '{GATE}' ausloesen. Das darf nur ein Mensch freigeben.")
        if interactive:
            approve = input("Freigeben? [j/N] ").strip().lower() in ("j", "ja", "y", "yes")
        else:
            o.say("(Demo: Freigabe wird simuliert - in echt klickt hier der Mensch)", 2.0)
        if not approve:
            o.say("Nicht freigegeben. Demo endet ohne Veroeffentlichung.")
            return {"status": "NEEDS_YOU", "lines": o.lines}
        o.say(_c("32", "Freigabe erteilt (MOCK: es wird nichts veroeffentlicht).", color), 1.0)
        orch.goal.authorization = tuple(orch.goal.authorization) + (GATE,)
        orch.goal.status = GoalStatus.WORKING
        for t in orch.tasks:
            if t.status == TaskStatus.NEEDS_HUMAN:
                t.status = TaskStatus.QUEUED
        o.phase("WORKING", "34")
        card = orch.run()
        flush_events()

    # DONE
    o.phase("DONE" if card["status"] == "DONE" else card["status"], "32")
    evidence = {
        "demo": "courier-demo-60s", "mode": "MOCK", "goal": goal_text,
        "board": card,
        "deltas": [to_dict(d) for d in orch.hub.deltas],
        "events": [list(e) for e in orch.events],
    }
    blob = json.dumps(evidence, sort_keys=True, ensure_ascii=False, default=str, indent=2).encode()
    sha = hashlib.sha256(blob).hexdigest()
    out_dir.mkdir(parents=True, exist_ok=True)
    art = out_dir / "demo_60s_evidence.json"
    art.write_bytes(blob)
    (out_dir / "demo_60s_evidence.sha256").write_text(f"{sha}  {art.name}\n")
    o.say(f"Status:        {card['status']}")
    o.say(f"Gepruefte Ergebnisse: {card['verified_results']}/{len(orch.tasks)} (jedes vom unabhaengigen Pruefer)")
    o.say(f"Kosten:        {card['budget']['spent']:.2f} EUR MOCK (real: 0,00 EUR)")
    o.say(f"Beleg:         {art}")
    o.say(_c("32;1", f"SHA-256:       {sha}", color))
    o.say(_c("33;1", BANNER, color))
    return {"status": card["status"], "sha256": sha, "artifact": str(art), "lines": o.lines}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Courier 60-Sekunden-Demo (MOCK)")
    ap.add_argument("--goal", default=DEFAULT_GOAL, help="Ziel-Text")
    ap.add_argument("--fast", action="store_true", help="ohne Pausen (fuer Tests)")
    ap.add_argument("--interactive", action="store_true", help="Freigabe per Tastatur bei NEEDS YOU")
    ap.add_argument("--out", default=str(ROOT / "demo_out"), help="Ordner fuer den Beleg")
    ap.add_argument("--no-color", action="store_true")
    a = ap.parse_args(argv)
    pace = 0.0 if a.fast else 1.0
    color = not a.no_color and sys.stdout.isatty()
    r = run(a.goal, Path(a.out), pace=pace, color=color, interactive=a.interactive)
    return 0 if r["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
