"""GAP-A repro: outbox filename built from raw dispatch_id (origin base)."""
import os
import os
import sys
import tempfile

sys.path.insert(0, os.environ.get("COURIER_PRISTINE_TREE", r"C:\tmp\courier-evidence"))

from courier_worker.host import outbox_read_all, outbox_remove, outbox_write

home = tempfile.mkdtemp(prefix="repro-outbox-")
payload = {"dispatch_id": "../escape", "result_id": "r-1", "artifacts": [],
           "outcome": "failure", "retryable": False}
outbox_write(home, payload)
escaped = os.path.join(home, "escape.json")
print("escaped file exists:", os.path.exists(escaped))
print("visible via outbox_read_all:", [p for _, p in outbox_read_all(home)])
assert os.path.exists(escaped), "expected traversal write outside outbox"
outbox_remove(home, "../escape")
print("after remove, escaped exists:", os.path.exists(escaped))
print("REPRO-A CONFIRMED")
