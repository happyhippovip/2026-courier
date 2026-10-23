"""Probe 4: after RECLAIM the old holder's late renew/release/attach/claim are rejected and change nothing;
a duplicated RECLAIM line never ends the next holder's lease."""
import json, multiprocessing as mp, os, random, sys, tempfile, time
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import setup, assigned_by_item, T0


def stale(idir, ledger, kind, now_s, barrier, out):
    from courier_core.work_queue import WorkQueue, WorkQueueError
    q = WorkQueue(idir, ledger)
    now = T0 + timedelta(seconds=now_s)
    barrier.wait()
    time.sleep(random.uniform(0, 0.005))
    try:
        if kind == "renew":
            q.renew("WKA", "holder-0", 60, now=now)
        elif kind == "release":
            q.release("WKA", "holder-0", "FINAL_DONE t", now=now)
        elif kind == "attach":
            q.attach("WKA", "holder-0", "GOOGLE_WINDOWS/WINDOWS_REMOTE", now=now)
        else:
            q.claim("WKA", "holder-0", 60, now=now, announce=True)
        out.put((kind, now_s, "ACCEPTED"))
    except WorkQueueError as e:
        out.put((kind, now_s, e.code))


def run(it, phase):
    random.seed(1000 + it)
    root = Path(tempfile.mkdtemp(prefix=f"p4_{it}_", dir=os.environ["RACE_TMP"]))
    idir, ledger, (a, b) = setup(root, 2, ("WKA",), ttl=60)
    from courier_core.work_queue import WorkQueue
    from courier_worker.queue_feed import feed_once
    q = WorkQueue(idir, ledger)
    feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)            # claim+attach+ASSIGNED, expires +60
    q.reclaim("WKA", "dennis", "A gone", now=T0 + timedelta(seconds=70))
    reclaim_line = ledger.read_text().splitlines()[-1]
    if phase == "after_new_claim":
        feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=T0 + timedelta(seconds=70))
    view_at = T0 + timedelta(seconds=80)
    before = q.items(now=view_at)
    kinds = ["renew", "release", "attach"] + (["claim"] if phase == "after_new_claim" else [])
    jobs = [(k, random.choice([30, 55, 59, 61, 70, 75])) for k in kinds for _ in range(2)]   # skewed stale clocks
    bar, out = mp.Barrier(len(jobs)), mp.Queue()
    ps = [mp.Process(target=stale, args=(idir, ledger, k, s, bar, out)) for k, s in jobs]
    [p.start() for p in ps]; [p.join() for p in ps]
    res = [out.get() for _ in ps]
    bad = [r for r in res if r[2] == "ACCEPTED"]
    after = q.items(now=view_at)
    if after != before:
        bad.append(("replay state changed", before[0]["lease"], after[0]["lease"]))
    if phase == "after_new_claim":
        with ledger.open("a") as fh:
            fh.write(reclaim_line + "\n")
        if q.items(now=view_at)[0]["lease"]["holder"] != "holder-1":
            bad.append("duplicate RECLAIM ended holder-1's lease")
    return bad


def same_holder_regains(it):
    """The old holder legitimately regains the workkey later; a duplicated old RECLAIM line is replayed."""
    root = Path(tempfile.mkdtemp(prefix=f"p4s_{it}_", dir=os.environ["RACE_TMP"]))
    idir, ledger, (a, b) = setup(root, 2, ("WKA",), ttl=60)
    from courier_core.work_queue import WorkQueue
    from courier_worker.queue_feed import feed_once
    q = WorkQueue(idir, ledger)
    feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)
    q.reclaim("WKA", "dennis", "A gone", now=T0 + timedelta(seconds=70))
    reclaim_line = ledger.read_text().splitlines()[-1]
    variant = it % 2
    if variant == 0:      # explicit CLI/human claim gives it back to A
        q.claim("WKA", "holder-0", 600, now=T0 + timedelta(seconds=80), announce=True)
        at = T0 + timedelta(seconds=90)
    else:                 # B claims, dies before ATTACH, A's feed takes over B's unattached expired claim
        q.claim("WKA", "holder-1", 60, now=T0 + timedelta(seconds=80), announce=True)
        r = feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0 + timedelta(seconds=150))
        assert r["claimed"] == ["WKA"], r
        at = T0 + timedelta(seconds=160)
    live = q.items(now=at)[0]["lease"]
    with ledger.open("a") as fh:
        fh.write(reclaim_line + "\n")
    after = q.items(now=at)[0]
    if after["lease"] != live:
        return [f"variant={variant}: live lease {live} -> {after['lease']} status={after['status']} reclaimed={after['reclaimed']}"]
    return []


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    for phase in ("before_new_claim", "after_new_claim"):
        fails, sample = 0, None
        for it in range(n):
            bad = run(it, phase)
            if bad:
                fails += 1; sample = sample or bad
        print(f"stale ops {phase}: iters={n} fails={fails} {sample or ''}")
    fails, sample = 0, []
    for it in range(n):
        bad = same_holder_regains(it)
        if bad:
            fails += 1
            if len(sample) < 2:
                sample += bad
    print(f"dup RECLAIM, old holder regained: iters={n} fails={fails} {sample}")
