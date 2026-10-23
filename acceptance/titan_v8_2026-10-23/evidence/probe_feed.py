"""Probe queue_feed: B09 crash windows, D09 next exactly once, D11 ERROR/BLOCKED mission stall."""
import json, tempfile
from pathlib import Path
from courier_core.work_queue import WorkQueue
import courier_worker.queue_feed as qf
from courier_worker.queue_feed import feed_once, has_open_work
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore

AGENT, HOST, HOLDER = "GOOGLE_WINDOWS", "WINDOWS_REMOTE", "h1"
def item(i, deps):
    return {"id": i, "title": i, "lane": "L1", "branch": f"lane/L1-{i.lower()}", "files_scope": [f"out/{i}/"],
            "depends_on": deps, "acceptance": ["x"], "provider_hints": [], "status": "READY", "lease": None}
def spec(u):
    return {"adapter": "synthetic", "params": {"content": u}, "effect_class": "idempotent", "max_attempts": 2, "lease_ttl_s": 10}
def setup(deps_b=("WKA",)):
    t = Path(tempfile.mkdtemp(dir=Path(__file__).parent)); home = t / "home"; home.mkdir(); items = t / "items"; items.mkdir()
    for i, d in (("WKA", []), ("WKB", list(deps_b)), ("WKC", [])):
        (items / f"{i}.json").write_text(json.dumps(item(i, d)))
    led = t / "q.jsonl"
    (home / "work_queue_feed.json").write_text(json.dumps({"items_dir": str(items), "ledger": str(led), "holder": HOLDER,
        "ttl_s": 600, "specs": {"WKA": spec("a"), "WKB": spec("b"), "WKC": spec("c")}}))
    return home, led
def ev(led): return [(e["type"], e["item_id"]) for e in map(json.loads, led.read_text().splitlines()) if e["type"] in ("CLAIM", "RELEASE")]
def stamp(home, mid, status):
    p = home / "ledger_bridge_state.json"
    s = json.loads(p.read_text()) if p.exists() else {"missions": {}}
    s["missions"][mid] = {"status": status, "task_id": f"task-{mid}"}
    p.write_text(json.dumps(s))

# 1. B09: bridge stamped FINAL_DONE, process died before queue release
home, led = setup()
feed_once(home, AGENT, HOST); stamp(home, "WKA", "FINAL_DONE")
r = feed_once(home, AGENT, HOST); r2 = feed_once(home, AGENT, HOST)
print("B09 release-after-crash:", ev(led), "| 2nd pass:", r2["outcome"], r2["renewed"])

# 2. crash after RELEASE append, before claim of next
home, led = setup(deps_b=())
feed_once(home, AGENT, HOST); stamp(home, "WKA", "FINAL_DONE")
orig = WorkQueue.claim
def boom(self, *a, **k): raise SystemExit("killed between release and next claim")
WorkQueue.claim = boom
try: feed_once(home, AGENT, HOST)
except SystemExit as e: print("crash:", e)
WorkQueue.claim = orig
feed_once(home, AGENT, HOST); feed_once(home, AGENT, HOST)
print("release->claim crash:", ev(led))

# 3. crash after queue claim, before ASSIGNED event
home, led = setup()
origw = FileCoordinationStore.write_event
FileCoordinationStore.write_event = lambda self, e: (_ for _ in ()).throw(SystemExit("killed before assign"))
try: feed_once(home, AGENT, HOST)
except SystemExit as e: print("crash:", e)
FileCoordinationStore.write_event = origw
r = feed_once(home, AGENT, HOST)
red = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
print("claim->assign crash: assigned", r["assigned"], "mission WKA exists:", red.get_mission("WKA") is not None, ev(led))

# 4. D11: mission ends ERROR / BLOCKED (controller FAILED or non-idempotent lease loss)
for st in ("ERROR", "BLOCKED"):
    home, led = setup(deps_b=())
    feed_once(home, AGENT, HOST); stamp(home, "WKA", st)
    for _ in range(5): r = feed_once(home, AGENT, HOST)
    items = {i["id"]: i["status"] for i in WorkQueue(items_dir=home.parent / "items", ledger_path=led).items()}
    renews = sum(1 for e in map(json.loads, led.read_text().splitlines()) if e["type"] == "RENEW")
    print(f"D11 mission {st}: queue={items} renews={renews} last={r['outcome']} open_work={has_open_work(home)} events={ev(led)}")
