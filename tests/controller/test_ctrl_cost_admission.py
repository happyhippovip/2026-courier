"""F-C1: the controller decides cost admission before TASK_CREATED.

The adapter module declares its cost class (adapters.<name>.COST_CLASS):
"local" runs on this host without a per-run charge, "metered" can charge.
An adapter without a declaration is unknown and never admitted.
"""
import pytest

from courier_core.controller import ApiError, Controller
from courier_core.events import EventType
from courier_core.verification import adapter_cost_class


@pytest.fixture
def ctrl(tmp_path):
    c = Controller(tmp_path, verifier=lambda adapter: None).boot()
    yield c
    c.stop()


def body(adapter="provider_exec", **params):
    return {"adapter": adapter, "params": params, "effect_class": "non_idempotent",
            "max_attempts": 1, "lease_ttl_s": 30}


def journal_types(ctrl):
    return [e.type for e in ctrl.journal.events()]


def assert_blocked(ctrl, b):
    before = journal_types(ctrl)
    with pytest.raises(ApiError) as exc:
        ctrl.create_task(b)
    assert exc.value.status == 400 and exc.value.code == "cost_blocked"
    assert journal_types(ctrl) == before                       # nothing written
    assert EventType.TASK_CREATED not in journal_types(ctrl)
    assert ctrl.claim({"worker_id": "w1"}) is None


def test_the_shipped_adapters_declare_their_cost_class():
    assert {name: adapter_cost_class(name) for name in
            ("synthetic", "local_shell", "local_json_delivery", "spreadsheet", "provider_exec")} == {
        "synthetic": "local", "local_shell": "metered", "local_json_delivery": "local",
        "spreadsheet": "local", "provider_exec": "metered"}
    assert adapter_cost_class("some_new_adapter") is None
    assert adapter_cost_class("../escape") is None


@pytest.mark.parametrize("params", [
    {},
    {"estimated_cost_eur": None},
    {"estimated_cost_eur": float("nan")},
    {"estimated_cost_eur": float("inf")},
    {"estimated_cost_eur": -1.0},
    {"estimated_cost_eur": True},
    {"estimated_cost_eur": False},                              # bool is an int in Python: False would read as 0
    {"estimated_cost_eur": "0"},
    {"estimated_cost_eur": [0]},
    {"estimated_cost_eur": 10**400},                           # valid JSON int; float() overflows
    {"estimated_cost_eur": -(10**400)},
])
def test_metered_adapter_without_a_finite_estimate_is_refused_before_the_journal(ctrl, params):
    assert_blocked(ctrl, body(**params))


@pytest.mark.parametrize("cost", [0.01, 1, 99.0])
def test_positive_cost_is_over_the_zero_spend_limit(ctrl, cost):
    assert_blocked(ctrl, body(estimated_cost_eur=cost))


@pytest.mark.parametrize("adapter", ["synthetic", "local_shell", "provider_exec"])
@pytest.mark.parametrize("marker", [{"unknown_cost": True}, {"unknown_cost": "true"}, {"unknown_cost": 1},
                                    {"cost_class": "unknown"}, {"cost_class": "Unknown"}, {"cost_class": 7}])
def test_an_explicit_unknown_marker_is_refused_for_every_adapter(ctrl, adapter, marker):
    assert_blocked(ctrl, body(adapter=adapter, estimated_cost_eur=0.0, **marker))


@pytest.mark.parametrize("params", [{}, {"estimated_cost_eur": 0.0}])
def test_an_undeclared_adapter_is_refused_even_with_a_zero_estimate(ctrl, params):
    assert_blocked(ctrl, body(adapter="some_new_adapter", **params))


def test_invalid_estimate_is_refused_for_a_local_adapter_too(ctrl):
    assert_blocked(ctrl, body(adapter="synthetic", estimated_cost_eur=float("nan")))


def test_metered_adapter_with_an_explicit_zero_is_created(ctrl):
    status, _ = ctrl.create_task(body(estimated_cost_eur=0.0))
    assert status == 201 and journal_types(ctrl).count(EventType.TASK_CREATED) == 1


@pytest.mark.parametrize("adapter", ["synthetic", "local_json_delivery", "spreadsheet"])
def test_a_local_adapter_without_an_estimate_is_still_created(ctrl, adapter):
    assert ctrl.create_task(body(adapter=adapter))[0] == 201


def test_local_shell_can_run_any_cli_so_it_needs_an_estimate(ctrl):
    """The adapter name is allowlisted, the argv is not: a paid provider CLI is one argv away."""
    paid_cli = {"command": ["claude", "-p", "hi"], "write": "o.txt"}
    assert_blocked(ctrl, body(adapter="local_shell", **paid_cli))
    assert ctrl.create_task(body(adapter="local_shell", estimated_cost_eur=0.0, **paid_cli))[0] == 201


def test_replay_of_an_admitted_task_is_a_duplicate_and_writes_nothing(ctrl):
    b = dict(body(estimated_cost_eur=0.0), idempotency_key="k1")
    assert ctrl.create_task(b)[0] == 201
    before = journal_types(ctrl)
    status, payload = ctrl.create_task(b)
    assert status == 200 and payload["duplicate"] is True
    assert journal_types(ctrl) == before


def test_a_refused_body_reusing_an_admitted_key_is_refused_and_writes_nothing(ctrl):
    ok = dict(body(estimated_cost_eur=0.0), idempotency_key="k2")
    ctrl.create_task(ok)
    before = journal_types(ctrl)
    with pytest.raises(ApiError) as exc:
        ctrl.create_task(dict(body(), idempotency_key="k2"))       # same key, estimate missing
    assert exc.value.code == "cost_blocked"
    assert journal_types(ctrl) == before


def test_an_injected_cost_class_resolver_decides(tmp_path):
    c = Controller(tmp_path, verifier=lambda adapter: None, cost_class={"probe": "local"}.get).boot()
    try:
        assert c.create_task(body(adapter="probe"))[0] == 201
        with pytest.raises(ApiError):
            c.create_task(body(adapter="other"))
    finally:
        c.stop()
