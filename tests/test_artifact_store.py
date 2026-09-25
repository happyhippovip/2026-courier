import hashlib

import pytest

from scripts.artifact_store import (ArtifactError, ArtifactStore, artifact_id_for, is_safe_artifact_name,
                                    verify_uploaded_artifact)

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
