"""Probe 3: SIGKILL a home between claim and attach / between attach and ASSIGNED; then others race."""
import json, multiprocessing as mp, os, random, signal, sys, tempfile, time
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import setup, assigned_by_item, T0

AG = [("GOOGLE_WINDOWS", "WINDOWS_REMOTE"), ("MUSE_MAC", "MAC_LOCAL"), ("CODEX_MAC", "MAC_LOCAL"),
      ("MUSE_WINDOWS", "WINDOWS_REMOTE")]


def crashing_a(home, point):
    import courier_core.work_queue as wq
    import scripts.github_coordination as gc
    from courier_worker.queue_feed import feed_once
    if point == "claim_attach":
        orig = wq.WorkQueue.attach
        def attach(self, *a, **k):
            os.kill(os.getpid(), signal.SIGKILL)
        wq.WorkQueue.attach = attach
    else:
        orig = gc.FileCoordinationStore.write_event
        def write_event(self, ev):
            os.kill(os.getpid(), signal.SIGKILL)
        gc.FileCoordinationStore.write_event = write_event
    feed_once(home, *AG[0], now=T0)
    os._exit(0)   # not reached


def racer(home, idx, now_s, barrier, out, probe_answer):
    from courier_worker.queue_feed import feed_once
    probe = None if probe_answer is None else (lambda i, a: probe_answer)
    barrier.wait()
    time.sleep(random.uniform(0, 0.01))
    try:
        r = feed_once(home, *AG[idx], now=T0 + timedelta(seconds=now_s), probe=probe)
        out.put((idx, "OK", r["claimed"], r["foreign_expired"]))
    except Exception as e:
        out.put((idx, f"EXC {type(e).__name__}:{getattr(e, 'code', '')}", [], []))


def run(it, point, a_restarts, probe_answer):
    random.seed(it)
    root = Path(tempfile.mkdtemp(prefix=f"p3_{point}_{it}_", dir=os.environ["RACE_TMP"]))
    idir, ledger, homes = setup(root, 4, ("WKA",), ttl=60)
    p = mp.Process(target=crashing_a, args=(homes[0], point)); p.start(); p.join()
    assert p.exitcode == -signal.SIGKILL, p.exitcode
    bad = []
    from courier_core.work_queue import WorkQueue
    from courier_worker.queue_feed import feed_once
    q = WorkQueue(idir, ledger)
    # while the lease is live nobody may take it
    r = feed_once(homes[1], *AG[1], now=T0 + timedelta(seconds=30))
    if r["claimed"]:
        bad.append("taken while live")
    # after expiry: homes 1..3 race (and optionally the restarted A)
    racers = [1, 2, 3] + ([0] if a_restarts else [])
    b, out = mp.Barrier(len(racers)), mp.Queue()
    ps = [mp.Process(target=racer, args=(homes[i], i, 61 + random.randint(0, 3), b, out, probe_answer)) for i in racers]
    [x.start() for x in ps]; [x.join() for x in ps]
    res = [out.get() for _ in ps]
    winners = [i for i, _, c, _ in res if c]
    excs = [(i, s) for i, s, _, _ in res if s != "OK"]
    by = assigned_by_item(homes)
    if point == "claim_attach":
        if len(winners) != 1:
            bad.append(f"expected exactly one takeover, got {winners}")
    else:
        foreign = [w for w in winners if w != 0]
        if foreign:
            bad.append(f"foreign takeover of attached item by {foreign}")
        if not a_restarts:
            v = [i for i in q.items(now=T0 + timedelta(seconds=70)) if i["id"] == "WKA"][0]
            if not (v["status"] == "READY" and (v["attached"] or {}).get("holder") == "holder-0"):
                bad.append(f"not foreign_expired: {v['status']} {v['attached']}")
            q.reclaim("WKA", "dennis", "A is gone", now=T0 + timedelta(seconds=70))
            b2, out2 = mp.Barrier(3), mp.Queue()
            ps = [mp.Process(target=racer, args=(homes[i], i, 70, b2, out2, None)) for i in (1, 2, 3)]
            [x.start() for x in ps]; [x.join() for x in ps]
            res2 = [out2.get() for _ in ps]
            w2 = [i for i, _, c, _ in res2 if c]
            if len(w2) != 1:
                bad.append(f"after reclaim expected one taker, got {w2}")
            by = assigned_by_item(homes)
    if any(len(v) > 1 for v in by.values()):
        bad.append(f"two ASSIGNED {by}")
    if excs:
        bad.append(f"escaped {excs}")
    return bad


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    for point, a_restarts, ans in (("claim_attach", False, None), ("claim_attach", True, None),
                                   ("attach_assigned", False, None), ("attach_assigned", False, "RUNNING"),
                                   ("attach_assigned", True, None)):
        fails, sample = 0, None
        for it in range(n):
            bad = run(it, point, a_restarts, ans)
            if bad:
                fails += 1; sample = sample or (it, bad)
        print(f"kill@{point} A_restarts={a_restarts} probe={ans}: iters={n} fails={fails} {sample or ''}")
