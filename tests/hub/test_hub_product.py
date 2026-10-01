"""L5 Desktop Hub: projection mapping and the real hub <-> controller loop.

The hub is exercised against the real L2 controller and HTTP service
(in-process, real sockets, real journal); no second runtime is faked.
"""

import json
import sys
import threading
from dataclasses import replace
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controller"))
from ctrl_helpers import FakeClock, LiveService, result_body, task_body  # noqa: E402

from courier_core.state_machine import TaskState, TaskStatus  # noqa: E402
from courier_hub import model  # noqa: E402
from courier_hub.server import Hub, HubServer  # noqa: E402

ACTOR = "desktop:tester"
MACHINE_KEYS = {"id", "pile", "outcome", "mark", "phase", "decision", "blocked_attempt", "at"}


# ------------------------------------------------------------------ helpers
def state(status, **kw):
    base = dict(task_id="t1", status=TaskStatus(status), adapter="synthetic", params={},
                effect_class="non_idempotent", max_attempts=3, lease_ttl_s=6, timeout_s=None, attempt=1)
    base.update(kw)
    return TaskState(**base)


class HubProcess:
    """The hub HTTP server in-process on a free port."""

    def __init__(self, home, controller_url):
        self.server = HubServer(Hub(Path(home), controller_url, actor=ACTOR), 0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self.thread.start()
        self.base = self.server.url.rstrip("/")

    def home(self):
        return requests.get(self.base + "/hub/api/home", timeout=10).json()

    def item(self, task_id):
        return requests.get(f"{self.base}/hub/api/items/{task_id}", timeout=10)

    def post(self, path, body, headers=None):
        h = {"X-Courier-Hub": "1", "Content-Type": "application/json"}
        h.update(headers or {})
        return requests.post(self.base + path, data=json.dumps(body), headers=h, timeout=10)

    def decide(self, task_id, decision, attempt, note=None):
        return self.post(f"/hub/api/items/{task_id}/decision",
                         {"decision": decision, "attempt": attempt, **({"note": note} if note else {})})

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


def pass_time(live, clock, seconds, step=0.25):
    for _ in range(int(seconds / step)):
        clock.advance(step)
        live.controller.tick()


def blocked_task(live, clock):
    """A started non-idempotent attempt whose worker vanished: BLOCKED."""
    task_id = live.post("/v1/tasks", task_body(effect_class="non_idempotent", lease_ttl_s=3)).json()["task_id"]
    lease = live.post("/v1/claim", {"worker_id": "w1"}).json()
    assert live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]}).status_code == 200
    pass_time(live, clock, 4)
    assert live.get(f"/v1/tasks/{task_id}").json()["status"] == "BLOCKED"
    return task_id


def wait_status(live, task_id, status, timeout=10):
    """The service's own verifier thread may hold the result; wait for the runtime, never guess."""
    import time
    deadline = time.monotonic() + timeout
    while live.get(f"/v1/tasks/{task_id}").json()["status"] != status:
        live.controller.drain()
        assert time.monotonic() < deadline, f"task never reached {status}"
        time.sleep(0.05)


def verified_task(live):
    task_id = live.post("/v1/tasks", task_body()).json()["task_id"]
    lease = live.post("/v1/claim", {"worker_id": "w1"}).json()
    live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]})
    live.post("/v1/result", result_body(lease["dispatch_id"]))
    wait_status(live, task_id, "COMPLETE")
    return task_id


@pytest.fixture
def world(tmp_path):
    clock = FakeClock()
    live = LiveService(tmp_path / "home", clock=clock)
    hub = HubProcess(tmp_path / "home", live.base)
    yield live, hub, clock
    hub.stop()
    live.stop()


# --------------------------------------------------------- projection (pure)
@pytest.mark.parametrize("status, pile", [
    ("QUEUED", "working"), ("CLAIMED", "working"), ("RUNNING", "working"), ("VERIFYING", "working"),
    ("ACCEPTED", "working"), ("RETRY_PENDING", "working"), ("BLOCKED", "needs_you"),
    ("COMPLETE", "done"), ("FAILED", "done"), ("CANCELLED", "done"),
])
def test_every_runtime_status_projects_to_exactly_one_pile(status, pile):
    assert model.pile_of(state(status)) == pile


def test_done_outcomes_stay_distinct_and_only_verified_gets_the_check():
    rows = {
        "verified": state("COMPLETE", resolution="verified"),
        "human": state("COMPLETE", resolution="effect_confirmed", decided_by="desktop:ana"),
        "failed": state("FAILED"),
        "stopped": state("CANCELLED"),
        "uncertain": state("CANCELLED", resolution="cancelled_effect_unknown", decided_by="desktop:ana"),
    }
    copy = {k: model.outcome_copy(v) for k, v in rows.items()}
    assert copy["verified"]["mark"] == "check" and copy["verified"]["label"] == "Checked by Courier"
    assert copy["human"]["mark"] == "signature" and copy["human"]["label"] == "Confirmed by ana"
    assert "did not verify" in copy["human"]["explanation"]
    assert copy["uncertain"]["label"] == "Outcome uncertain"
    assert copy["uncertain"]["explanation"] == "Courier stopped trying. The earlier action may already have happened."
    assert copy["failed"]["label"] == "Couldn't complete this safely"
    assert copy["stopped"]["label"] == "Stopped"
    assert [c["mark"] for c in copy.values()].count("check") == 1
    assert len({c["outcome"] for c in copy.values()}) == 5
    for c in copy.values():  # no outcome claims a safe stop
        assert "safely stopped" not in (c["label"] + c["explanation"]).lower()


def test_complete_without_resolution_is_never_shown_as_checked():
    assert model.outcome_copy(state("COMPLETE"))["mark"] == "neutral"


def test_retry_pending_does_not_change_the_working_card():
    running = model.working_phase(state("RUNNING"))
    recovering = model.working_phase(state("RETRY_PENDING"))
    assert running == recovering


def test_unknown_status_is_refused_not_guessed():
    with pytest.raises(ValueError):
        model.pile_of({"status": "TELEPORTED"})


def test_needs_you_card_explains_the_concrete_retry_consequence():
    card = model.needs_you_card(state("BLOCKED"), [])
    labels = [c["label"] for c in card["choices"]]
    assert labels == ["It happened", "Try once more", "Stop here"]
    retry = card["choices"][1]
    assert "could repeat it" in retry["confirm"] and model.ADAPTER_COPY["synthetic"]["repeat_consequence"] in retry["confirm"]
    stop = card["choices"][2]
    assert "may still have happened" in stop["explains"]


def test_retry_is_not_offered_once_a_stop_was_requested():
    card = model.needs_you_card(state("BLOCKED", cancel_requested=True), [])
    assert [c["decision"] for c in card["choices"]] == ["effect_confirmed", "cancel"]
    assert card["retry_unavailable_reason"]


def test_customer_copy_carries_no_internal_identifiers():
    task = state("BLOCKED", dispatch_id="dsp-secret-1", worker_id="worker-77")
    def words(value, key=None):  # what a customer can read: every string value except machine keys
        if isinstance(value, dict):
            return " ".join(words(v, k) for k, v in value.items() if k not in MACHINE_KEYS)
        if isinstance(value, list):
            return " ".join(words(v, key) for v in value)
        return str(value) if isinstance(value, str) else ""
    shown = words([model.card(task, []), model.receipt(task, [])])
    for internal in ("dsp-secret-1", "worker-77", "dispatch", "attempt", "effect_key", "BLOCKED", "lease"):
        assert internal not in shown
    assert "dsp-secret-1" in json.dumps(model.support(task, []))  # support view keeps them


# ---------------------------------------------------- slice 1: truth -> home
def test_empty_and_not_set_up_states(tmp_path):
    hub = HubProcess(tmp_path / "nothing-here", "http://127.0.0.1:9")
    try:
        view = hub.home()
        assert view["truth"] == "not_set_up" and view["status"]["controller"] == "not_set_up"
        assert view["counts"] == {"needs_you": 0, "working": 0, "done": 0}
    finally:
        hub.stop()


def test_home_projects_canonical_state_and_survives_restart(tmp_path):
    clock = FakeClock()
    home = tmp_path / "home"
    live = LiveService(home, clock=clock)
    hub = HubProcess(home, live.base)
    try:
        blocked = blocked_task(live, clock)
        done = verified_task(live)
        queued = live.post("/v1/tasks", task_body()).json()["task_id"]
        view = hub.home()
        assert view["truth"] == "ok" and view["status"]["controller"] == "running"
        assert [c["id"] for c in view["needs_you"]] == [blocked]
        assert [c["id"] for c in view["working"]] == [queued]
        assert [c["id"] for c in view["done"]] == [done] and view["done"][0]["mark"] == "check"
        before = {k: [c["id"] for c in view[k]] for k in ("needs_you", "working", "done")}
    finally:
        hub.stop()
        live.stop()
    # Controller and hub both gone, then back: the same truth comes back.
    hub = HubProcess(home, live.base)
    try:
        offline = hub.home()
        assert offline["status"]["controller"] == "unreachable"
        assert {k: [c["id"] for c in offline[k]] for k in before} == before
    finally:
        hub.stop()
    live = LiveService(home, clock=FakeClock())
    hub = HubProcess(home, live.base)
    try:
        again = hub.home()
        assert again["status"]["controller"] == "running"
        assert {k: [c["id"] for c in again[k]] for k in before} == before
    finally:
        hub.stop()
        live.stop()


# ------------------------------------------------ slice 2: Human Desk loop
def test_blocked_effect_confirmed_through_the_hub(world):
    live, hub, clock = world
    task_id = blocked_task(live, clock)
    card = hub.home()["needs_you"][0]
    attempt = card["needs_you"]["blocked_attempt"]
    answer = hub.decide(task_id, "effect_confirmed", attempt, note="I saw the file")
    assert answer.status_code == 200 and answer.json()["result"] == "recorded"
    view = hub.home()
    assert view["needs_you"] == []
    done = view["done"][0]
    assert done["outcome"] == "human_confirmed" and done["label"] == "Confirmed by tester"
    assert done["mark"] != "check"
    runtime = live.get(f"/v1/tasks/{task_id}").json()
    assert runtime["resolution"] == "effect_confirmed" and runtime["decided_by"] == ACTOR
    receipt = hub.item(task_id).json()["receipt"]
    assert receipt["decisions"][0]["who"] == "tester" and receipt["decisions"][0]["reason"] == "I saw the file"
    assert "did not verify" in receipt["how_known"]
    assert receipt["resumed"] is False  # interrupted, but it asked a person instead of resuming


def test_duplicate_click_is_recorded_once(world):
    live, hub, clock = world
    task_id = blocked_task(live, clock)
    first = hub.decide(task_id, "effect_confirmed", 1)
    second = hub.decide(task_id, "effect_confirmed", 1)
    assert first.json()["result"] == "recorded"
    assert second.status_code == 200 and second.json()["result"] == "already_recorded"
    events = [e for e in live.controller.journal.events(task_id=task_id) if e.type.value == "EFFECT_CONFIRMED"]
    assert len(events) == 1


def test_a_stale_screen_cannot_decide_a_newer_question(world):
    live, hub, clock = world
    task_id = blocked_task(live, clock)
    assert hub.decide(task_id, "retry_authorized", 1).json()["result"] == "recorded"
    assert hub.home()["working"][0]["id"] == task_id  # the authorised attempt is Courier's again
    lease = live.post("/v1/claim", {"worker_id": "w2"}).json()
    live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]})
    pass_time(live, clock, 4)  # lost again: a second question about attempt 2
    stale = hub.decide(task_id, "effect_confirmed", 1)  # a screen still showing attempt 1
    assert stale.status_code == 409 and stale.json()["result"] == "stale"
    assert stale.json()["item"]["card"]["pile"] == "needs_you"
    assert live.get(f"/v1/tasks/{task_id}").json()["status"] == "BLOCKED"


def test_stop_after_uncertain_effect_stays_uncertain(world):
    live, hub, clock = world
    task_id = blocked_task(live, clock)
    assert hub.decide(task_id, "cancel", 1).json()["result"] == "recorded"
    done = hub.home()["done"][0]
    assert done["outcome"] == "outcome_uncertain" and done["mark"] == "gate-question"
    assert live.get(f"/v1/tasks/{task_id}").json()["resolution"] == "cancelled_effect_unknown"
    assert hub.item(task_id).json()["receipt"]["happened"] == "Outcome uncertain"


def test_decision_while_controller_is_down_changes_nothing(tmp_path):
    clock = FakeClock()
    home = tmp_path / "home"
    live = LiveService(home, clock=clock)
    task_id = blocked_task(live, clock)
    base = live.base
    live.stop()
    hub = HubProcess(home, base)
    try:
        answer = hub.decide(task_id, "effect_confirmed", 1)
        assert answer.status_code == 503 and answer.json()["result"] == "offline"
        assert hub.home()["needs_you"][0]["id"] == task_id
    finally:
        hub.stop()


def test_invalid_decisions_are_refused_before_reaching_the_runtime(world):
    live, hub, clock = world
    task_id = blocked_task(live, clock)
    assert hub.decide(task_id, "approve_everything", 1).status_code == 400
    assert hub.post(f"/hub/api/items/{task_id}/decision", {"decision": "cancel"}).status_code == 400
    assert hub.home()["needs_you"][0]["id"] == task_id


# ----------------------------------------- slice 3: truthful Working card
def test_working_card_shows_observable_state_authority_and_stop(world):
    live, hub, clock = world
    task_id = live.post("/v1/tasks", task_body(effect_class="non_idempotent")).json()["task_id"]
    lease = live.post("/v1/claim", {"worker_id": "w1"}).json()
    live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]})
    card = hub.home()["working"][0]
    assert card["label"] == "In progress" and card["last_change"]["what"] == "Courier started the work"
    assert "never repeats this on its own" in card["authority"]["must_ask"][0]
    assert "not available yet" in card["authority"]["note"]
    answer = hub.post(f"/hub/api/items/{task_id}/stop", {})
    assert answer.status_code == 200
    assert hub.home()["working"][0]["phase"] == "stopping"
    assert live.get(f"/v1/tasks/{task_id}").json()["cancel_requested"] is True


# ---------------------------------------------- slice 4: Done receipts
def test_verified_receipt_says_how_courier_knows(world):
    live, hub, clock = world
    task_id = verified_task(live)
    receipt = hub.item(task_id).json()["receipt"]
    assert receipt["happened"] == "Checked by Courier"
    assert receipt["how_known"].startswith("Checked by Courier")
    assert receipt["evidence"] and receipt["evidence"][0]["accepted"] is True
    assert receipt["decisions"] == []


# -------------------------------------------------------------- security
def test_requests_from_other_origins_are_refused(world):
    live, hub, clock = world
    task_id = blocked_task(live, clock)
    no_header = requests.post(f"{hub.base}/hub/api/items/{task_id}/decision",
                              json={"decision": "cancel", "attempt": 1}, timeout=10)
    assert no_header.status_code == 403
    rebinding = requests.get(hub.base + "/hub/api/home", headers={"Host": "evil.example:80"}, timeout=10)
    assert rebinding.status_code == 421
    assert live.get(f"/v1/tasks/{task_id}").json()["status"] == "BLOCKED"


def test_page_is_served_with_a_strict_content_security_policy(world):
    _, hub, _ = world
    page = requests.get(hub.base + "/", timeout=10)
    assert page.status_code == 200 and "script-src 'self'" in page.headers["Content-Security-Policy"]
    assert "<script>" not in page.text  # no inline script
    assert requests.get(hub.base + "/../courier_core/serve.py", timeout=10).status_code == 404


def test_resumed_only_when_courier_actually_continued(world):
    live, hub, clock = world
    task_id = live.post("/v1/tasks", task_body(lease_ttl_s=3)).json()["task_id"]
    first = live.post("/v1/claim", {"worker_id": "w1"}).json()
    live.post("/v1/start", {"dispatch_id": first["dispatch_id"]})
    pass_time(live, clock, 4)  # idempotent: Courier retries by itself
    second = live.post("/v1/claim", {"worker_id": "w2"}).json()
    live.post("/v1/start", {"dispatch_id": second["dispatch_id"]})
    live.post("/v1/result", result_body(second["dispatch_id"], result_id="r2"))
    wait_status(live, task_id, "COMPLETE")
    view = hub.home()
    assert view["done"][0]["mark"] == "check" and view["needs_you"] == []  # recovery never asked anyone
    receipt = hub.item(task_id).json()["receipt"]
    assert receipt["resumed"] is True and receipt["decisions"] == []
