"""P9 pins for courier_worker.service resolve_spec home/heartbeat mapping.

Tests only; no behavior change. Pins the resolve_spec branches the other
service P9 aspects do not cover: home derivation from artifacts_root when
home is None (and the argv/artifact_dir consistency that follows), heartbeat
passthrough for non-positive or non-numeric claim values, exact field
mapping, and the artifact-prefix curdir branch. Offline; no network calls.
"""

import os
import sys

from courier_worker import adapter_bridge
from courier_worker.host import DEFAULT_TIMEOUT_S
from courier_worker.service import _artifact_prefix, resolve_spec


def _claim(**overrides):
    claim = {
        "task_id": "t-1",
        "dispatch_id": "d-1",
        "attempt": 1,
        "ttl_s": 60,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "ek-1"},
    }
    claim.update(overrides)
    return claim


def test_home_none_derives_from_artifacts_root(tmp_path):
    artifacts_root = str(tmp_path / "artifacts")
    spec = resolve_spec(_claim(), "w-1", artifacts_root, 5.0, home=None)
    derived = os.path.dirname(os.path.abspath(artifacts_root))
    assert derived == str(tmp_path)
    assert spec.artifact_dir == os.path.join(artifacts_root, "d-1")
    assert spec.argv[0] == sys.executable
    assert spec.argv[1] == adapter_bridge.RUNNER_SCRIPT
    assert spec.argv[2] == adapter_bridge.request_path(derived, "d-1")


def test_explicit_home_used_verbatim_for_argv(tmp_path):
    home = str(tmp_path / "home")
    artifacts_root = os.path.join(home, "artifacts")
    spec = resolve_spec(_claim(), "w-1", artifacts_root, 5.0, home=home)
    assert spec.artifact_dir == os.path.join(artifacts_root, "d-1")
    assert spec.argv[2] == adapter_bridge.request_path(home, "d-1")


def test_non_positive_claim_heartbeat_leaves_default(tmp_path):
    for bad in (0, -2, 0.0):
        claim = _claim(heartbeat_s=bad)
        spec = resolve_spec(claim, "w-1", str(tmp_path), 5.0, home=str(tmp_path))
        assert spec.heartbeat_s == 5.0


def test_non_numeric_claim_heartbeat_leaves_default(tmp_path):
    for bad in ("fast", None, [1]):
        claim = _claim(heartbeat_s=bad)
        spec = resolve_spec(claim, "w-1", str(tmp_path), 5.0, home=str(tmp_path))
        assert spec.heartbeat_s == 5.0


def test_field_mapping_is_exact(tmp_path):
    home = str(tmp_path)
    spec = resolve_spec(_claim(), "w-9", str(tmp_path / "artifacts"), 7.5, home=home)
    assert spec.task_id == "t-1"
    assert spec.dispatch_id == "d-1"
    assert spec.attempt == 1
    assert spec.worker_id == "w-9"
    assert spec.result_id == "r-d-1"
    assert spec.lease_ttl_s == 60.0 and isinstance(spec.lease_ttl_s, float)
    assert spec.timeout_s == float(DEFAULT_TIMEOUT_S) and isinstance(spec.timeout_s, float)
    assert spec.heartbeat_s == 7.5
    assert spec.adapter == "synthetic"
    assert spec.effect_key == "ek-1"
    assert spec.params == {}


def test_artifact_prefix_empty_when_dir_is_home(tmp_path):
    assert _artifact_prefix(str(tmp_path), str(tmp_path)) == ""


def test_artifact_prefix_nested_inside_home(tmp_path):
    nested = os.path.join(str(tmp_path), "a", "b")
    assert _artifact_prefix(nested, str(tmp_path)) == "a/b/"
