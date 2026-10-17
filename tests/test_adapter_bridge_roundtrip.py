"""P9 hardening for courier_worker.adapter_bridge: request/report round-trip.

Focus: the host-owned filesystem contract under <home> (offline only).
- path helpers never escape their directory, even for hostile dispatch ids;
- write_request persists exactly what the runner must do and drops any
  stale report for the same dispatch;
- read_report returns None for absent/malformed/out-of-contract reports;
- cleanup removes only this dispatch's files and is idempotent.

No network, no credentials, no behaviour change to the module under test.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge


def _spec(dispatch_id: str = "d-1") -> SimpleNamespace:
    return SimpleNamespace(
        dispatch_id=dispatch_id,
        adapter="synthetic",
        params={"steps": 1},
        attempt=1,
        task_id="t-1",
        effect_key="key.1:ok",
        artifact_dir=os.path.join("artifacts", dispatch_id),
    )


# -- _safe ---------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc-XYZ_012.9", "abc-XYZ_012.9"),
        ("a/b\\c:d e", "a_b_c_d_e"),
        ("", "unnamed"),
        ("../escape", ".._escape"),
        ("x" * 300, "x" * 300),  # _safe does not truncate; length is bounded elsewhere
    ],
)
def test_safe_sanitizes(raw: str, expected: str) -> None:
    assert adapter_bridge._safe(raw) == expected


# -- request_path / report_path ------------------------------------------

def test_paths_stay_in_their_directories(tmp_path) -> None:
    home = str(tmp_path)
    for dispatch in ("d-1", "../escape", "a/b", "d 1:x"):
        for path_fn, leaf in (
            (adapter_bridge.request_path, "requests"),
            (adapter_bridge.report_path, "reports"),
        ):
            path = path_fn(home, dispatch)
            assert os.path.dirname(path) == os.path.join(home, "run", leaf)
            assert path.endswith(".json")
            assert os.sep not in os.path.basename(path)


def test_request_and_report_paths_share_stem(tmp_path) -> None:
    home = str(tmp_path)
    stem = os.path.basename(adapter_bridge.request_path(home, "d-9"))[: -len(".json")]
    assert os.path.basename(adapter_bridge.report_path(home, "d-9")) == stem + ".json"


def test_runner_argv_points_at_repo_runner(tmp_path) -> None:
    home = str(tmp_path)
    exe, script, request = adapter_bridge.runner_argv(home, "d-2")
    assert exe == sys.executable
    assert os.path.isabs(script)
    assert os.path.basename(script) == "adapter_runner.py"
    assert os.path.isfile(script)
    assert request == adapter_bridge.request_path(home, "d-2")


# -- write_request ----------------------------------------------------------

def test_write_request_persists_runner_envelope(tmp_path) -> None:
    home = str(tmp_path)
    spec = _spec("d-3")
    path = adapter_bridge.write_request(home, spec)
    assert path == adapter_bridge.request_path(home, "d-3")
    with open(path, encoding="utf-8") as fh:
        body = json.load(fh)
    assert body == {
        "adapter": "synthetic",
        "params": {"steps": 1},
        "attempt": 1,
        "task_id": "t-1",
        "dispatch_id": "d-3",
        "effect_key": "key.1:ok",
        "workdir": spec.artifact_dir,
        "report": adapter_bridge.report_path(home, "d-3"),
    }


def test_write_request_drops_stale_report(tmp_path) -> None:
    home = str(tmp_path)
    stale = adapter_bridge.report_path(home, "d-4")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success"}, fh)
    adapter_bridge.write_request(home, _spec("d-4"))
    assert not os.path.exists(stale)


def test_write_request_is_repeatable(tmp_path) -> None:
    home = str(tmp_path)
    first = adapter_bridge.write_request(home, _spec("d-5"))
    second = adapter_bridge.write_request(home, _spec("d-5"))
    assert first == second
    with open(second, encoding="utf-8") as fh:
        assert json.load(fh)["dispatch_id"] == "d-5"


# -- read_report ------------------------------------------------------------

def test_read_report_none_when_absent(tmp_path) -> None:
    assert adapter_bridge.read_report(str(tmp_path), "missing") is None


@pytest.mark.parametrize(
    "body",
    [
        "{not json",
        "[1, 2]",
        '{"outcome": "maybe"}',
        '{"outcome": "success", "retryable": "yes"}',
        '{"no_outcome": true}',
    ],
)
def test_read_report_none_when_malformed(tmp_path, body: str) -> None:
    home = str(tmp_path)
    path = adapter_bridge.report_path(home, "d-6")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    assert adapter_bridge.read_report(home, "d-6") is None


def test_read_report_returns_valid_reports(tmp_path) -> None:
    home = str(tmp_path)
    path = adapter_bridge.report_path(home, "d-7")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for report in (
        {"outcome": "success"},
        {"outcome": "failure", "retryable": True, "reason": "boom"},
    ):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh)
        assert adapter_bridge.read_report(home, "d-7") == report


# -- cleanup -----------------------------------------------------------------

def test_cleanup_removes_only_this_dispatch(tmp_path) -> None:
    home = str(tmp_path)
    adapter_bridge.write_request(home, _spec("d-8"))
    adapter_bridge.write_request(home, _spec("d-9"))
    report = adapter_bridge.report_path(home, "d-8")
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success"}, fh)
    adapter_bridge.cleanup(home, "d-8")
    assert not os.path.exists(adapter_bridge.request_path(home, "d-8"))
    assert not os.path.exists(report)
    assert os.path.exists(adapter_bridge.request_path(home, "d-9"))


def test_cleanup_is_idempotent(tmp_path) -> None:
    home = str(tmp_path)
    adapter_bridge.cleanup(home, "never-written")  # must not raise


# -- full round trip -----------------------------------------------------------

def test_full_request_report_cleanup_round_trip(tmp_path) -> None:
    home = str(tmp_path)
    spec = _spec("d-10")
    adapter_bridge.write_request(home, spec)
    # The runner's side of the contract: one structured outcome file.
    report_path = adapter_bridge.report_path(home, "d-10")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "failure", "retryable": False}, fh)
    report = adapter_bridge.read_report(home, "d-10")
    assert report is not None and report["outcome"] == "failure"
    adapter_bridge.cleanup(home, "d-10")
    assert adapter_bridge.read_report(home, "d-10") is None
    assert not os.path.exists(adapter_bridge.request_path(home, "d-10"))
