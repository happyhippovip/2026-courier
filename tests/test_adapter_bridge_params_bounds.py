"""P9 hardening pins for courier_worker.adapter_bridge params envelope.

Tests only: no behavior change. Covers validate_request's params bounds
(type, plain-JSON, NaN/Infinity, 64 KiB size bound) and _safe dispatch
sanitization keeping request/report paths contained under the home dir.
Offline, no network, no credentials.
"""

import json
import os

import pytest

from courier_worker import adapter_bridge as A
from courier_worker.host import SpecError

EFFECT_KEY = "cfx-" + "a" * 40


def make_spec(**over):
    spec = {
        "adapter": "synthetic",
        "effect_key": EFFECT_KEY,
        "params": {"write": "out.txt", "content": "hi"},
    }
    spec.update(over)
    return spec


def test_non_dict_spec_refused():
    for bad in (None, [], "spec", 42):
        with pytest.raises(SpecError, match="no spec object"):
            A.validate_request(bad)


def test_argv_spec_refused():
    spec = make_spec(argv=["python", "-c", "pass"])
    with pytest.raises(SpecError, match="must not carry argv"):
        A.validate_request(spec)


def test_unknown_adapter_refused():
    with pytest.raises(SpecError, match="not allowlisted"):
        A.validate_request(make_spec(adapter="shell"))
    with pytest.raises(SpecError, match="not allowlisted"):
        A.validate_request(make_spec(adapter=None))


def test_non_dict_params_refused():
    with pytest.raises(SpecError, match="params must be an object"):
        A.validate_request(make_spec(params="sleep 1"))
    with pytest.raises(SpecError, match="params must be an object"):
        A.validate_request(make_spec(params=None))
    with pytest.raises(SpecError, match="params must be an object"):
        A.validate_request(make_spec(params=["sleep_s", 0]))


def test_nan_and_infinity_params_refused_as_non_json():
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(make_spec(params={"sleep_s": float("nan")}))
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(make_spec(params={"sleep_s": float("inf")}))
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(make_spec(params={"sleep_s": float("-inf")}))


def test_non_serializable_params_refused():
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(make_spec(params={"write": "out.txt", "extra": {1, 2, 3}}))
    with pytest.raises(SpecError, match="not plain JSON"):
        A.validate_request(make_spec(params={"write": "out.txt", "extra": object()}))


def test_oversize_params_refused():
    big = {"write": "out.txt", "content": "x" * 70000}
    encoded = json.dumps(big, sort_keys=True, allow_nan=False)
    assert len(encoded.encode("utf-8")) > A.MAX_PARAMS_BYTES
    with pytest.raises(SpecError, match="exceed the size bound"):
        A.validate_request(make_spec(params=big))


def test_size_bound_is_exact_not_off_by_one():
    overhead = len(json.dumps({"content": "", "write": "out.txt"},
                              sort_keys=True, allow_nan=False).encode("utf-8"))
    n_at = A.MAX_PARAMS_BYTES - overhead
    at = {"write": "out.txt", "content": "x" * n_at}
    assert len(json.dumps(at, sort_keys=True, allow_nan=False).encode("utf-8")) == A.MAX_PARAMS_BYTES
    adapter, params, effect_key = A.validate_request(make_spec(params=at))
    assert (adapter, effect_key) == ("synthetic", EFFECT_KEY)
    over = {"write": "out.txt", "content": "x" * (n_at + 1)}
    with pytest.raises(SpecError, match="exceed the size bound"):
        A.validate_request(make_spec(params=over))


def test_valid_params_pass_through():
    adapter, params, effect_key = A.validate_request(make_spec())
    assert adapter == "synthetic"
    assert params == {"write": "out.txt", "content": "hi"}
    assert effect_key == EFFECT_KEY


def test_safe_sanitizes_dispatch_id():
    assert A._safe("") == "unnamed"
    assert A._safe("../../etc/passwd") == ".._.._etc_passwd"
    assert "/" not in A._safe("a/b\\c d")
    assert A._safe("dsp-7_ok.1") == "dsp-7_ok.1"


def test_request_and_report_paths_stay_contained(tmp_path):
    home = str(tmp_path)
    for evil in ("../../etc/passwd", "..\\..\\win", "a/b", "", "d 1"):
        for path in (A.request_path(home, evil), A.report_path(home, evil)):
            assert os.path.abspath(path).startswith(os.path.abspath(home) + os.sep)
    assert A.request_path(home, "d1").endswith(os.path.join("run", "requests", "d1.json"))
    assert A.report_path(home, "d1").endswith(os.path.join("run", "reports", "d1.json"))
