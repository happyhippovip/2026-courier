import json
import os
import pytest
from pathlib import Path
from flask import Flask

from scripts.artifact_store import (
    ArtifactStore,
    ArtifactError,
    _atomic_write,
    verify_uploaded_artifact,
    create_blueprint,
)

BINDING = {
    "goal_id": "g",
    "task_id": "t",
    "attempt_id": "t:attempt:1",
    "dispatch_id": "dispatch-1",
    "worker_id": "WINDOWS-01",
}


def test_atomic_write_exception(tmp_path, monkeypatch):
    path = tmp_path / "test_file.txt"
    
    # Mock os.replace to raise an Exception so we trigger the except BaseException block
    def mock_replace(src, dst):
        raise RuntimeError("simulated failure")
        
    monkeypatch.setattr(os, "replace", mock_replace)
    
    with pytest.raises(RuntimeError, match="simulated failure"):
        _atomic_write(path, b"data")
        
    # The temp file should have been unlinked
    assert not any(tmp_path.iterdir())


def test_read_bytes_unknown_artifact(tmp_path):
    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactError, match="unknown artifact_id"):
        store.read_bytes("art-0000000000000000000000000000000000000000000000000000000000000000")


def test_check_reference_size_mismatch(tmp_path):
    store = ArtifactStore(tmp_path)
    data = b"some data"
    record = store.put(data, name="x.txt", binding=BINDING)
    
    ref = {
        "artifact_id": record["artifact_id"],
        "path": "x.txt",
        "sha256": record["sha256"],
        "size": 9999,  # Mismatch
    }
    
    with pytest.raises(ArtifactError, match="artifact size mismatch"):
        store.check_reference(ref, BINDING)


def test_verify_uploaded_artifact_size_mismatch():
    data = b"data"
    record = {"sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7", "size": 4, "name": "x.txt", "artifact_id": "art-123"}
    ref = {"sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7", "size": 999}
    
    ok, msg = verify_uploaded_artifact(data, record, ref, BINDING)
    assert not ok
    assert msg == "size mismatch"


def test_verify_uploaded_artifact_reference_mismatch():
    data = b"data"
    record = {"sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7", "size": 4, "name": "x.txt", "artifact_id": "art-123"}
    ref = {"sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7", "size": 4, "path": "y.txt", "artifact_id": "art-123"}
    
    ok, msg = verify_uploaded_artifact(data, record, ref, BINDING)
    assert not ok
    assert msg == "reference mismatch"


@pytest.fixture
def app(tmp_path):
    store = ArtifactStore(tmp_path)
    app = Flask(__name__)
    
    def worker_auth(f):
        return f

    def verifier_auth(f):
        return f

    def task_lookup(task_id):
        if task_id == "t":
            return {
                "status": "DISPATCHED",
                "artifacts": ["x.txt"],
                **BINDING
            }
        elif task_id == "not-dispatched":
            return {
                "status": "DONE",
                **BINDING
            }
        return None

    bp = create_blueprint(
        store, 
        worker_auth=worker_auth, 
        verifier_auth=verifier_auth, 
        task_lookup=task_lookup
    )
    app.register_blueprint(bp)
    
    # Store for easy access in tests
    app.store = store
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_flask_upload_artifact_success(client, app):
    meta = {
        "task_id": "t",
        "name": "x.txt",
        "sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7",
        "size": 4,
        **BINDING
    }
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 201
    data = resp.json
    assert data["artifact_id"] is not None


def test_flask_upload_artifact_no_header(client):
    resp = client.post("/artifacts", data=b"data")
    assert resp.status_code == 400
    assert "required" in resp.json["error"]


def test_flask_upload_artifact_bad_header(client):
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": "not-json"})
    assert resp.status_code == 400


def test_flask_upload_artifact_too_large(client, app):
    app.store.max_bytes = 2
    meta = {"task_id": "t", "name": "x.txt"}
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 413


def test_flask_upload_artifact_task_not_found(client):
    meta = {"task_id": "unknown"}
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 409


def test_flask_upload_artifact_task_not_dispatched(client):
    meta = {"task_id": "not-dispatched"}
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 409


def test_flask_upload_artifact_binding_mismatch(client):
    meta = {
        "task_id": "t",
        "name": "x.txt",
        **BINDING
    }
    meta["worker_id"] = "WRONG"
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 400
    assert "mismatch" in resp.json["error"]


def test_flask_upload_artifact_unexpected_name(client):
    meta = {
        "task_id": "t",
        "name": "y.txt",
        **BINDING
    }
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 400
    assert "not expected" in resp.json["error"]


def test_flask_upload_artifact_artifact_error(client):
    meta = {
        "task_id": "t",
        "name": "x.txt",
        "sha256": "wrong",  # Claim wrong sha256
        **BINDING
    }
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 400
    assert "claimed sha256" in resp.json["error"]


def test_flask_artifact_meta_success(client, app):
    record = app.store.put(b"data", name="x.txt", binding=BINDING)
    resp = client.get(f"/artifacts/{record['artifact_id']}/meta")
    assert resp.status_code == 200
    assert resp.json["artifact_id"] == record["artifact_id"]


def test_flask_artifact_meta_not_found(client, app):
    # Valid artifact format, but doesn't exist
    resp = client.get("/artifacts/art-0000000000000000000000000000000000000000000000000000000000000000/meta")
    assert resp.status_code == 404


def test_flask_artifact_meta_invalid_id(client, app):
    resp = client.get("/artifacts/invalid/meta")
    assert resp.status_code == 400


def test_flask_artifact_bytes_success(client, app):
    record = app.store.put(b"data", name="x.txt", binding=BINDING)
    resp = client.get(f"/artifacts/{record['artifact_id']}")
    assert resp.status_code == 200
    assert resp.data == b"data"


def test_flask_artifact_bytes_not_found(client, app):
    resp = client.get("/artifacts/invalid")
    assert resp.status_code == 404


def test_flask_upload_artifact_meta_not_dict(client):
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": "[]"})
    assert resp.status_code == 400
