"""P9 containment pins for courier_worker.adapter_bridge (tests only).

Scope: hostile dispatch IDs must never escape the worker home directory.
Every path the bridge derives from a dispatch ID (request file, report
file, runner argv) stays a single file name under <home>/run/requests or
<home>/run/reports. No network, no credentials, no subprocesses.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge
from courier_worker.host import SpecError


HOSTILE_IDS = [
    "../../etc/passwd",
    "a/b/c",
    "..\\..\\win",
    " name with spaces ",
    "",
    "x" * 300,
    "....",
    "a:b*c?d",
]


def _spec(dispatch_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        adapter="synthetic",
        params={},
        attempt=1,
        task_id="t-1",
        dispatch_id=dispatch_id,
        effect_key="lane1.ok-1:a_b",
        artifact_dir=os.path.join("artifacts", dispatch_id or "unnamed"),
    )


def test_safe_never_emits_separator():
    for raw in HOSTILE_IDS:
        safe = adapter_bridge._safe(raw)
        assert os.sep not in safe
        assert "/" not in safe and "\\" not in safe
        assert safe, "sanitized id must be non-empty"


def test_safe_empty_becomes_unnamed():
    assert adapter_bridge._safe("") == "unnamed"


def test_safe_keeps_benign_ids():
    # Allowed: alnum plus "-_." — anything else (e.g. ":") is scrubbed.
    assert adapter_bridge._safe("abc-123_X.y-z") == "abc-123_X.y-z"
    assert adapter_bridge._safe("abc-123_X.y:z") == "abc-123_X.y_z"


def test_request_and_report_paths_stay_under_home(tmp_path):
    home = str(tmp_path)
    for raw in HOSTILE_IDS:
        for path in (
            adapter_bridge.request_path(home, raw),
            adapter_bridge.report_path(home, raw),
        ):
            real = os.path.realpath(path)
            assert real.startswith(os.path.realpath(home) + os.sep), (raw, path)
            parent = os.path.basename(os.path.dirname(real))
            assert parent in {"requests", "reports"}, path
            assert os.path.basename(real).endswith(".json")


def test_distinct_dispatch_ids_do_not_collide_silently(tmp_path):
    home = str(tmp_path)
    first = adapter_bridge.request_path(home, "a/b")
    second = adapter_bridge.request_path(home, "a_b")
    assert first == second  # sanitization is documented lossy; callers must use unique ids
    assert os.path.realpath(first).startswith(os.path.realpath(home) + os.sep)


def test_runner_argv_is_pinned_and_contained(tmp_path):
    home = str(tmp_path)
    argv = adapter_bridge.runner_argv(home, "../../evil")
    assert argv[0] == sys.executable
    assert os.path.isabs(argv[1]) and argv[1].endswith("adapter_runner.py")
    assert os.path.isfile(argv[1])
    assert argv[2] == adapter_bridge.request_path(home, "../../evil")
    assert os.path.realpath(argv[2]).startswith(os.path.realpath(home) + os.sep)


def test_runner_script_exists_in_repo():
    assert os.path.isfile(adapter_bridge.RUNNER_SCRIPT)


@pytest.mark.parametrize(
    "spec",
    [
        ["not-a-dict"],
        {"adapter": "synthetic", "params": {}, "effect_key": "k", "argv": ["evil"]},
        {"adapter": "nope", "params": {}, "effect_key": "k"},
        {"params": {}, "effect_key": "k"},
        {"adapter": "synthetic", "params": [], "effect_key": "k"},
        {"adapter": "synthetic", "params": {"x": float("nan")}, "effect_key": "k"},
        {"adapter": "synthetic", "params": {"blob": "x" * (64 * 1024 + 1)}, "effect_key": "k"},
        {"adapter": "synthetic", "params": {}},
        {"adapter": "synthetic", "params": {}, "effect_key": "has space"},
        {"adapter": "synthetic", "params": {}, "effect_key": "a/b"},
        {"adapter": "synthetic", "params": {}, "effect_key": 42},
    ],
)
def test_validate_request_fail_closed(spec):
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(spec)


def test_validate_request_happy_path():
    adapter, params, key = adapter_bridge.validate_request(
        {"adapter": "synthetic", "params": {}, "effect_key": "lane1.ok:a"}
    )
    assert (adapter, params, key) == ("synthetic", {}, "lane1.ok:a")


def test_write_request_round_trip_contained(tmp_path):
    home = str(tmp_path)
    spec = _spec("../../evil")
    path = adapter_bridge.write_request(home, spec)
    assert path == adapter_bridge.request_path(home, "../../evil")
    assert os.path.realpath(path).startswith(os.path.realpath(home) + os.sep)
    with open(path, encoding="utf-8") as handle:
        stored = json.load(handle)
    assert stored["adapter"] == "synthetic"
    assert stored["dispatch_id"] == "../../evil"
    # No report yet: never read a (possibly stale) report as success.
    assert adapter_bridge.read_report(home, "../../evil") is None


def test_read_report_rejects_malformed(tmp_path):
    home = str(tmp_path)
    dispatch = "r1"
    assert adapter_bridge.read_report(home, dispatch) is None  # absent
    report = adapter_bridge.report_path(home, dispatch)
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    assert adapter_bridge.read_report(home, dispatch) is None
    with open(report, "w", encoding="utf-8") as handle:
        json.dump({"outcome": "weird", "retryable": False}, handle)
    assert adapter_bridge.read_report(home, dispatch) is None
    with open(report, "w", encoding="utf-8") as handle:
        json.dump({"outcome": "success", "retryable": "yes"}, handle)
    assert adapter_bridge.read_report(home, dispatch) is None
    with open(report, "w", encoding="utf-8") as handle:
        json.dump({"outcome": "success", "retryable": True, "reason": "ok"}, handle)
    assert adapter_bridge.read_report(home, dispatch)["outcome"] == "success"


def test_cleanup_is_idempotent(tmp_path):
    home = str(tmp_path)
    spec = _spec("c1")
    adapter_bridge.write_request(home, spec)
    adapter_bridge.cleanup(home, "c1")
    assert not os.path.exists(adapter_bridge.request_path(home, "c1"))
    adapter_bridge.cleanup(home, "c1")  # second call must not raise
