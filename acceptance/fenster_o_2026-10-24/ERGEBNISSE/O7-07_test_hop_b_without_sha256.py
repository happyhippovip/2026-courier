"""O7-07 (B4 A->B->C bytes): hop B must not be accepted without a sha256 per input.

Guard (holds): the bridge refuses an upstream artifact without a sha256
(scripts/ledger_v1_bridge.py:492-497 -> input_unverified) and posts B only with
{path, sha256} per input (tests/test_golden_ledger_bridge_ab.py, test_ledger_bridge_verified_inputs.py).
Defect (strict xfail): the controller treats params as opaque
(courier_core/controller.py:347-360). A B task whose params.inputs carry no sha256
is created (201) and can run and finalize. The hop contract is enforced only by one
client, not at the controller boundary.
"""
import pytest

from courier_core.controller import ApiError, Controller
from scripts import ledger_v1_bridge as bridge
from tests.test_ledger_bridge_verified_inputs import _Args, _fake, _state


def _b_task(inputs):
    return {
        "adapter": "synthetic",
        "params": {"write": "out.txt", "content": "unit-b", "estimated_cost_eur": 0.0, "inputs": inputs},
        "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 30,
        "idempotency_key": "o7-07-b",
    }


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-07/B4: controller creates hop B whose inputs carry no sha256")
@pytest.mark.parametrize("entry", [
    {"mission_id": "A", "task_id": "task-a", "result_id": "r-a", "path": "artifacts/a/out.txt"},
    {"mission_id": "A", "task_id": "task-a", "result_id": "r-a", "path": "artifacts/a/out.txt", "sha256": ""},
    {"mission_id": "A", "task_id": "task-a", "result_id": "r-a", "path": "artifacts/a/out.txt", "sha256": "abc"},
])
def test_controller_refuses_hop_b_inputs_without_sha256(tmp_path, entry):
    ctrl = Controller(tmp_path / "home").boot()
    try:
        try:
            status, record = ctrl.create_task(_b_task([entry]))
        except ApiError as exc:
            assert exc.status == 400
            return
        raise AssertionError(f"hop B created: {status} {record.get('task_id')}")
    finally:
        ctrl.stop()


@pytest.mark.parametrize("artifact", [
    {"path": "artifacts/d/out0.txt"},
    {"path": "artifacts/d/out0.txt", "sha256": ""},
    {"path": "artifacts/d/out0.txt", "sha256": "ABC"},
])
def test_guard_bridge_refuses_upstream_artifact_without_sha256(tmp_path, artifact):
    result = {"task_id": "task-a", "result_id": "r-1", "artifacts": [artifact]}
    got = bridge._resolve_inputs(_state(), {"inputs_from": ["A"]}, {"depends_on": ["A"]},
                                 _fake(result), _Args, "t", tmp_path)
    assert got == (None, "input_unverified", True)
