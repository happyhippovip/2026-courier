"""Minimal reproducer: a duplicated RECLAIM/RECONCILE line ends a LATER live lease of the same holder
(work_queue.py:713 matches only on holder name), letting another home assign a second mission."""
import os, sys, tempfile
from datetime import timedelta as td
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import setup, assigned_by_item, T0
from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once

for kind in ("RECLAIM", "RECONCILE"):
    root = Path(tempfile.mkdtemp(dir=os.environ["RACE_TMP"]))
    idir, ledger, (a, b, c) = setup(root, 3, ("WKA",), ttl=60)
    q = WorkQueue(idir, ledger)
    feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0)                     # A: claim, ATTACH, ASSIGNED
    if kind == "RECLAIM":
        q.reclaim("WKA", "dennis", "A gone", now=T0 + td(seconds=70))
    else:
        q.reconcile("WKA", "FAILED", "holder-0 FAILED", "holder-1", now=T0 + td(seconds=70))
    line = ledger.read_text().splitlines()[-1]
    q.claim("WKA", "holder-1", 60, now=T0 + td(seconds=80), announce=True)       # B claims, dies before ATTACH
    print(kind, "A takes over B's unattached claim:", feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=T0 + td(seconds=150))["claimed"])
    at = T0 + td(seconds=160)
    print("  live lease:", q.items(now=at)[0]["lease"]["holder"])
    with ledger.open("a") as fh:
        fh.write(line + "\n")                                                     # same line, written twice
    v = q.items(now=at)[0]
    print("  after duplicate line: status", v["status"], "lease", v["lease"])
    print("  C feed:", feed_once(c, "CODEX_MAC", "MAC_LOCAL", now=at)["claimed"], "ASSIGNED:", assigned_by_item([a, b, c]))
