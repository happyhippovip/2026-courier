"""P9 hardening for courier_worker.adapter_bridge: atomic-write durability.

Tests only; no behavior change. Offline: filesystem via tmp_path, no network,
no credentials.

Scope is deliberately narrow (sibling P9 runs pin paths, validation,
cleanup, round-trip, sanitize, effect-key and argv aspects elsewhere): this
file pins that request writes are atomic -- a failed write never leaves a
partial request file or tmp litter, and an overwrite fully replaces the
previous envelope.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge


def _spec(dispatch_id: str = "d-1", **overrides) -> SimpleNamespace:
    base = {
        "dispatch_id": dispatch_id,
        "adapter": "synthetic",
        "params": {"steps": 1},
        "attempt": 1,
        "task_id": "t-1",
        "effect_key": "key.1:ok",
        "artifact_dir": os.path.join("artifacts", dispatch_id),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _dir_files(path: str) -> list:
    if not os.path.isdir(path):
        return []
    return sorted(os.listdir(path))


# -- overwrite atomicity ----------------------------------------------------

def test_write_request_overwrite_fully_replaces(tmp_path) -> None:
    home = str(tmp_path)
    adapter_bridge.write_request(home, _spec("d-1", params={"steps": 1}, attempt=1))
    adapter_bridge.write_request(home, _spec("d-1", params={"steps": 7}, attempt=2))
    with open(adapter_bridge.request_path(home, "d-1"), encoding="utf-8") as fh:
        raw = fh.read()
    body = json.loads(raw)  # a partial overwrite would not parse
    assert body == {
        "adapter": "synthetic",
        "params": {"steps": 7},
        "attempt": 2,
        "task_id": "t-1",
        "dispatch_id": "d-1",
        "effect_key": "key.1:ok",
        "workdir": os.path.join("artifacts", "d-1"),
        "report": adapter_bridge.report_path(home, "d-1"),
    }


def test_write_request_leaves_no_tmp_litter(tmp_path) -> None:
    home = str(tmp_path)
    adapter_bridge.write_request(home, _spec("d-2"))
    assert _dir_files(os.path.join(home, "run", "requests")) == ["d-2.json"]


# -- failure atomicity ------------------------------------------------------

def test_atomic_json_failure_leaves_no_file_or_tmp(tmp_path) -> None:
    target = str(tmp_path / "sub" / "req.json")
    with pytest.raises((TypeError, ValueError)):
        adapter_bridge._atomic_json(target, {"x": {1, 2}})  # set is not JSON
    assert not os.path.exists(target)
    assert _dir_files(str(tmp_path / "sub")) == []


def test_write_request_failure_is_atomic(tmp_path) -> None:
    home = str(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        adapter_bridge.write_request(home, _spec("d-3", params={"x": {1, 2}}))
    assert not os.path.exists(adapter_bridge.request_path(home, "d-3"))
    assert _dir_files(os.path.join(home, "run", "requests")) == []


def test_write_request_failure_still_drops_stale_report(tmp_path) -> None:
    home = str(tmp_path)
    stale = adapter_bridge.report_path(home, "d-4")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success"}, fh)
    with pytest.raises((TypeError, ValueError)):
        adapter_bridge.write_request(home, _spec("d-4", params={"x": {1, 2}}))
    # The stale report is unlinked before the write is attempted, so a
    # failed write can never resurrect an older outcome for this dispatch.
    assert not os.path.exists(stale)
    assert not os.path.exists(adapter_bridge.request_path(home, "d-4"))


# -- durability details -----------------------------------------------------

def test_atomic_json_writes_sorted_keys(tmp_path) -> None:
    target = str(tmp_path / "req.json")
    adapter_bridge._atomic_json(target, {"z": 1, "a": {"y": 2, "b": 3}})
    with open(target, encoding="utf-8") as fh:
        body = json.load(fh)
    assert list(body) == ["a", "z"]
    assert list(body["a"]) == ["b", "y"]


def test_atomic_json_creates_missing_parent_dirs(tmp_path) -> None:
    target = str(tmp_path / "deep" / "nested" / "req.json")
    adapter_bridge._atomic_json(target, {"outcome": "success"})
    with open(target, encoding="utf-8") as fh:
        assert json.load(fh) == {"outcome": "success"}
