"""Probe 5: views live processes saw (incl. mid-run snapshots taken under the queue lock) equal a
from-scratch replay of the same ledger bytes in a fresh interpreter."""
import json, multiprocessing as mp, os, random, subprocess, sys, tempfile, time
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import setup, clock_now, T0
from probe1_feed_storm import AGENTS, ITEMS, SimCrash

REPLAY = r'''
import json, sys, shutil, tempfile
from pathlib import Path
from datetime import datetime
from courier_core.work_queue import WorkQueue
items, ledger_bytes, now = sys.argv[1], sys.argv[2], datetime.fromisoformat(sys.argv[3])
d = Path(tempfile.mkdtemp()); shutil.copytree(items, d / "items"); (d / "q.jsonl").write_bytes(Path(ledger_bytes).read_bytes())
print(json.dumps(WorkQueue(d / "items", d / "q.jsonl").items(now=now), sort_keys=True))
'''


def worker(idx, home, clock, seed, rounds, snapdir, barrier, out_q):
    random.seed(seed)
    import courier_core.work_queue as wq
    from courier_worker.queue_feed import feed_once
    orig = wq.WorkQueue.attach
    def attach(self, *a, **k):
        if random.random() < 0.05:
            raise SimCrash()
        return orig(self, *a, **k)
    wq.WorkQueue.attach = attach
    q = wq.WorkQueue(home.parent / "items", home.parent / "queue.jsonl")
    snaps = 0
    for r in range(rounds):
        now = clock_now(clock)
        try:
            feed_once(home, *AGENTS[idx], now=now)
        except Exception:
            pass
        if random.random() < 0.1:
            with q._lock():
                raw = q.ledger_path.read_bytes()
                view = [wq._public(x) for x in sorted(q._effective(now).values(), key=lambda x: x["id"])]
            p = snapdir / f"s{idx}_{r}"
            p.with_suffix(".ledger").write_bytes(raw)
            p.with_suffix(".json").write_text(json.dumps({"now": now.isoformat(), "view": view}, sort_keys=True))
            snaps += 1
    barrier.wait()
    end = T0 + timedelta(seconds=10_000)
    out_q.put((idx, json.dumps(q.items(now=end), sort_keys=True)))


def replay(items, ledger_file, now_iso):
    r = subprocess.run([sys.executable, "-c", REPLAY, str(items), str(ledger_file), now_iso],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def run_once(it):
    root = Path(tempfile.mkdtemp(prefix=f"p5_{it}_", dir=os.environ["RACE_TMP"]))
    idir, ledger, homes = setup(root, 4, ITEMS, ttl=3)
    snapdir = root / "snaps"; snapdir.mkdir()
    clock = root / "clock"; clock.write_text("0")
    b, q = mp.Barrier(4), mp.Queue()
    ps = [mp.Process(target=worker, args=(i, homes[i], clock, 7000 + it * 10 + i, 80, snapdir, b, q)) for i in range(4)]
    [p.start() for p in ps]
    t = 0
    while any(p.is_alive() for p in ps):
        time.sleep(0.01); t += 1; clock.write_text(str(t))
    finals = [q.get() for _ in ps]; [p.join() for p in ps]
    bad = []
    if len({f for _, f in finals}) != 1:
        bad.append("live processes disagree at end")
    end = (T0 + timedelta(seconds=10_000)).isoformat()
    if replay(idir, ledger, end) != finals[0][1]:
        bad.append("fresh replay != live final view")
    snaps = sorted(snapdir.glob("*.json"))
    for s in snaps:
        d = json.loads(s.read_text())
        if replay(idir, s.with_suffix(".ledger"), d["now"]) != json.dumps(d["view"], sort_keys=True):
            bad.append(f"snapshot {s.name} differs")
    return bad, len(snaps), sum(1 for _ in ledger.read_text().splitlines())


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    fails, sample, nsnap, nev = 0, None, 0, 0
    for it in range(n):
        bad, s, e = run_once(it)
        nsnap += s; nev += e
        if bad:
            fails += 1; sample = sample or bad
    print(f"replay determinism: iters={n} fails={fails} snapshots_checked={nsnap} ledger_events={nev} {sample or ''}")
