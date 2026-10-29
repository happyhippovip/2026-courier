"""P9 test hardening for courier_core.serve main() argv handling.

Tests only; no behavior change.

``courier_core.serve.main`` parses the controller CLI
(``--home`` / ``--port`` / ``--print-port``) fail-closed:
a missing home or an out-of-range port ends in ``SystemExit(2)`` before any
socket is bound or any lock is taken. Valid arguments reach
``Service(home, port)`` with the documented defaults, ``--print-port``
emits the bound port, and a held home lock (``SystemExit`` from ``Service``)
propagates instead of becoming a success code.

No sockets, no subprocesses, no network: ``Service`` is stubbed out, so no
port is ever bound and no controller ever starts.
"""

from __future__ import annotations

import signal
from pathlib import Path

import pytest

import courier_core.serve as serve


class _StubController:
    mode = "prod"
    degraded_reason = ""


class _StubService:
    """Stand-in for serve.Service: records construction, never binds."""

    instances = []

    def __init__(self, home, port, controller=None):
        self.home = home
        self.port_arg = port
        self.controller = _StubController()
        type(self).instances.append(self)
        self.ran = False

    @property
    def port(self):
        return 51999

    def run(self):
        self.ran = True


@pytest.fixture()
def stub_service(monkeypatch):
    _StubService.instances.clear()
    monkeypatch.setattr(serve, "Service", _StubService)
    # main() installs SIGTERM/SIGINT handlers in-process; record instead.
    installed = {}
    monkeypatch.setattr(signal, "signal",
                        lambda signum, handler: installed.setdefault(signum, handler))
    return _StubService, installed


def _no_courier_home(monkeypatch):
    monkeypatch.delenv("COURIER_HOME", raising=False)
    monkeypatch.delenv("COURIER_LOG_LEVEL", raising=False)


def test_missing_home_without_env_exits_2(stub_service, monkeypatch):
    _no_courier_home(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        serve.main(["--port", "0"])
    assert exc.value.code == 2
    assert _StubService.instances == []


def test_missing_home_usage_names_flag(stub_service, monkeypatch, capsys):
    _no_courier_home(monkeypatch)
    with pytest.raises(SystemExit):
        serve.main([])
    assert "--home" in capsys.readouterr().err


def test_port_above_max_exits_2(stub_service, monkeypatch, tmp_path):
    _no_courier_home(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        serve.main(["--home", str(tmp_path), "--port", "65536"])
    assert exc.value.code == 2
    assert _StubService.instances == []


def test_negative_port_exits_2(stub_service, monkeypatch, tmp_path):
    _no_courier_home(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        serve.main(["--home", str(tmp_path), "--port", "-1"])
    assert exc.value.code == 2
    assert _StubService.instances == []


def test_non_integer_port_exits_2(stub_service, monkeypatch, tmp_path):
    _no_courier_home(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        serve.main(["--home", str(tmp_path), "--port", "abc"])
    assert exc.value.code == 2
    assert _StubService.instances == []


def test_port_boundaries_reach_service(stub_service, monkeypatch, tmp_path):
    _no_courier_home(monkeypatch)
    for port in ("0", "1", "65535"):
        _StubService.instances.clear()
        assert serve.main(["--home", str(tmp_path), "--port", port]) == 0
        assert len(_StubService.instances) == 1
        assert _StubService.instances[0].port_arg == int(port)
        assert _StubService.instances[0].ran is True


def test_home_reaches_service_resolved(stub_service, monkeypatch, tmp_path):
    _no_courier_home(monkeypatch)
    assert serve.main(["--home", str(tmp_path)]) == 0
    (stub, _installed) = stub_service
    assert len(stub.instances) == 1
    assert stub.instances[0].home == Path(str(tmp_path)).expanduser().resolve()
    assert stub.instances[0].port_arg == 0


def test_home_defaults_to_courier_home_env(stub_service, monkeypatch, tmp_path):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    assert serve.main([]) == 0
    (stub, _installed) = stub_service
    assert stub.instances[0].home == Path(str(tmp_path)).expanduser().resolve()


def test_empty_courier_home_still_required(stub_service, monkeypatch, tmp_path):
    monkeypatch.setenv("COURIER_HOME", "")
    with pytest.raises(SystemExit) as exc:
        serve.main(["--port", "0"])
    assert exc.value.code == 2
    assert _StubService.instances == []


def test_print_port_emits_bound_port(stub_service, monkeypatch, tmp_path, capsys):
    _no_courier_home(monkeypatch)
    assert serve.main(["--home", str(tmp_path), "--port", "0", "--print-port"]) == 0
    assert capsys.readouterr().out.strip() == "51999"


def test_no_print_port_flag_prints_nothing(stub_service, monkeypatch, tmp_path, capsys):
    _no_courier_home(monkeypatch)
    assert serve.main(["--home", str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""


def test_held_lock_system_exit_propagates(stub_service, monkeypatch, tmp_path):
    _no_courier_home(monkeypatch)

    def _locked(home, port, controller=None):
        raise SystemExit(f"another Courier controller already owns {home}")

    monkeypatch.setattr(serve, "Service", _locked)
    with pytest.raises(SystemExit) as exc:
        serve.main(["--home", str(tmp_path)])
    assert "already owns" in str(exc.value.code)


def test_signal_handlers_are_wired(stub_service, monkeypatch, tmp_path):
    _no_courier_home(monkeypatch)
    assert serve.main(["--home", str(tmp_path)]) == 0
    (_stub, installed) = stub_service
    assert signal.SIGTERM in installed
    assert signal.SIGINT in installed
