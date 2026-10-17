"""An undecodable or unmapped task state must not take Home down.

A journal written by a newer controller can hold a status this hub cannot
decode. That is a truth-read failure, not an internal error. A status the
model cannot file is one unrecognised card, and the other tasks still render.
"""

import http.client
import json
import sqlite3
import threading
from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub import model
from courier_hub.server import Hub, HubServer, TruthUnavailable

_PAYLOAD = {
    "adapter": "synthetic",
    "params": {"title": "Carry the parcel"},
    "effect_class": "idempotent",
    "max_attempts": 3,
    "lease_ttl_s": 6,
}


def _journal(tmp_path, count=3):
    home = tmp_path / "home"
    with Journal(home / "courier.db") as journal:
        for i in range(count):
            journal.append(Event(
                type=EventType.TASK_CREATED,
                task_id=f"t{i}",
                payload={**_PAYLOAD, "params": {"title": f"Task {i}"}},
            ))
    return home


def _set_status(home, task_id, status):
    conn = sqlite3.connect(home / "courier.db")
    try:
        conn.execute("UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id))
        conn.commit()
    finally:
        conn.close()


def _hub(home):
    return Hub(home, "http://127.0.0.1:9", actor="desktop:tester")


def _no_internal_error(payload):
    text = json.dumps(payload)
    assert "internal error" not in text.lower()
    assert "Traceback" not in text
    assert "ValueError" not in text


def test_unknown_stored_status_makes_home_unavailable_not_an_internal_error(tmp_path):
    home = _journal(tmp_path)
    _set_status(home, "t1", "TELEPORTED")
    view = _hub(home).home_view()
    assert view["truth"] == "unreadable"
    assert view["needs_you"] == [] and view["working"] == [] and view["done"] == []
    _no_internal_error(view)


def test_unknown_stored_status_item_is_unavailable_not_an_internal_error(tmp_path):
    home = _journal(tmp_path)
    _set_status(home, "t1", "TELEPORTED")
    hub = _hub(home)
    with pytest.raises(TruthUnavailable) as raised:
        hub.item_view("t1")
    assert raised.value.args == ("unreadable",)

    server = HubServer(hub, 0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/hub/api/items/t1")
        response = conn.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        assert response.status == 503
        assert body["result"] == "unavailable"
        assert body["truth"] == "unreadable"
        _no_internal_error(body)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_one_unmapped_status_is_an_unrecognised_card_and_home_stays_up(tmp_path, monkeypatch):
    home = _journal(tmp_path)
    real = model.pile_of

    def pile_of(task):
        task_id = task["task_id"] if isinstance(task, dict) else task.task_id
        if task_id == "t1":
            raise ValueError("status not mapped by this hub")
        return real(task)

    monkeypatch.setattr(model, "pile_of", pile_of)
    view = _hub(home).home_view()
    assert view["truth"] == "ok"
    odd = [card for card in view["working"] if card["id"] == "t1"]
    assert len(odd) == 1
    assert odd[0]["phase"] == "unrecognised"
    assert odd[0]["stop"] is None
    others = {card["id"] for card in view["working"] if card["id"] != "t1"}
    assert others == {"t0", "t2"}
    assert all(card["phase"] != "unrecognised" for card in view["working"] if card["id"] != "t1")
    _no_internal_error(view)
