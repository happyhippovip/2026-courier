"""Contract: cannon storage foundations (priorities 1+2).

Pins the untested single-flight lock, atomic durable writes, owned-path
confinement, and loud corrupt-state reads that Duplicate-Execution and
Lost-Results protection rests on. Pure stdlib; ROOT is redirected into
tmp_path so no repo file is touched.
"""
import json

import pytest

from app.cannon import storage


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    return tmp_path


def test_second_live_lock_holder_is_rejected(root):
    with storage.InstanceLock(root / "run"):
        with pytest.raises(RuntimeError, match="CANNON_ALREADY_RUNNING"):
            with storage.InstanceLock(root / "run"):
                pass


def test_lock_released_after_exit_allows_takeover(root):
    with storage.InstanceLock(root / "run"):
        pass
    with storage.InstanceLock(root / "run"):
        pass


def test_atomic_write_reads_back_identical_payload(root):
    path = root / "queue" / "state.json"
    payload = {"tasks": {"t1": {"status": "CLAIMED"}}, "n": 3}
    storage.atomic(path, payload)
    assert storage.read(path) == payload
    assert not path.with_name(path.name + ".tmp").exists()


def test_owned_rejects_outside_paths_and_root_itself(root, tmp_path):
    with pytest.raises(ValueError, match="outside owned workspace"):
        storage.owned(tmp_path.parent / "escape.json")
    with pytest.raises(ValueError, match="outside owned workspace"):
        storage.owned(root)


def test_corrupt_state_is_loud_never_empty(root):
    path = root / "state.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        storage.read(path)
    assert storage.read(root / "missing.json") is None
