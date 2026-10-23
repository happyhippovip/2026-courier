"""Deterministic reproducer: NOT_HOLDER escapes feed_once when another home takes over an
announced-but-unattached claim between this home's claim/items() and its attach()."""
import os, sys, tempfile
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import setup, assigned_by_item, T0
import courier_core.work_queue as wq
from courier_worker.queue_feed import feed_once

for path in ("claim", "held"):
    root = Path(tempfile.mkdtemp(dir=os.environ["RACE_TMP"]))
    idir, ledger, (a, b) = setup(root, 2, ("WKA",), ttl=60)
    q = wq.WorkQueue(idir, ledger)
    if path == "held":   # A claimed earlier and died before ATTACH; A restarts at +59 while B runs at +61
        q.claim("WKA", "holder-0", 60, host="WINDOWS_REMOTE", now=T0, announce=True)
        a_now = T0 + timedelta(seconds=59)
    else:                # A claims at T0 in feed_once; B (clock ahead by >ttl, or A stalled) runs before A's attach
        a_now = T0
    orig = wq.WorkQueue.attach
    fired = []
    def attach(self, item, holder, ref, now=None):
        if holder == "holder-0" and not fired:
            fired.append(1)
            print("  B:", feed_once(b, "MUSE_MAC", "MAC_LOCAL", now=T0 + timedelta(seconds=61))["claimed"])
        return orig(self, item, holder, ref, now=now)
    wq.WorkQueue.attach = attach
    try:
        print(path, "A:", feed_once(a, "GOOGLE_WINDOWS", "WINDOWS_REMOTE", now=a_now))
    except Exception as e:
        print(path, "ESCAPED from feed_once:", type(e).__name__, e.code)
    wq.WorkQueue.attach = orig
    print("  ASSIGNED by item:", assigned_by_item([a, b]))
