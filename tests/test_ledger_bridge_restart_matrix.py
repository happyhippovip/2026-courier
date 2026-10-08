"""Restart the ledger bridge at each durable step. One process death per case.

The bridge is one shot: ``main`` is the public entry, and a new call is a
restart. The controller is an in-memory double. Crash points are the moments
state is already on disk:

- before claim: the process never entered ``main``
- after claim: the claim is in the ledger and the controller post did not land
- after controller dispatch: the controller stored the task and the process
  died before it recorded that fact
- after result write: the controller holds the accepted result and the bridge
  has not receipted it
- after receipt append: the FINAL line is in the ledger and the process died
  before the next claim
- after release: A's ownership is clear, the next unit is claimed, and the
  process died before that unit was dispatched

Every case must end with one claim, one dispatch, and one FINAL per unit, and
the unit chosen after the restart must be the one the ledger still owes.
"""

import hashlib
import json
from collections import Counter

import pytest

from scripts.coordination_ledger import (
    AgentID, CoordinationEvent, EventType, HostID, MissionStatus,
)
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.ledger_v1_bridge import main

TOKEN = "controller-token-value-0123456789abcdef"
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
SHA = "0123456789abcdef0123456789abcdef01234567"
BOUNDARIES = (
    "before_claim",
    "after_claim",
    "after_controller_dispatch",
    "after_result_write",
    "after_receipt_append",
    "after_release",
)


def _event(eid, mid, etype, status, ts, deps=None):
    return CoordinationEvent(
        event_id=eid, mission_id=mid, agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=etype, status=status, depends_on=deps or [], head="sha", evidence_ref="ref",
        created_at=ts, payload_hash="h", ownership=AGENT,
    )


def _spec(unit):
    return {
        "adapter": "synthetic",
        "params": {"unit": unit},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
        "source_sha": SHA,
    }


def _task_id(key):
    return "task-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


class Controller:
    """Loopback stand-in. A failed post or get is the process dying on that call."""

    def __init__(self):
        self.posts = []
        self.views = {}
        self.fail_post = False
        self.fail_get = False

    def __call__(self, method, url, headers, body, timeout):
        assert timeout > 0
        assert headers.get("X-Courier-Token") == TOKEN
        if method == "POST" and url.endswith("/v1/tasks"):
            if self.fail_post:
                raise OSError("killed after claim")
            posted = json.loads(body.decode("utf-8"))
            key = posted["idempotency_key"]
            task_id = _task_id(key)
            duplicate = any(item["idempotency_key"] == key for item in self.posts)
            if not duplicate:
                self.posts.append(posted)
                self.views[task_id] = {
                    "task_id": task_id, "status": "QUEUED", "attempt": 0,
                    "accepted_result_id": None, "last_reason": None,
                }
            return (200 if duplicate else 201), json.dumps(
                {"task_id": task_id, "duplicate": duplicate}).encode()
        if method == "GET" and "/v1/tasks/" in url:
            if self.fail_get:
                raise OSError("killed after dispatch")
            task_id = url.rstrip("/").rsplit("/", 1)[-1]
            view = self.views.get(task_id)
            if view is None:
                return 404, b"{}"
            return 200, json.dumps(view).encode()
        raise AssertionError(method + " " + url)


class _KillOnReceipt:
    """Die once the bridge has asked to emit this outcome, before the log append."""

    def __init__(self, outcome):
        self.outcome = outcome

    def __call__(self, line):
        record = json.loads(line)
        if record.get("outcome") == self.outcome:
            raise RuntimeError("killed after receipt append")


def _home(tmp_path):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text(TOKEN + "\n", encoding="utf-8")
    specs = {"A": _spec("a"), "B": _spec("b")}
    (home / "ledger_tasks.json").write_text(json.dumps(specs), encoding="utf-8")
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    store.write_event(_event("a-assign", "A", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-08T04:00:00Z"))
    store.write_event(_event(
        "b-assign", "B", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-08T04:00:01Z", deps=["A"],
    ))
    return home


def _run(home, http, stdout=None):
    out, err = [], []
    code = main(
        ["--home", str(home), "--agent-id", AGENT, "--host-id", HOST, "--controller", "http://127.0.0.1:9"],
        http=http, stdout=stdout or out.append, stderr=err.append,
    )
    return code, "".join(out), "".join(err)


def _reducer(home):
    return reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))


def _state(home):
    path = home / "ledger_bridge_state.json"
    if not path.exists():
        return {"missions": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _of(home, event_type):
    return [event for event in _reducer(home).events if event.event_type == event_type]


def _units(http):
    return [item["params"]["unit"] for item in http.posts]


def _log(home):
    path = home / "run" / "ledger_bridge.log"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _complete(http, unit, result_id):
    posted = next(item for item in http.posts if item["params"]["unit"] == unit)
    http.views[_task_id(posted["idempotency_key"])].update(
        status="COMPLETE", accepted_result_id=result_id, attempt=1,
    )


def _kill(home, http, boundary):
    if boundary == "before_claim":
        return
    if boundary == "after_claim":
        http.fail_post = True
        assert _run(home, http)[0] == 75
        return
    if boundary == "after_controller_dispatch":
        http.fail_get = True
        assert _run(home, http)[0] == 75
        return
    assert _run(home, http)[0] == 0
    assert _units(http) == ["a"]
    _complete(http, "a", "result-a")
    if boundary == "after_result_write":
        return
    if boundary == "after_receipt_append":
        with pytest.raises(RuntimeError, match="killed after receipt append"):
            _run(home, http, stdout=_KillOnReceipt("final"))
        return
    if boundary == "after_release":
        http.fail_post = True
        assert _run(home, http)[0] == 75
        return
    raise AssertionError(boundary)


def _assert_killed_at(home, http, boundary):
    reducer = _reducer(home)
    missions = _state(home)["missions"]
    started = [event.mission_id for event in _of(home, EventType.STARTED)]
    finals = [event.mission_id for event in _of(home, EventType.FINAL)]
    if boundary == "before_claim":
        assert started == [] and finals == [] and _units(http) == [] and missions == {}
    elif boundary == "after_claim":
        assert started == ["A"] and finals == [] and _units(http) == []
        assert missions["A"]["posted"] is False and "B" not in missions
    elif boundary == "after_controller_dispatch":
        assert started == ["A"] and finals == [] and _units(http) == ["a"]
        assert missions["A"]["posted"] is False and "B" not in missions
    elif boundary == "after_result_write":
        assert started == ["A"] and finals == [] and _units(http) == ["a"]
        assert missions["A"]["posted"] is True and missions["A"]["status"] == "POSTED"
        view = http.views[missions["A"]["task_id"]]
        assert view["status"] == "COMPLETE" and view["accepted_result_id"] == "result-a"
    elif boundary == "after_receipt_append":
        assert started == ["A"] and finals == ["A"] and _units(http) == ["a"]
        assert reducer.get_mission("A")["status"] == MissionStatus.DONE
        assert reducer.get_mission("A")["ownership"] is None
        assert "B" not in missions
        assert not any(record.get("outcome") == "final" for record in _log(home))
    elif boundary == "after_release":
        assert started == ["A", "B"] and finals == ["A"] and _units(http) == ["a"]
        assert reducer.get_mission("A")["status"] == MissionStatus.DONE
        assert reducer.get_mission("A")["ownership"] is None
        assert missions["B"]["posted"] is False
        assert any(record.get("mission_id") == "A" and record.get("outcome") == "final" for record in _log(home))
    else:
        raise AssertionError(boundary)


def _restart_once(home, http, boundary):
    """The first invocation after the death. It must pick the owed unit and add no duplicate."""
    before_finals = [event.event_id for event in _of(home, EventType.FINAL)]
    before_started = [event.event_id for event in _of(home, EventType.STARTED)]
    code, _out, err = _run(home, http)
    assert code == 0, err
    started = [event.mission_id for event in _of(home, EventType.STARTED)]
    finals = [event.event_id for event in _of(home, EventType.FINAL)]
    assert set(before_finals) <= set(finals)
    assert set(before_started) <= {event.event_id for event in _of(home, EventType.STARTED)}
    if boundary in ("before_claim", "after_claim"):
        assert _units(http) == ["a"] and started == ["A"] and finals == before_finals
    elif boundary == "after_controller_dispatch":
        assert _units(http) == ["a"] and started == ["A"] and "B" not in _state(home)["missions"]
    elif boundary == "after_result_write":
        assert _units(http) == ["a", "b"] and started == ["A", "B"]
        assert [event.mission_id for event in _of(home, EventType.FINAL)] == ["A"]
    elif boundary == "after_receipt_append":
        assert _units(http) == ["a", "b"] and started == ["A", "B"] and finals == before_finals
    elif boundary == "after_release":
        assert _units(http) == ["a", "b"] and started == ["A", "B"] and finals == before_finals
    else:
        raise AssertionError(boundary)


def _drain(home, http):
    for _ in range(6):
        reducer = _reducer(home)
        mission_a = reducer.get_mission("A")
        mission_b = reducer.get_mission("B")
        if (
            mission_a and mission_b
            and mission_a["status"] == MissionStatus.DONE
            and mission_b["status"] == MissionStatus.DONE
        ):
            break
        if any(item["params"]["unit"] == "a" for item in http.posts):
            view = http.views[_task_id(next(item["idempotency_key"] for item in http.posts if item["params"]["unit"] == "a"))]
            if view["status"] != "COMPLETE":
                _complete(http, "a", "result-a")
        if any(item["params"]["unit"] == "b" for item in http.posts):
            view = http.views[_task_id(next(item["idempotency_key"] for item in http.posts if item["params"]["unit"] == "b"))]
            if view["status"] != "COMPLETE":
                _complete(http, "b", "result-b")
        code, _out, err = _run(home, http)
        assert code == 0, err
    else:
        raise AssertionError("units did not both finish after restart")
    frozen = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
    frozen_posts = list(http.posts)
    code, _out, err = _run(home, http)
    assert code == 0, err
    assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == frozen
    assert http.posts == frozen_posts


def _assert_exactly_once(home, http):
    reducer = _reducer(home)
    assert reducer.get_mission("A")["status"] == MissionStatus.DONE
    assert reducer.get_mission("B")["status"] == MissionStatus.DONE
    assert reducer.get_mission("A")["ownership"] is None
    assert reducer.get_mission("B")["ownership"] is None
    started = _of(home, EventType.STARTED)
    finals = _of(home, EventType.FINAL)
    assert sorted(event.mission_id for event in started) == ["A", "B"]
    assert sorted(event.mission_id for event in finals) == ["A", "B"]
    assert len({event.event_id for event in started}) == 2
    assert len({event.event_id for event in finals}) == 2
    assert _units(http) == ["a", "b"]
    missions = _state(home)["missions"]
    assert missions["A"]["accepted_result_id"] == "result-a"
    assert missions["B"]["accepted_result_id"] == "result-b"
    assert missions["A"]["idempotency_key"].startswith("ledger:claim-")
    assert missions["B"]["idempotency_key"].startswith("ledger:claim-")
    assert missions["A"]["idempotency_key"] != missions["B"]["idempotency_key"]
    counts = Counter((record["mission_id"], record["outcome"]) for record in _log(home))
    assert all(count == 1 for count in counts.values()), counts
    assert counts["A", "final"] == 1
    assert counts["B", "final"] == 1
    assert counts["B", "queued"] == 1 or counts["B", "duplicate"] == 1


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_bridge_restart_is_exactly_once(tmp_path, boundary):
    http = Controller()
    home = _home(tmp_path)
    _kill(home, http, boundary)
    _assert_killed_at(home, http, boundary)
    http.fail_post = False
    http.fail_get = False
    _restart_once(home, http, boundary)
    _drain(home, http)
    _assert_exactly_once(home, http)
