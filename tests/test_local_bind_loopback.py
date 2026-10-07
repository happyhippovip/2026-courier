"""Local-only Courier services bind loopback by default (firewall incident 2026-10-02)."""
import importlib

import pytest


def test_dashboard_binds_loopback():
    server_mod = importlib.import_module("dashboard.server")
    server = server_mod.create_server(0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def test_legacy_server_defaults_to_loopback(monkeypatch):
    app_mod = importlib.import_module("server.app")
    monkeypatch.delenv("COURIER_BIND_HOST", raising=False)
    assert app_mod.bind_host() == "127.0.0.1"


def test_legacy_server_lan_bind_is_an_explicit_opt_in(monkeypatch):
    app_mod = importlib.import_module("server.app")
    monkeypatch.setenv("COURIER_BIND_HOST", "0.0.0.0")
    assert app_mod.bind_host() == "0.0.0.0"


@pytest.mark.parametrize("module, attr", [("courier_core.serve", "ControllerServer"),
                                          ("courier_hub.server", "HubServer")])
def test_v1_services_stay_loopback(module, attr):
    source = importlib.util.find_spec(module).origin
    text = open(source, encoding="utf-8").read()
    assert '("127.0.0.1", port)' in text, f"{module}.{attr} must bind 127.0.0.1"
