"""Probe 1: 4 homes run feed_once concurrently on one shared queue; shared advancing clock (+ optional skew)."""
import json, multiprocessing as mp, os, random, sys, tempfile, time, traceback
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import setup, assigned_by_item, clock_now, T0

AGENTS = [("GOOGLE_WINDOWS", "WINDOWS_REMOTE"), ("MUSE_MAC", "MAC_LOCAL"), ("CODEX_MAC", "MAC_LOCAL"),
          ("MUSE_WINDOWS", "WINDOWS_REMOTE")]
ITEMS = ("WK1", "WK2", "WK3", "WK4", "WK5")


class SimCrash(Exception):
    pass


def worker(idx, home, clock, seed, skew, rounds, out_q, crash_p):
    random.seed(seed)
    import courier_core.work_queue as wq
    from courier_worker.queue_feed import feed_once
    orig_attach = wq.WorkQueue.attach

    def attach(self, *a, **k):
        if random.random() < crash_p:
            raise SimCrash()                   # process "died" between claim and attach
        return orig_attach(self, *a, **k)
    wq.WorkQueue.attach = attach
    errs, crashes, reports = [], 0, []
    my_skew = random.randint(-skew, skew) if skew else 0
    for r in range(rounds):
        now = clock_now(clock) + timedelta(seconds=my_skew)
        try:
            rep = feed_once(home, *AGENTS[idx], now=now)
            reports.append(rep.get("outcome"))
        except SimCrash:
            crashes += 1
        except Exception as e:
            errs.append(f"{type(e).__name__}:{getattr(e, 'code', e)} @{now.isoformat()} {" | ".join(l.strip() for l in traceback.format_exc().splitlines() if "queue_feed.py" in l)}")
        if random.random() < 0.03:               # mission finished -> FINAL_DONE checkpoint for a held item
            st = home / "ledger_bridge_state.json"
            held = [i["id"] for i in wq.WorkQueue(home.parent / "items", home.parent / "queue.jsonl").items(now=now)
                    if (i.get("lease") or {}).get("holder") == f"holder-{idx}"]
            if held:
                st.write_text(json.dumps({"missions": {held[0]: {"status": "FINAL_DONE", "task_id": "t"}}}))
        if random.random() < 0.1:
            time.sleep(random.uniform(0.02, 0.15))   # go quiet: leases expire meanwhile
    out_q.put((idx, errs, crashes))


def run_once(it, skew, crash_p):
    root = Path(tempfile.mkdtemp(prefix=f"p1_{it}_", dir=os.environ["RACE_TMP"]))
    idir, ledger, homes = setup(root, 4, ITEMS, ttl=3)
    clock = root / "clock"
    clock.write_text("0")
    q = mp.Queue()
    ps = [mp.Process(target=worker, args=(i, homes[i], clock, it * 100 + i, skew, 120, q, crash_p)) for i in range(4)]
    for p in ps:
        p.start()
    t = 0
    while any(p.is_alive() for p in ps):
        time.sleep(0.01)
        t += 1
        clock.write_text(str(t))
    res = [q.get() for _ in ps]
    for p in ps:
        p.join()
    by = assigned_by_item(homes)
    dup = {k: v for k, v in by.items() if len(v) > 1}
    errs = [e for _, es, _ in res for e in es]
    crashes = sum(c for _, _, c in res)
    takeovers = sum(1 for line in ledger.read_text().splitlines() if json.loads(line)["type"] == "CLAIM")
    return dup, errs, crashes, takeovers, by


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    for skew, crash_p in ((0, 0.0), (0, 0.05), (2, 0.05)):
        fails, errsamples, total_err, total_crash, claims = 0, [], 0, 0, 0
        for it in range(n):
            dup, errs, crashes, c, by = run_once(it, skew, crash_p)
            fails += bool(dup)
            total_err += len(errs)
            total_crash += crashes
            claims += c
            if dup and len(errsamples) < 3:
                errsamples.append(("DUP", it, dup))
            for e in errs[:2]:
                if len(errsamples) < 6:
                    errsamples.append(("EXC", it, e))
        print(f"skew=±{skew}s crash_p={crash_p}: iters={n} dupASSIGNED_iters={fails} escaped_exc={total_err} "
              f"sim_crashes={total_crash} CLAIM_events={claims}")
        for s in errsamples:
            print("   ", s)
