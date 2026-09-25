"""End to end: workers upload artifact bytes to the server-owned store, the result
references artifact_id, and the verifier re-hashes the server copy. Runs against
server/app.py + docs/p3/artifact-upload-cutover.patch applied in a temp copy."""
import hashlib
import io
import json
import subprocess
import urllib.error

import pytest

from p3_preview import PATCH, ROOT, VERIFIER, WORKER, load_patched_server

IDS = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")


def setup(tmp_path, monkeypatch, worker="WINDOWS-01", target="windows", caps=("windows",), artifacts=("win.txt",)):
    srv = load_patched_server(tmp_path, monkeypatch)
    http = srv.app.test_client()
    http.post("/workers/register", headers=WORKER, json={"worker_id": worker, "capabilities": list(caps)})
    http.post("/goals", headers=WORKER, json={"goal_text": "g", "workflow_plan": [
        {"task_id": "w1", "target_agent": target, "instruction": "make it", "artifacts": list(artifacts)}]})
    return srv, http


def upload(http, task, artifact_name, data, headers=WORKER, **over):
    meta = {"name": artifact_name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
            **{f: task[f] for f in IDS}, **over}
    return http.post("/artifacts", headers={**headers, "X-Courier-Artifact": json.dumps(meta)},
                     data=data, content_type="application/octet-stream")


def claim(http, worker="WINDOWS-01"):
    return http.post("/tasks/claim", headers=WORKER, json={"worker_id": worker}).get_json()["task"]


def result_for(task, refs):
    return {**{f: task[f] for f in IDS}, "run_id": "r1", "result_id": "result-1", "status": "SUCCESS",
            "artifacts": refs}


# ---------------------------------------------------------------- P3 patch

def test_p3_patch_applies_to_current_server_and_server_is_untouched():
    subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=ROOT, check=True)
    diff = subprocess.run(["git", "diff", "--quiet", "origin/main", "--", "server/app.py", "server/run_waitress.py",
                           "server/launch_server_hidden.vbs"], cwd=ROOT)
    assert diff.returncode == 0


# ---------------------------------------------------------------- server endpoints

def test_upload_then_result_reference_is_accepted(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    task = claim(http)
    r = upload(http, task, "win.txt", b"ok\n")
    assert r.status_code == 201
    rec = r.get_json()
    ref = {"path": "win.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": rec["size"]}
    assert http.post("/tasks/result", headers=WORKER, json=result_for(task, [ref])).status_code == 200
    assert srv.load_state()["tasks"]["w1"]["result"]["artifacts"] == [ref]


@pytest.mark.parametrize("over,code", [
    ({"dispatch_id": "dispatch-other"}, 400), ({"attempt_id": "w1:attempt:9"}, 400),
    ({"worker_id": "OTHER"}, 400), ({"name": "unexpected.txt"}, 400), ({"name": "../win.txt"}, 400),
    ({"sha256": "0" * 64}, 400), ({"size": 1}, 400)])
def test_upload_rejects_wrong_binding_name_or_claims(tmp_path, monkeypatch, over, code):
    srv, http = setup(tmp_path, monkeypatch)
    task = claim(http)
    assert upload(http, task, "win.txt", b"ok\n", **over).status_code == code
    assert not list((tmp_path / "artifact-store").rglob("records/*.json"))


def test_upload_requires_dispatched_task_and_worker_key(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    fake = {"goal_id": "g", "task_id": "w1", "attempt_id": "a", "dispatch_id": "d", "worker_id": "WINDOWS-01"}
    assert upload(http, fake, "win.txt", b"x").status_code == 409  # not dispatched yet
    task = claim(http)
    assert upload(http, task, "win.txt", b"x", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert upload(http, task, "win.txt", b"x", headers=VERIFIER).status_code == 401


def test_upload_size_limit(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    task = claim(http)
    assert upload(http, task, "win.txt", b"x" * 5000).status_code == 413


def test_result_with_foreign_or_unknown_artifact_id_is_rejected(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    task = claim(http)
    rec = upload(http, task, "win.txt", b"ok\n").get_json()
    good = {"path": "win.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": rec["size"]}
    for bad in (dict(good, artifact_id="art-" + "1" * 64), dict(good, sha256="f" * 64), dict(good, size=99)):
        assert http.post("/tasks/result", headers=WORKER, json=result_for(task, [bad])).status_code == 400
    assert srv.load_state()["tasks"]["w1"]["status"] == "DISPATCHED"


def test_artifact_read_requires_verifier_key(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    task = claim(http)
    art = upload(http, task, "win.txt", b"ok\n").get_json()["artifact_id"]
    assert http.get(f"/artifacts/{art}", headers=WORKER).status_code == 401
    assert http.get(f"/artifacts/{art}", headers=VERIFIER).data == b"ok\n"
    assert http.get(f"/artifacts/{art}/meta", headers=VERIFIER).get_json()["task_id"] == "w1"


# ---------------------------------------------------------------- verifier

def load_verifier(monkeypatch):
    import importlib.util
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    spec = importlib.util.spec_from_file_location("courier_verifier_under_test", ROOT / "scripts" / "courier_verifier.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def client_fetch(http):
    def fetch(artifact_id):
        meta = http.get(f"/artifacts/{artifact_id}/meta", headers=VERIFIER)
        blob = http.get(f"/artifacts/{artifact_id}", headers=VERIFIER)
        if meta.status_code != 200 or blob.status_code != 200:
            raise RuntimeError("fetch failed")
        return meta.get_json(), blob.data
    return fetch


def test_verifier_independently_hashes_server_copy_and_detects_tampering(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    task = claim(http)
    rec = upload(http, task, "win.txt", b"ok\n").get_json()
    ref = {"path": "win.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": rec["size"]}
    http.post("/tasks/result", headers=WORKER, json=result_for(task, [ref]))
    [pending] = http.get("/tasks/pending_verification", headers=VERIFIER).get_json()["tasks"]
    v = load_verifier(monkeypatch)
    local = []
    lv = lambda *a: local.append(a) or True
    assert v.verify_artifacts(pending, pending["result"], fetch=client_fetch(http), local_verify=lv) == "PASS"
    blob = tmp_path / "artifact-store" / "blobs" / rec["sha256"][:2] / rec["sha256"]
    blob.write_bytes(b"tampered")
    assert v.verify_artifacts(pending, pending["result"], fetch=client_fetch(http), local_verify=lv) == "FAIL"
    assert local == []  # never opened a local path


@pytest.mark.parametrize("target", ["windows", "mac"])
def test_verifier_never_opens_remote_worker_paths(monkeypatch, target):
    v = load_verifier(monkeypatch)
    local = []
    task = {"target_capability": target}
    result = {"artifacts": [{"path": "win.txt", "sha256": "a" * 64}]}
    assert v.verify_artifacts(task, result, fetch=None, local_verify=lambda *a: local.append(a) or True) == "FAIL"
    assert local == []


def test_verifier_fails_without_evidence(monkeypatch):
    v = load_verifier(monkeypatch)
    assert v.verify_artifacts({"target_capability": "github"}, {"artifacts": []}) == "FAIL"


def test_verifier_fails_when_fetch_fails(monkeypatch):
    v = load_verifier(monkeypatch)
    def boom(_):
        raise RuntimeError("down")
    art = {"path": "a", "sha256": "a" * 64, "artifact_id": "art-" + "a" * 64, "size": 1}
    assert v.verify_artifacts({"target_capability": "windows"}, {"artifacts": [art]}, fetch=boom) == "FAIL"


def test_verifier_fails_when_expected_artifact_missing(monkeypatch):
    v = load_verifier(monkeypatch)
    task = {"target_capability": "linux", "artifacts": ["file_a.txt", "file_b.txt"]}
    result = {"artifacts": [{"path": "file_a.txt", "sha256": "a" * 64}]}
    assert v.verify_artifacts(task, result, local_verify=lambda *a: True) == "FAIL"


def test_verifier_rejects_path_traversal_local_artifact(monkeypatch):
    v = load_verifier(monkeypatch)
    local = []
    task = {"target_capability": "linux"}
    result = {"artifacts": [{"path": "../outside.txt", "sha256": "a" * 64}]}
    assert v.verify_artifacts(task, result, local_verify=lambda *a: local.append(a) or True) == "FAIL"
    assert local == []



# ---------------------------------------------------------------- Windows worker end to end

class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class StopLoop(BaseException):
    pass


class Harness:
    def __init__(self, http, faults=(), max_calls=12):
        self.http, self.faults, self.max_calls, self.calls = http, list(faults), max_calls, []

    def __call__(self, req, data=None, timeout=None):
        endpoint = "/" + req.full_url.split("/", 3)[-1]
        self.calls.append(endpoint)
        if len(self.calls) > self.max_calls:
            raise StopLoop()
        if endpoint == "/artifacts":
            if self.faults:
                fault = self.faults.pop(0)
                if fault == "network":
                    raise urllib.error.URLError("down")
                raise urllib.error.HTTPError(req.full_url, fault, "x", {}, io.BytesIO(b"{}"))
            r = self.http.post(endpoint, headers={"Authorization": req.get_header("Authorization"),
                                                  "X-Courier-Artifact": req.get_header("X-courier-artifact")},
                               data=data, content_type="application/octet-stream")
        else:
            r = self.http.post(endpoint, headers={"Authorization": req.get_header("Authorization")},
                               json=json.loads(data.decode()) if data else {})
        if r.status_code >= 400:
            raise urllib.error.HTTPError(req.full_url, r.status_code, "x", {}, io.BytesIO(r.data))
        return Resp(r.data)


def windows_daemon(tmp_path, monkeypatch, harness, executions, content=b"ok\n"):
    import importlib.util
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_ARTIFACT_UPLOAD", "1")
    spec = importlib.util.spec_from_file_location("win_daemon_upload", ROOT / "scripts/windows_worker/daemon.py")
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    monkeypatch.chdir(work)
    monkeypatch.setattr(d, "STATE_DIR", tmp_path / "wstate")
    monkeypatch.setattr(d, "load_config", lambda: {"WORKER_ID": "WINDOWS-01"})
    monkeypatch.setattr(d, "acquire_lock", lambda w: tmp_path / "lock")
    monkeypatch.setattr(d, "is_resource_pressure_high", lambda: False)
    monkeypatch.setattr(d.time, "sleep", lambda s: None)
    monkeypatch.setattr(d.urllib.request, "urlopen", harness)

    class PS:
        pid, returncode = 7, 0

        def __init__(self, *a, **k):
            executions.append(1)
            (work / "win.txt").write_bytes(content)

        def communicate(self, timeout=None):
            return "", ""
    monkeypatch.setattr(d.subprocess, "Popen", PS)
    return d


def run_loop(d):
    with pytest.raises(StopLoop):
        d.loop()


def test_windows_worker_uploads_and_verifier_reconciles(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    executions = []
    d = windows_daemon(tmp_path, monkeypatch, Harness(http, max_calls=6), executions)
    run_loop(d)
    task = srv.load_state()["tasks"]["w1"]
    assert task["status"] == "RESULT_RECEIVED" and executions == [1]
    [ref] = task["result"]["artifacts"]
    assert ref["artifact_id"].startswith("art-") and ref["size"] == 3
    # Remove the worker-local file: verification must rely on the server copy only.
    (tmp_path / "work" / "win.txt").unlink()
    [pending] = http.get("/tasks/pending_verification", headers=VERIFIER).get_json()["tasks"]
    v = load_verifier(monkeypatch)
    verdict = v.verify_artifacts(pending, pending["result"], fetch=client_fetch(http))
    assert verdict == "PASS"
    r = http.post("/tasks/verify", headers=VERIFIER, json={
        "task_id": "w1", "result_id": ref and pending["result"]["result_id"], "verifier_id": "VERIFIER-01",
        "verdict": verdict, "artifacts": pending["result"]["artifacts"]})
    assert r.get_json()["status"] == "RECONCILED"


def test_windows_transient_upload_failure_keeps_result_without_reexecution(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    executions = []
    d = windows_daemon(tmp_path, monkeypatch, Harness(http, faults=["network", 503], max_calls=12), executions)
    run_loop(d)
    assert executions == [1]
    assert srv.load_state()["tasks"]["w1"]["status"] == "RESULT_RECEIVED"


def test_windows_artifact_changed_after_hashing_is_released_not_uploaded(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    executions = []
    harness = Harness(http, max_calls=8)
    d = windows_daemon(tmp_path, monkeypatch, harness, executions)
    real = d.build_result_payload

    def build_then_modify(task, result, config):
        payload = real(task, result, config)
        (tmp_path / "work" / "win.txt").write_bytes(b"changed")
        return payload
    monkeypatch.setattr(d, "build_result_payload", build_then_modify)
    run_loop(d)
    assert "/artifacts" not in harness.calls
    state = srv.load_state()
    assert state["tasks"]["w1"]["status"] == "HUMAN_REQUIRED"
    assert state["workers"]["WINDOWS-01"]["current_task"] is None


def test_windows_upload_disabled_by_default(tmp_path, monkeypatch):
    srv, http = setup(tmp_path, monkeypatch)
    executions = []
    harness = Harness(http, max_calls=5)
    d = windows_daemon(tmp_path, monkeypatch, harness, executions)
    monkeypatch.delenv("COURIER_ARTIFACT_UPLOAD")
    run_loop(d)
    assert "/artifacts" not in harness.calls
    assert "artifact_id" not in srv.load_state()["tasks"]["w1"]["result"]["artifacts"][0]


# ---------------------------------------------------------------- Mac worker end to end

def test_mac_worker_uploads_and_verifier_reconciles(tmp_path, monkeypatch):
    import importlib.util
    srv, http = setup(tmp_path, monkeypatch, worker="MAC-01", target="mac", caps=("macos",), artifacts=("effect.txt",))
    spec = importlib.util.spec_from_file_location("mac_daemon_upload", ROOT / "scripts/mac_worker/daemon.py")
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    for sub in ("state", "logs"):
        (tmp_path / f"m{sub}").mkdir()
    monkeypatch.setattr(d, "STATE_DIR", tmp_path / "mstate")
    monkeypatch.setattr(d, "LOGS_DIR", tmp_path / "mlogs")
    monkeypatch.setattr(d, "load_config", lambda: {"COURIER_SERVER": "http://x", "WORKER_ID": "MAC-01",
                                                   "COURIER_API_KEY": "test-secret", "ARTIFACT_UPLOAD": True,
                                                   "POLL_INTERVAL_SECONDS": 0})
    monkeypatch.setattr(d.time, "sleep", lambda s: None)
    work = tmp_path / "mwork"
    work.mkdir()
    monkeypatch.chdir(work)
    calls, executions = [], []

    def post(config, endpoint, data):
        calls.append(endpoint)
        if len(calls) > 6:
            raise StopLoop()
        r = http.post(endpoint, headers=WORKER, json=data)
        return (r.get_json(), None) if r.status_code < 400 else (None, f"HTTP Error {r.status_code}: x")

    def upload_(config, meta, data):
        calls.append("/artifacts")
        r = http.post("/artifacts", headers={**WORKER, "X-Courier-Artifact": json.dumps(meta)},
                      data=data, content_type="application/octet-stream")
        return (r.get_json(), None) if r.status_code < 400 else (None, f"HTTP Error {r.status_code}: x")

    def execute(packet, config):
        executions.append(1)
        (work / "effect.txt").write_text("done\n")
        return {"status": "SUCCESS", "stdout": "", "stderr": "", "execution_mode": "NATIVE"}

    monkeypatch.setattr(d, "http_post", post)
    monkeypatch.setattr(d, "http_upload", upload_)
    monkeypatch.setattr(d, "run_native", execute)
    monkeypatch.setattr(d, "run_agy", execute)
    with pytest.raises(StopLoop):
        d.loop()
    task = srv.load_state()["tasks"]["w1"]
    assert executions == [1] and task["status"] == "RESULT_RECEIVED"
    [ref] = task["result"]["artifacts"]
    assert ref["artifact_id"].startswith("art-")
    (work / "effect.txt").unlink()
    [pending] = http.get("/tasks/pending_verification", headers=VERIFIER).get_json()["tasks"]
    assert load_verifier(monkeypatch).verify_artifacts(pending, pending["result"], fetch=client_fetch(http)) == "PASS"
