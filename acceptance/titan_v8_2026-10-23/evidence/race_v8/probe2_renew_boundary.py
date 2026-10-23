"""Probe 2: holder renews exactly at / just before expiry while another home tries takeover."""
import json, multiprocessing as mp, os, random, sys, tempfile, time
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import setup, assigned_by_item, T0


def op(kind, idir, ledger, barrier, delay, now_s, out):
    from courier_core.work_queue import WorkQueue, WorkQueueError
    q = WorkQueue(idir, ledger)
    barrier.wait()
    time.sleep(delay)
    now = T0 + timedelta(seconds=now_s)
    try:
        if kind == "renewA":
            r = q.renew("WKA", "holder-0", 60, now=now)
        elif kind == "claimA":
            r = q.claim("WKA", "holder-0", 60, now=now, announce=True)
        else:
            r = q.claim("WKA", "holder-1", 60, now=now, announce=True)
        out.put((kind, "OK", r.get("idempotent")))
    except WorkQueueError as e:
        out.put((kind, e.code, None))


def feed(home, idx, barrier, delay, now_s, out):
    from courier_worker.queue_feed import feed_once
    ag = [("GOOGLE_WINDOWS", "WINDOWS_REMOTE"), ("MUSE_MAC", "MAC_LOCAL")][idx]
    barrier.wait()
    time.sleep(delay)
    try:
        out.put((idx, "OK", feed_once(home, *ag, now=T0 + timedelta(seconds=now_s))["outcome"]))
    except Exception as e:
        out.put((idx, f"EXC {type(e).__name__}:{getattr(e, 'code', e)}", None))


def scenario(it, attached, a_kind, a_now):
    root = Path(tempfile.mkdtemp(prefix=f"p2_{it}_", dir=os.environ["RACE_TMP"]))
    idir, ledger, homes = setup(root, 2, ("WKA",), ttl=60)
    from courier_core.work_queue import WorkQueue
    q = WorkQueue(idir, ledger)
    q.claim("WKA", "holder-0", 60, now=T0, announce=True)        # expires at T0+60
    if attached:
        q.attach("WKA", "holder-0", "GOOGLE_WINDOWS/WINDOWS_REMOTE", now=T0)
    b, out = mp.Barrier(2), mp.Queue()
    ps = [mp.Process(target=op, args=(a_kind, idir, ledger, b, random.uniform(0, 0.003), a_now, out)),
          mp.Process(target=op, args=("claimB", idir, ledger, b, random.uniform(0, 0.003), 60, out))]
    [p.start() for p in ps]; [p.join() for p in ps]
    res = dict((k, (c, i)) for k, c, i in [out.get() for _ in ps])
    view = [i for i in q.items(now=T0 + timedelta(seconds=60)) if i["id"] == "WKA"][0]
    winners = [k for k, (c, _) in res.items() if c == "OK"]
    holder = (view["lease"] or {}).get("holder")
    bad = []
    expect_none = attached and a_kind == "renewA" and a_now == 60   # renew at expiry refused + attached refused
    if (len(winners) != 1) and not (expect_none and winners == []):
        bad.append(f"winners={winners} res={res}")
    if winners == ["claimB"] and holder != "holder-1":
        bad.append(f"B won but holder={holder}")
    if winners and winners[0] != "claimB" and holder != "holder-0":
        bad.append(f"A won but holder={holder}")
    if attached and res["claimB"][0] == "OK":
        bad.append("B took over an ATTACHED lease")
    if a_kind == "renewA" and a_now == 60 and res["renewA"][0] == "OK":
        bad.append("renew at exact expiry accepted")
    return bad, res


def feed_scenario(it, attached, a_now):
    root = Path(tempfile.mkdtemp(prefix=f"p2f_{it}_", dir=os.environ["RACE_TMP"]))
    idir, ledger, homes = setup(root, 2, ("WKA",), ttl=60)
    from courier_core.work_queue import WorkQueue
    from courier_worker.queue_feed import feed_once
    q = WorkQueue(idir, ledger)
    if attached:
        feed_once(homes[0], "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)
    else:
        q.claim("WKA", "holder-0", 60, host="WINDOWS_REMOTE", now=T0, announce=True)
    b, out = mp.Barrier(2), mp.Queue()
    ps = [mp.Process(target=feed, args=(homes[0], 0, b, random.uniform(0, 0.02), a_now, out)),
          mp.Process(target=feed, args=(homes[1], 1, b, random.uniform(0, 0.02), 60, out))]
    [p.start() for p in ps]; [p.join() for p in ps]
    res = [out.get() for _ in ps]
    by = assigned_by_item(homes)
    bad = []
    if any(len(v) > 1 for v in by.values()):
        bad.append(f"two ASSIGNED {by}")
    if attached and 1 in by.get("WKA", []):
        bad.append("B assigned an attached item")
    excs = [r for r in res if r[1] != "OK"]
    return bad, excs


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    for attached in (False, True):
        for a_kind, a_now in (("renewA", 60), ("renewA", 59), ("claimA", 60)):
            fails, sample, outcomes = 0, None, {}
            for it in range(n):
                bad, res = scenario(it, attached, a_kind, a_now)
                key = tuple(sorted((k, c) for k, (c, _) in res.items()))
                outcomes[key] = outcomes.get(key, 0) + 1
                if bad:
                    fails += 1; sample = sample or bad
            print(f"core attached={attached} A={a_kind}@+{a_now}s vs B claim@+60s: iters={n} fails={fails} outcomes={outcomes} {sample or ''}")
    for attached in (False, True):
        for a_now in (60, 59, 30):
            fails, sample, excs = 0, None, []
            for it in range(n):
                bad, e = feed_scenario(it, attached, a_now)
                excs += e
                if bad:
                    fails += 1; sample = sample or bad
            print(f"feed attached={attached} A feed@+{a_now}s vs B feed@+60s: iters={n} fails={fails} escaped={len(excs)} {set(x[1] for x in excs)} {sample or ''}")
