import pytest
import os
import sys
sys.path.insert(0, "tests")
from p3_preview import load_patched_server, VERIFIER, WORKER
from test_artifact_upload_flow import setup, claim, upload, result_for
import hashlib

class MockMonkeypatch:
    def setenv(self, *a, **k):
        os.environ[a[0]] = str(a[1])

def run():
    import tempfile
    import pathlib
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        expected_hash = hashlib.sha256(b"ok\n").hexdigest()
        srv, http = setup(tmp, MockMonkeypatch(), artifacts=([{"path": "win.txt", "expected_sha256": expected_hash}]))
        task = claim(http)
        rec = upload(http, task, "win.txt", b"ok\n").get_json()
        ref = {"path": "win.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": rec["size"]}
        res = http.post("/tasks/result", headers=WORKER, json=result_for(task, [ref]))
        print("POST status:", res.status_code)
        print("POST data:", res.get_data(as_text=True))

if __name__ == '__main__':
    run()
