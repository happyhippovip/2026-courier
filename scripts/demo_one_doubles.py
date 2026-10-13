"""Synthetische Doubles fuer die Ein-Befehl-Demo (MOCK, stdlib only, kein pytest noetig).

MockController beantwortet die V1-Controller-Aufrufe der Bridge im Prozess (kein Netzwerk),
dedupliziert per idempotency_key und meldet Tasks auf Zuruf als COMPLETE. setup() legt ein
frisches Courier-Home mit zwei Arbeitspaketen (WKA -> WKB) und einem unbestaetigten Goal Contract an.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

TOKEN = "demo-mock-token-not-a-secret-0000000000"
AGENT, HOST, HOLDER = "GOOGLE_WINDOWS", "WINDOWS_REMOTE", "worker-demo"
SHA = "0" * 40
CONTROLLER = "http://127.0.0.1:9"   # wird nie kontaktiert: http-Aufrufe gehen an MockController


class MockController:
    def __init__(self):
        self.posts, self.views = [], {}

    def __call__(self, method, url, headers, body, timeout):
        if method == "POST" and url.endswith("/v1/tasks"):
            posted = json.loads(body.decode("utf-8"))
            key = posted["idempotency_key"]
            task_id = "task-" + hashlib.sha256(key.encode()).hexdigest()[:32]
            dup = any(p["idempotency_key"] == key for p in self.posts)
            if not dup:
                self.posts.append(posted)
                self.views[task_id] = {"task_id": task_id, "status": "QUEUED", "attempt": 0,
                                       "accepted_result_id": None, "last_reason": None}
            return (200 if dup else 201), json.dumps({"task_id": task_id, "duplicate": dup}).encode()
        if method == "GET" and "/v1/tasks/" in url:
            view = self.views.get(url.rstrip("/").rsplit("/", 1)[-1])
            return (200, json.dumps(view).encode()) if view else (404, b'{"error":"unknown_task"}')
        raise RuntimeError(f"MOCK: unerwarteter Aufruf {method} {url}")

    def complete_all(self):
        for task_id, v in self.views.items():
            if v["status"] != "COMPLETE":
                v.update(status="COMPLETE", attempt=1, accepted_result_id="result-" + task_id[-6:])


def _item(item_id, deps):
    return {"id": item_id, "title": f"synthetic {item_id}", "lane": "L1", "branch": f"lane/L1-{item_id.lower()}",
            "files_scope": [f"out/{item_id}/"], "depends_on": deps, "acceptance": ["synthetic artifact"],
            "provider_hints": [], "status": "READY", "lease": None}


def setup(base: Path, end_result: str):
    from courier_core.goal_contract import AcceptanceCriterion, Gates, GoalContract, GoalContractStore
    from courier_core.work_queue import WorkQueue
    from courier_worker import queue_feed

    home = base / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text(TOKEN + "\n", encoding="utf-8")
    (home / "ledger_tasks.json").write_text("{}", encoding="utf-8")
    items = base / "items"
    items.mkdir()
    for iid, deps in (("WKA", []), ("WKB", ["WKA"])):
        (items / f"{iid}.json").write_text(json.dumps(_item(iid, deps)), encoding="utf-8")
    contract = GoalContract(
        goal_id="goal-demo", end_result=end_result, allowed_scope=["out"], forbidden_scope=["secrets"],
        constraints=["no network"],
        acceptance_criteria=[AcceptanceCriterion("artifact", "out.txt hash matches", "deterministic")],
        side_effect_limits=["no commits"], gates=Gates(human=True, money=True, safety=True))
    GoalContractStore(home / "goal_contracts.jsonl").append(contract)

    def spec(unit):
        return {"adapter": "synthetic", "params": {"unit": unit}, "effect_class": "idempotent",
                "max_attempts": 1, "lease_ttl_s": 30, "source_sha": SHA, "goal_id": contract.goal_id,
                "goal_fingerprint": contract.fingerprint(),
                "goal_task": {"scope": ["out"], "acceptance_ids": ["artifact"], "evidence_class": "deterministic"}}

    ledger = base / "queue.jsonl"
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps({
        "items_dir": str(items), "ledger": str(ledger), "holder": HOLDER, "ttl_s": 600,
        "specs": {"WKA": spec("a"), "WKB": spec("b")}}), encoding="utf-8")
    return home, WorkQueue(items_dir=items, ledger_path=ledger), ledger, contract


def queue_seq(ledger: Path):
    if not ledger.exists():
        return []
    rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l]
    return [(r["type"], r["item_id"]) for r in rows if r["type"] in ("CLAIM", "RELEASE")]


def bridge_pass(home: Path, http) -> None:
    from scripts.ledger_v1_bridge import main
    err = []
    code = main(["--home", str(home), "--agent-id", AGENT, "--host-id", HOST, "--controller", CONTROLLER],
                http=http, stdout=lambda s: None, stderr=err.append)
    if code != 0:
        raise RuntimeError("bridge: " + "".join(err))
