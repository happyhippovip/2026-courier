"""Regression for #139 (thermal relief): the worker must still talk to the real V1 controller.

#139 made WorkerLoop.iterate call ``self.host`` (does not exist), read an uninitialised
``_cooldown_until`` and send ``resource_state`` on /claim and /heartbeat, which the V1
controller rejects as unknown fields. Every tick then crashed or idled, and no task ever
completed. ``tests/golden`` would catch it but skips on CI, so this test runs everywhere:
it routes ControllerClient calls into a booted, in-process ``courier_core`` Controller.
"""
from __future__ import annotations

import threading

from courier_core.controller import ApiError, Controller
from courier_worker import host as H
from courier_worker import service as S

ROUTES = {"/claim": "claim", "/heartbeat": "heartbeat"}


class RoutedClient(S.ControllerClient):
    """ControllerClient whose wire calls land on a real Controller; errors are recorded."""

    def __init__(self, controller: Controller):
        super().__init__("http://127.0.0.1:9", "unused-token")
        self.controller = controller
        self.errors: list = []
        self.paths: list = []

    def _call(self, method, path, body=None):  # noqa: D401 - same shape as the parent
        self.paths.append(path)
        try:
            result = getattr(self.controller, ROUTES[path])(body)
        except ApiError as exc:
            self.errors.append((path, exc.status, exc.code, exc.message))
            return exc.status, exc.body()
        return (204, None) if result is None else (200, result)


def _controller(tmp_path):
    return Controller(tmp_path / "controller").boot()


def _loop(tmp_path, client, probe):
    home = tmp_path / "worker"
    home.mkdir()
    engine = H.WorkerHost(str(home), pressure_probe=probe)
    return S.WorkerLoop(str(home), "http://127.0.0.1:9", "w-139", 0.2,
                        engine=engine, client_factory=lambda: client)


def test_client_bodies_are_accepted_by_the_v1_controller(tmp_path):
    client = RoutedClient(_controller(tmp_path))
    assert client.claim("w-139") is None                      # empty queue -> 204
    assert client.claim("w-139", resource_state="NORMAL") is None
    assert isinstance(client.heartbeat("w-139", [], resource_state="PRESSURED"), dict)
    assert isinstance(client.heartbeat("w-139", []), dict)
    assert client.errors == []


def test_iterate_on_a_healthy_host_reaches_the_controller_without_errors(tmp_path):
    client = RoutedClient(_controller(tmp_path))
    loop = _loop(tmp_path, client, lambda: None)
    assert loop.iterate(threading.Event()) == "idle"
    assert "/claim" in client.paths
    assert client.errors == []
    assert loop._last_resource_state == "NORMAL"


def test_pressure_then_cooldown_never_claims_and_stays_accepted(tmp_path):
    client = RoutedClient(_controller(tmp_path))
    loop = _loop(tmp_path, client, lambda: "thermal-pressure: speed limit 50%")
    assert loop.iterate(threading.Event()) == "idle"
    assert loop._last_resource_state == "PRESSURED"
    loop.engine._pressure_probe = lambda: None
    assert loop.iterate(threading.Event()) == "idle"
    assert loop._last_resource_state == "COOLDOWN"
    assert "/claim" not in client.paths
    assert client.paths and set(client.paths) == {"/heartbeat"}
    assert client.errors == []
