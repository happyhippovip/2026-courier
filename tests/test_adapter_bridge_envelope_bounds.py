"""P9 envelope-bound pins for courier_worker.adapter_bridge (tests only).

Covers the request-envelope bounds that keep a claim spec small, plain and
addressable: params size/JSON-shape limits, effect_key charset/length limits,
dispatch-id sanitization, stale-report clearing on write, atomic-write
failure cleanup, and report shape gating. No network, no subprocesses, no
behavior change to the module under test.
"""

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge as ab
from courier_worker.host import SpecError

VALID_KEY = "run-1:dispatch_2.3"


def _spec(**overrides):
    base = {"adapter": "synthetic", "params": {}, "effect_key": VALID_KEY}
    base.update(overrides)
    return base


def test_happy_path_returns_adapter_params_key():
    params = {"content": "hi"}
    adapter, out_params, key = ab.validate_request(_spec(params=params))
    assert adapter == "synthetic"
    assert out_params == params
    assert key == VALID_KEY


def test_non_dict_spec_refused():
    with pytest.raises(SpecError):
        ab.validate_request(["not", "a", "dict"])


def test_spec_carrying_argv_refused():
    with pytest.raises(SpecError):
        ab.validate_request(_spec(argv=["anything"]))


def test_unknown_adapter_refused():
    with pytest.raises(SpecError):
        ab.validate_request(_spec(adapter="shell"))
    with pytest.raises(SpecError):
        ab.validate_request({"params": {}, "effect_key": VALID_KEY})


def test_adapter_table_is_closed():
    assert set(ab.ADAPTERS) == {"synthetic"}


def test_params_must_be_a_dict():
    with pytest.raises(SpecError):
        ab.validate_request(_spec(params=["x"]))


def test_params_rejected_by_adapter_validator():
    with pytest.raises(SpecError):
        ab.validate_request(_spec(params={"sleep_s": -1}))


def test_params_nan_refused():
    with pytest.raises(SpecError):
        ab.validate_request(_spec(params={"sleep_s": float("nan")}))


def test_params_not_plain_json_refused():
    with pytest.raises(SpecError):
        ab.validate_request(_spec(params={"blob": object()}))


def test_params_over_size_bound_refused():
    with pytest.raises(SpecError):
        ab.validate_request(_spec(params={"content": "x" * (ab.MAX_PARAMS_BYTES + 1)}))


def test_params_at_size_bound_accepted():
    overhead = len(json.dumps({"content": ""}, sort_keys=True).encode("utf-8"))
    exact = {"content": "x" * (ab.MAX_PARAMS_BYTES - overhead)}
    assert len(json.dumps(exact, sort_keys=True).encode("utf-8")) == ab.MAX_PARAMS_BYTES
    adapter, _, _ = ab.validate_request(_spec(params=exact))
    assert adapter == "synthetic"


def test_params_one_byte_over_bound_refused():
    overhead = len(json.dumps({"content": ""}, sort_keys=True).encode("utf-8"))
    over = {"content": "x" * (ab.MAX_PARAMS_BYTES - overhead + 1)}
    assert len(json.dumps(over, sort_keys=True).encode("utf-8")) == ab.MAX_PARAMS_BYTES + 1
    with pytest.raises(SpecError):
        ab.validate_request(_spec(params=over))


def test_effect_key_missing_or_not_a_string_refused():
    with pytest.raises(SpecError):
        ab.validate_request({"adapter": "synthetic", "params": {}})
    with pytest.raises(SpecError):
        ab.validate_request(_spec(effect_key=None))
    with pytest.raises(SpecError):
        ab.validate_request(_spec(effect_key=""))


def test_effect_key_charset_and_length_bounds():
    for bad in ["has space", "slash/x", "new\nline", "x" * 201, "uni–dash"]:
        with pytest.raises(SpecError):
            ab.validate_request(_spec(effect_key=bad))
    edge = "a" * 200
    _, _, key = ab.validate_request(_spec(effect_key=edge))
    assert key == edge
    _, _, key = ab.validate_request(_spec(effect_key="A9._:-z"))
    assert key == "A9._:-z"


def test_safe_sanitizes_dispatch_ids():
    assert ab._safe("run-1_ok.json") == "run-1_ok.json"
    assert ab._safe("") == "unnamed"
    assert ab._safe("a/b c") == "a_b_c"
    assert ab._safe("../..") == ".._.."


def test_request_and_report_paths_stay_under_home(tmp_path):
    home = str(tmp_path)
    assert ab.request_path(home, "d 1/x") == os.path.join(home, "run", "requests", "d_1_x.json")
    assert ab.report_path(home, "d 1/x") == os.path.join(home, "run", "reports", "d_1_x.json")


def test_runner_argv_names_own_runner(tmp_path):
    home = str(tmp_path)
    argv = ab.runner_argv(home, "d1")
    assert argv[0] == sys.executable
    assert os.path.isabs(argv[1])
    assert os.path.basename(argv[1]) == "adapter_runner.py"
    assert argv[2] == ab.request_path(home, "d1")


def _ns(home, dispatch_id="d1"):
    return SimpleNamespace(
        adapter="synthetic",
        params={"content": "hi"},
        attempt=1,
        task_id="t1",
        dispatch_id=dispatch_id,
        effect_key=VALID_KEY,
        artifact_dir=os.path.join(home, "artifacts", dispatch_id),
    )


def test_write_request_persists_envelope_and_returns_path(tmp_path):
    home = str(tmp_path)
    path = ab.write_request(home, _ns(home))
    assert path == ab.request_path(home, "d1")
    with open(path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["adapter"] == "synthetic"
    assert stored["params"] == {"content": "hi"}
    assert stored["attempt"] == 1
    assert stored["task_id"] == "t1"
    assert stored["dispatch_id"] == "d1"
    assert stored["effect_key"] == VALID_KEY
    assert stored["report"] == ab.report_path(home, "d1")


def test_write_request_clears_stale_report(tmp_path):
    home = str(tmp_path)
    stale = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        fh.write('{"outcome": "success"}')
    ab.write_request(home, _ns(home))
    assert not os.path.exists(stale)


def test_write_request_leaves_no_temp_files(tmp_path):
    home = str(tmp_path)
    ab.write_request(home, _ns(home))
    parent = os.path.dirname(ab.request_path(home, "d1"))
    assert [n for n in os.listdir(parent) if n.startswith(".tmp-")] == []


def test_atomic_write_failure_cleans_up(tmp_path):
    target = str(tmp_path / "req.json")
    with pytest.raises(TypeError):
        ab._atomic_json(target, {"blob": object()})
    assert not os.path.exists(target)
    assert [n for n in os.listdir(str(tmp_path)) if n.startswith(".tmp-")] == []


def test_read_report_round_trip(tmp_path):
    home = str(tmp_path)
    assert ab.read_report(home, "d1") is None
    report = {"outcome": "success", "retryable": False, "detail": "ok"}
    path = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh)
    assert ab.read_report(home, "d1") == report


def test_read_report_rejects_bad_shapes(tmp_path):
    home = str(tmp_path)
    path = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def _write(raw):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(raw)

    _write("not json{")
    assert ab.read_report(home, "d1") is None
    _write('["success"]')
    assert ab.read_report(home, "d1") is None
    _write('{"outcome": "pending", "retryable": false}')
    assert ab.read_report(home, "d1") is None
    _write('{"outcome": "success", "retryable": "yes"}')
    assert ab.read_report(home, "d1") is None
    _write('{"outcome": "failure", "retryable": true}')
    assert ab.read_report(home, "d1") == {"outcome": "failure", "retryable": True}


def test_cleanup_removes_pair_and_is_idempotent(tmp_path):
    home = str(tmp_path)
    ab.write_request(home, _ns(home))
    report = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as fh:
        fh.write('{"outcome": "success", "retryable": false}')
    ab.cleanup(home, "d1")
    assert not os.path.exists(ab.request_path(home, "d1"))
    assert not os.path.exists(report)
    ab.cleanup(home, "d1")


def test_report_outcomes_are_closed():
    assert set(ab.REPORT_OUTCOMES) == {"success", "failure"}
