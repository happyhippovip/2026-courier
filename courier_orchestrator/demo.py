"""Demo: one goal, 3 mock workers, independent mock Pruefer, end to end."""
from __future__ import annotations

import json
import sys

from .engine import Orchestrator
from .models import Goal, Task
from .workers import MockPruefer, MockWorker, default_registry


def build(actions_for_t3=(), bad_website=False):
    goal = Goal("G-DEMO-1", "P-COURIER", "Landingpage-Abschnitt 'Wie Courier arbeitet'", 2.0, "2026-10-20")
    tasks = [
        Task("T1", goal.goal_id, "spec", ("docs/orchestrator/",), "Abschnittsspezifikation", ("headline", "3_steps"), 0.2),
        Task("T2", goal.goal_id, "web", ("website/",), "HTML-Entwurf", ("renders", "uses_spec"), 0.2, depends_on=("T1",)),
        Task("T3", goal.goal_id, "tests", ("tests/",), "Testplan", ("covers_steps",), 0.2,
             actions=tuple(actions_for_t3), depends_on=("T2",)),
    ]
    reg = [p for p in default_registry() if p.worker_id != "courier-grok-mock"]
    workers = {p.worker_id: MockWorker(p, "bad" if bad_website and p.role == "Website" else "ok") for p in reg}
    return Orchestrator(goal, tasks, workers, MockPruefer())


def main() -> int:
    orch = build(bad_website=True)
    card = orch.run()
    print(json.dumps({"board": card, "events": orch.events}, indent=2, default=str))
    return 0 if card["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
