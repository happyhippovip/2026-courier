"""Task/Result parcel schema + claiming (desktop overlay, decoupled)."""
import pytest

from courier_desktop import task_schema as parcels


def task(**changes):
    parcel = {"goal_id": "goal-1", "task_id": "task-1", "attempt_id": "a-1",
              "dispatch_id": "d-1", "status": "NEW", "title": "demo parcel"}
    parcel.update(changes)
    return parcel


def result(**changes):
    parcel = {"result_id": "result-d-1", "task_id": "task-1", "dispatch_id": "d-1",
              "status": "READY", "artifacts": []}
    parcel.update(changes)
    return parcel


def test_validate_task_parcel_accepts_wellformed():
    assert parcels.validate_task_parcel(task())["task_id"] == "task-1"


@pytest.mark.parametrize("field", ["goal_id", "task_id", "attempt_id", "dispatch_id"])
def test_validate_task_parcel_rejects_missing_identity(field):
    bad = task()
    del bad[field]
    with pytest.raises(ValueError, match="must be a non-empty string"):
        parcels.validate_task_parcel(bad)


def test_validate_task_parcel_rejects_unknown_status():
    with pytest.raises(ValueError, match="unknown task status"):
        parcels.validate_task_parcel(task(status="FLYING"))


def test_validate_task_parcel_rejects_nondict():
    with pytest.raises(ValueError, match="must be a JSON object"):
        parcels.validate_task_parcel(["task-1"])


def test_validate_result_parcel_accepts_confined_artifact(tmp_path):
    digest = "a" * 64
    parcel = result(artifacts=[{"path": "evidence.json", "sha256": digest}])
    assert parcels.validate_result_parcel(parcel)["result_id"] == "result-d-1"


@pytest.mark.parametrize("evil", ["/etc/passwd", "../out.json", "C:\\Win\\e.json", "", None])
def test_validate_result_parcel_rejects_unsafe_artifact_path(evil):
    parcel = result(artifacts=[{"path": evil, "sha256": "a" * 64}])
    with pytest.raises(ValueError, match="unsafe artifact path"):
        parcels.validate_result_parcel(parcel)


def test_validate_result_parcel_rejects_bad_fingerprint():
    parcel = result(artifacts=[{"path": "e.json", "sha256": "ZZZ"}])
    with pytest.raises(ValueError, match="invalid artifact fingerprint"):
        parcels.validate_result_parcel(parcel)


def test_claim_task_moves_new_to_claimed():
    claimed = parcels.claim_task(task(), "MUSE-1")
    assert claimed["status"] == "CLAIMED"
    assert claimed["worker_id"] == "MUSE-1"
    assert task()["status"] == "NEW"


@pytest.mark.parametrize("status", ["CLAIMED", "RUNNING", "DONE", "BLOCKED", "FAILED"])
def test_claim_task_rejects_non_new(status):
    with pytest.raises(ValueError, match="not claimable"):
        parcels.claim_task(task(status=status), "MUSE-1")


def test_claim_task_rejects_empty_worker():
    with pytest.raises(ValueError, match="worker_id"):
        parcels.claim_task(task(), "")
