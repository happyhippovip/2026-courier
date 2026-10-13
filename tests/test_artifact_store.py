import hashlib

import pytest

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from functools import wraps
import json
from flask import Flask

from scripts.artifact_store import (
    ArtifactError,
    ArtifactStore,
    artifact_id_for,
    is_safe_artifact_name,
    verify_uploaded_artifact,
    create_blueprint,
    BINDING_FIELDS,
    DEFAULT_MAX_BYTES,
)

BINDING = {"goal_id": "g", "task_id": "t", "attempt_id": "t:attempt:1",
           "dispatch_id": "dispatch-1", "worker_id": "WINDOWS-01"}


def store(tmp_path, limit=1024):
    return ArtifactStore(tmp_path / "store", max_bytes=limit)


def test_server_hashes_bytes_and_binds_record(tmp_path):
    s = store(tmp_path)
    rec = s.put(b"hello\n", name="out.txt", binding=BINDING)
    assert rec["sha256"] == hashlib.sha256(b"hello\n").hexdigest() and rec["size"] == 6
    assert rec["artifact_id"] == artifact_id_for(BINDING, "out.txt", rec["sha256"])
    assert s.read_bytes(rec["artifact_id"]) == b"hello\n"
    assert {k: rec[k] for k in BINDING} == BINDING


def test_upload_is_idempotent_and_content_addressed(tmp_path):
    s = store(tmp_path)
    a = s.put(b"x", name="a.txt", binding=BINDING)
    assert s.put(b"x", name="a.txt", binding=BINDING) == a
    other = s.put(b"x", name="a.txt", binding=dict(BINDING, dispatch_id="dispatch-2"))
    assert other["artifact_id"] != a["artifact_id"]
    assert len(list((tmp_path / "store" / "blobs").rglob("*"))) == 2  # one dir + one blob


@pytest.mark.parametrize("claim", [{"claimed_sha256": "0" * 64}, {"claimed_size": 99}])
def test_claimed_hash_or_size_must_match_uploaded_bytes(tmp_path, claim):
    with pytest.raises(ArtifactError):
        store(tmp_path).put(b"data", name="a.txt", binding=BINDING, **claim)


def test_size_limit_is_enforced(tmp_path):
    with pytest.raises(ArtifactError):
        store(tmp_path, limit=3).put(b"four", name="a.txt", binding=BINDING)


@pytest.mark.parametrize("name", ["/etc/passwd", "../x", "a/../../x", "C:\\x", "C:x", "\\\\srv\\share\\x",
                                  "..\\x", "", "a\x00b"])
def test_unsafe_names_rejected(tmp_path, name):
    assert not is_safe_artifact_name(name)
    with pytest.raises(ArtifactError):
        store(tmp_path).put(b"x", name=name, binding=BINDING)


@pytest.mark.parametrize("field", list(BINDING))
def test_binding_is_required(tmp_path, field):
    with pytest.raises(ArtifactError):
        store(tmp_path).put(b"x", name="a.txt", binding=dict(BINDING, **{field: ""}))


def test_check_reference_enforces_exact_binding(tmp_path):
    s = store(tmp_path)
    rec = s.put(b"x", name="a.txt", binding=BINDING)
    ref = {"path": "a.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": 1}
    s.check_reference(ref, BINDING)
    for field in BINDING:
        with pytest.raises(ArtifactError):
            s.check_reference(ref, dict(BINDING, **{field: "other"}))
    with pytest.raises(ArtifactError):
        s.check_reference(dict(ref, path="b.txt"), BINDING)
    with pytest.raises(ArtifactError):
        s.check_reference(dict(ref, artifact_id="art-" + "0" * 64), BINDING)


def test_invalid_artifact_id_cannot_escape_store(tmp_path):
    with pytest.raises(ArtifactError):
        store(tmp_path).get_record("../../etc/passwd")


def test_verifier_detects_tampered_server_copy(tmp_path):
    s = store(tmp_path)
    rec = s.put(b"original", name="a.txt", binding=BINDING)
    ref = {"path": "a.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": rec["size"]}
    assert verify_uploaded_artifact(s.read_bytes(rec["artifact_id"]), rec, ref, BINDING) == (True, "ok")
    blob = tmp_path / "store" / "blobs" / rec["sha256"][:2] / rec["sha256"]
    blob.write_bytes(b"tampered")
    ok, reason = verify_uploaded_artifact(s.read_bytes(rec["artifact_id"]), rec, ref, BINDING)
    assert not ok and reason == "hash mismatch"
    ok, reason = verify_uploaded_artifact(b"original", rec, ref, dict(BINDING, attempt_id="t:attempt:2"))
    assert not ok and "attempt_id" in reason


from scripts.integration_contract import ContractError, validate_durable_result

TASK = dict(BINDING)


def durable(artifacts):
    return {**BINDING, "run_id": "r", "result_id": "result-1", "status": "SUCCESS", "artifacts": artifacts}


def test_contract_accepts_path_only_and_uploaded_references():
    validate_durable_result(TASK, durable([{"path": "a.txt", "sha256": "a" * 64}]))
    validate_durable_result(TASK, durable([{"path": "a.txt", "sha256": "a" * 64,
                                           "artifact_id": "art-" + "b" * 64, "size": 3}]))


@pytest.mark.parametrize("art", [
    {"path": "a.txt", "sha256": "a" * 64, "artifact_id": "art-x", "size": 3},
    {"path": "a.txt", "sha256": "a" * 64, "artifact_id": "art-" + "b" * 64, "size": -1},
    {"path": "a.txt", "sha256": "a" * 64, "artifact_id": "art-" + "b" * 64, "size": True},
    {"path": "a.txt", "sha256": "a" * 64, "artifact_id": "art-" + "b" * 64},
    {"path": "C:\\x.txt", "sha256": "a" * 64},
    {"path": "C:x.txt", "sha256": "a" * 64},
    {"path": "..\\x.txt", "sha256": "a" * 64},
])
def test_contract_rejects_malformed_references_and_windows_paths(art):
    with pytest.raises(ContractError):
        validate_durable_result(TASK, durable([art]))


def test_artifact_store_from_env_defaults(monkeypatch):
    monkeypatch.delenv("COURIER_ARTIFACT_DIR", raising=False)
    monkeypatch.delenv("COURIER_ARTIFACT_MAX_BYTES", raising=False)
    s = ArtifactStore.from_env()
    assert s.root == Path("server/state/artifacts")
    assert s.max_bytes == DEFAULT_MAX_BYTES


def test_artifact_store_from_env_custom(monkeypatch, tmp_path):
    custom_dir = str(tmp_path / "custom_artifacts")
    monkeypatch.setenv("COURIER_ARTIFACT_DIR", custom_dir)
    monkeypatch.setenv("COURIER_ARTIFACT_MAX_BYTES", "4096")
    s = ArtifactStore.from_env()
    assert s.root == Path(custom_dir)
    assert s.max_bytes == 4096


def test_corrupt_stored_blob_detected_on_put(tmp_path):
    s = store(tmp_path)
    data = b"hello blob"
    sha = hashlib.sha256(data).hexdigest()
    blob_path = s._blob_path(sha)
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_bytes(b"tampered pre-existing blob")
    with pytest.raises(ArtifactError, match="stored blob is corrupt"):
        s.put(data, name="out.txt", binding=BINDING)


def test_artifact_record_conflict_detected_on_put(tmp_path):
    s = store(tmp_path)
    data = b"hello record"
    sha = hashlib.sha256(data).hexdigest()
    art_id = artifact_id_for(BINDING, "out.txt", sha)
    rec_path = s._record_path(art_id)
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(json.dumps({"conflict": True}), encoding="utf-8")
    with pytest.raises(ArtifactError, match="artifact record conflict"):
        s.put(data, name="out.txt", binding=BINDING)


def test_read_bytes_missing_blob_file(tmp_path):
    s = store(tmp_path)
    rec = s.put(b"content", name="f.txt", binding=BINDING)
    blob_path = s._blob_path(rec["sha256"])
    blob_path.unlink()
    with pytest.raises(ArtifactError, match="artifact bytes missing"):
        s.read_bytes(rec["artifact_id"])


def test_read_bytes_unknown_artifact_id(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ArtifactError, match="unknown artifact_id"):
        s.read_bytes("art-" + "1" * 64)


def test_check_reference_unknown_artifact_id(tmp_path):
    s = store(tmp_path)
    ref = {"path": "a.txt", "sha256": "0" * 64, "artifact_id": "art-" + "0" * 64}
    with pytest.raises(ArtifactError, match="unknown artifact_id"):
        s.check_reference(ref, BINDING)


def test_check_reference_size_mismatch(tmp_path):
    s = store(tmp_path)
    rec = s.put(b"hello", name="a.txt", binding=BINDING)
    ref = {"path": "a.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": 999}
    with pytest.raises(ArtifactError, match="artifact size mismatch"):
        s.check_reference(ref, BINDING)


@pytest.mark.parametrize("mismatched_field", list(BINDING))
def test_verify_uploaded_artifact_all_binding_field_mismatches(tmp_path, mismatched_field):
    s = store(tmp_path)
    data = b"verified payload"
    rec = s.put(data, name="doc.txt", binding=BINDING)
    ref = {"path": "doc.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": rec["size"]}
    mismatched_task = dict(BINDING, **{mismatched_field: "other_value"})
    ok, reason = verify_uploaded_artifact(data, rec, ref, mismatched_task)
    assert not ok
    assert reason == f"{mismatched_field} mismatch"


def test_verify_uploaded_artifact_size_mismatch(tmp_path):
    s = store(tmp_path)
    data = b"correct payload"
    rec = s.put(data, name="doc.txt", binding=BINDING)
    ref = {"path": "doc.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": 999}
    ok, reason = verify_uploaded_artifact(data, rec, ref, BINDING)
    assert not ok and reason == "size mismatch"


def test_verify_uploaded_artifact_reference_mismatch(tmp_path):
    s = store(tmp_path)
    data = b"correct payload"
    rec = s.put(data, name="doc.txt", binding=BINDING)
    ref = {"path": "other_doc.txt", "sha256": rec["sha256"], "artifact_id": rec["artifact_id"], "size": rec["size"]}
    ok, reason = verify_uploaded_artifact(data, rec, ref, BINDING)
    assert not ok and reason == "reference mismatch"

    ref_bad_id = {"path": "doc.txt", "sha256": rec["sha256"], "artifact_id": "art-" + "f" * 64, "size": rec["size"]}
    ok2, reason2 = verify_uploaded_artifact(data, rec, ref_bad_id, BINDING)
    assert not ok2 and reason2 == "reference mismatch"


def test_create_blueprint_endpoints(tmp_path):
    s = store(tmp_path, limit=100)
    task_db = {
        "t": {
            **BINDING,
            "status": "DISPATCHED",
            "artifacts": [{"path": "result.json"}, "logs.txt"],
        }
    }

    def noop_auth(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper

    bp = create_blueprint(
        s,
        worker_auth=noop_auth,
        verifier_auth=noop_auth,
        task_lookup=lambda tid: task_db.get(tid),
    )

    app = Flask(__name__)
    app.register_blueprint(bp)
    client = app.test_client()

    # 1. POST /artifacts without X-Courier-Artifact header
    resp = client.post("/artifacts", data=b"data")
    assert resp.status_code == 400
    assert "metadata header is required" in resp.get_json()["error"]

    # 2. POST /artifacts with invalid JSON in header
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": "not-json"})
    assert resp.status_code == 400
    assert "metadata header is required" in resp.get_json()["error"]

    # 3. POST /artifacts with non-dict JSON in header
    resp = client.post("/artifacts", data=b"data", headers={"X-Courier-Artifact": "[1, 2]"})
    assert resp.status_code == 400

    # 4. POST /artifacts exceeding size limit
    oversized = b"x" * 150
    meta = {**BINDING, "name": "result.json", "size": len(oversized)}
    resp = client.post("/artifacts", data=oversized, headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 413

    # 5. POST /artifacts for unknown task
    meta_unknown = dict(meta, task_id="nonexistent")
    resp = client.post("/artifacts", data=b"valid", headers={"X-Courier-Artifact": json.dumps(meta_unknown)})
    assert resp.status_code == 409
    assert "not awaiting artifacts" in resp.get_json()["error"]

    # 6. POST /artifacts for task not in DISPATCHED status
    task_db["t"]["status"] = "DONE"
    resp = client.post("/artifacts", data=b"valid", headers={"X-Courier-Artifact": json.dumps(meta)})
    assert resp.status_code == 409
    task_db["t"]["status"] = "DISPATCHED"

    # 7. POST /artifacts with binding mismatch
    meta_mismatch = dict(meta, worker_id="OTHER_WORKER")
    resp = client.post("/artifacts", data=b"valid", headers={"X-Courier-Artifact": json.dumps(meta_mismatch)})
    assert resp.status_code == 400
    assert "worker_id mismatch" in resp.get_json()["error"]

    # 8. POST /artifacts with unexpected artifact name
    meta_unexpected = dict(meta, name="unexpected.exe")
    resp = client.post("/artifacts", data=b"valid", headers={"X-Courier-Artifact": json.dumps(meta_unexpected)})
    assert resp.status_code == 400
    assert "artifact name is not expected" in resp.get_json()["error"]

    # 9. POST /artifacts with store.put error (e.g. unsafe name)
    task_db["t"]["artifacts"].append("../escape.txt")
    meta_unsafe = dict(meta, name="../escape.txt")
    resp = client.post("/artifacts", data=b"valid", headers={"X-Courier-Artifact": json.dumps(meta_unsafe)})
    assert resp.status_code == 400
    assert "unsafe artifact name" in resp.get_json()["error"]

    # 10. Valid POST /artifacts upload (string artifact in task)
    payload = b'{"status": "ok"}'
    meta_valid = {
        **BINDING,
        "name": "logs.txt",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    resp = client.post("/artifacts", data=payload, headers={"X-Courier-Artifact": json.dumps(meta_valid)})
    assert resp.status_code == 201
    created = resp.get_json()
    assert created["name"] == "logs.txt"
    art_id = created["artifact_id"]

    # 11. GET /artifacts/<id>/meta with valid id
    resp_meta = client.get(f"/artifacts/{art_id}/meta")
    assert resp_meta.status_code == 200
    assert resp_meta.get_json() == created

    # 12. GET /artifacts/<id>/meta with unknown id
    resp_meta_unknown = client.get(f"/artifacts/art-{'0'*64}/meta")
    assert resp_meta_unknown.status_code == 404

    # 13. GET /artifacts/<id>/meta with malformed id
    resp_meta_bad = client.get("/artifacts/not-an-artifact-id/meta")
    assert resp_meta_bad.status_code == 400

    # 14. GET /artifacts/<id> with valid id
    resp_bytes = client.get(f"/artifacts/{art_id}")
    assert resp_bytes.status_code == 200
    assert resp_bytes.data == payload
    assert resp_bytes.mimetype == "application/octet-stream"

    # 15. GET /artifacts/<id> with unknown id
    resp_bytes_unknown = client.get(f"/artifacts/art-{'0'*64}")
    assert resp_bytes_unknown.status_code == 404
