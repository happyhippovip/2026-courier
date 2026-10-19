"""Read-only Courier MCP server: tools, auth, demo mode, fail-closed reads."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from courier_mcp import server as srv
from courier_mcp.state import MAX_STATE_BYTES, STATE_NAME
from courier_mcp.tools import TOOLS, Source, ToolError, call_tool

TOKEN = "t" * 40
NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


def _stamp(minutes):
    return (NOW - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(tmp_path, missions):
    (tmp_path / STATE_NAME).write_text(json.dumps({"missions": missions}), encoding="utf-8")
    return Source(state_dir=tmp_path)


def _missions():
    return {
        "m1": {"task_id": "t1", "status": "FINAL_DONE", "updated_at": _stamp(30),
               "accepted_result_id": "r1", "evidence_ref": "e1", "goal_id": "g1"},
        "m2": {"task_id": "t2", "status": "POSTED", "updated_at": _stamp(2)},
    }


# ---- tools ------------------------------------------------------------------

def test_tool_list_is_read_only_and_complete():
    names = {tool["name"] for tool in TOOLS}
    assert names == {"courier_about", "courier_status", "list_missions", "get_mission",
                     "list_receipts", "receipts_summary"}
    for tool in TOOLS:
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["destructiveHint"] is False


def test_courier_about_is_public_text():
    payload = call_tool(Source(demo=True), "courier_about", {}, now=NOW)
    assert payload["tagline"] == "Ideas travel further."
    assert payload["data"] == "DEMO"


def test_status_running_and_counts(tmp_path):
    source = _write(tmp_path, _missions())
    card = call_tool(source, "courier_status", {}, now=NOW)["card"]
    assert card["state"] == "RUNNING" and card["in_flight"] == 1
    summary = call_tool(source, "receipts_summary", {}, now=NOW)
    assert summary["counts"] == {"POSTED": 1, "FINAL_DONE": 1, "BLOCKED": 0, "ERROR": 0}
    assert summary["receipts"] == 1 and summary["last_updated"] == _stamp(2)


def test_status_precedence_error_blocked_stale_idle(tmp_path):
    missions = _missions()
    missions["m3"] = {"task_id": "t3", "status": "BLOCKED", "reason": "GOAL_PAIR", "updated_at": _stamp(1)}
    assert call_tool(_write(tmp_path, missions), "courier_status", {}, now=NOW)["card"]["state"] == "BLOCKED"
    missions["m4"] = {"task_id": "t4", "status": "ERROR", "reason": "FAILED", "updated_at": _stamp(1)}
    card = call_tool(_write(tmp_path, missions), "courier_status", {}, now=NOW)["card"]
    assert card["state"] == "ATTENTION" and card["reason"] == "ERROR" and card["reason_codes"] == ["FAILED"]
    stale = {"m": {"task_id": "t", "status": "POSTED", "updated_at": _stamp(60)}}
    assert call_tool(_write(tmp_path, stale), "courier_status", {}, now=NOW)["card"]["reason"] == "STALE"
    idle = {"m": {"task_id": "t", "status": "FINAL_DONE", "updated_at": _stamp(60)}}
    assert call_tool(_write(tmp_path, idle), "courier_status", {}, now=NOW)["card"]["state"] == "IDLE"
    future = {"m": {"task_id": "t", "status": "POSTED", "updated_at": _stamp(-30)}}
    assert call_tool(_write(tmp_path, future), "courier_status", {}, now=NOW)["card"]["reason"] == "CLOCK"


def test_list_and_get_missions(tmp_path):
    source = _write(tmp_path, _missions())
    listed = call_tool(source, "list_missions", {}, now=NOW)
    assert [m["mission_id"] for m in listed["missions"]] == ["m2", "m1"]
    only = call_tool(source, "list_missions", {"status": "FINAL_DONE", "limit": 1}, now=NOW)
    assert only["total"] == 1 and only["missions"][0]["mission_id"] == "m1"
    found = call_tool(source, "get_mission", {"mission_id": "m1"}, now=NOW)
    assert found["found"] is True and found["mission"]["task_id"] == "t1"
    missing = call_tool(source, "get_mission", {"mission_id": "nope"}, now=NOW)
    assert missing == {"source": "OK", "readable": True, "found": False, "mission": None}


def test_list_receipts_only_accepted(tmp_path):
    receipts = call_tool(_write(tmp_path, _missions()), "list_receipts", {}, now=NOW)
    assert receipts["total"] == 1
    assert receipts["receipts"][0]["accepted_result_id"] == "r1"


def test_legacy_rows_without_status_are_derived(tmp_path):
    source = _write(tmp_path, {"a": {"task_id": "ta", "accepted_result_id": "r"}, "b": {"task_id": "tb"}})
    statuses = {m["mission_id"]: m["status"] for m in call_tool(source, "list_missions", {}, now=NOW)["missions"]}
    assert statuses == {"a": "FINAL_DONE", "b": "POSTED"}


@pytest.mark.parametrize("arguments", [{"limit": 0}, {"limit": 101}, {"limit": True}, {"status": "DONE"},
                                       {"extra": 1}, ["x"]])
def test_invalid_arguments_are_rejected(tmp_path, arguments):
    with pytest.raises(ToolError):
        call_tool(_write(tmp_path, _missions()), "list_missions", arguments, now=NOW)


# ---- fail closed --------------------------------------------------------------

def test_absent_file_is_not_configured(tmp_path):
    payload = call_tool(Source(state_dir=tmp_path), "courier_status", {}, now=NOW)
    assert payload["source"] == "ABSENT" and payload["card"]["state"] == "NOT_CONFIGURED"


@pytest.mark.parametrize("content", [
    "not json",
    json.dumps({"missions": {"m": {"task_id": "t", "status": "WEIRD"}}}),
    json.dumps({"missions": {"m": {"task_id": "t", "reason": "SURPRISE"}}}),
    json.dumps({"missions": {"m": {"task_id": "t", "updated_at": "yesterday"}}}),
    json.dumps({"missions": {"a": {"task_id": "t"}, "b": {"task_id": "t"}}}),
    json.dumps({"missions": {"m": {"task_id": 5}}}),
    json.dumps({"missions": {}, "extra": 1}),
])
def test_bad_state_is_unreadable(tmp_path, content):
    (tmp_path / STATE_NAME).write_text(content, encoding="utf-8")
    source = Source(state_dir=tmp_path)
    status = call_tool(source, "courier_status", {}, now=NOW)
    assert status["readable"] is False and status["card"]["reason"] == "UNREADABLE"
    assert call_tool(source, "list_missions", {}, now=NOW)["missions"] == []


def test_oversized_state_is_unreadable(tmp_path):
    (tmp_path / STATE_NAME).write_bytes(b" " * (MAX_STATE_BYTES + 1))
    assert call_tool(Source(state_dir=tmp_path), "receipts_summary", {}, now=NOW)["readable"] is False


def test_symlinked_state_is_unreadable(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"missions": _missions()}), encoding="utf-8")
    inside = tmp_path / "state"
    inside.mkdir()
    try:
        (inside / STATE_NAME).symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    assert call_tool(Source(state_dir=inside), "list_missions", {}, now=NOW)["readable"] is False


# ---- start-up refusal -----------------------------------------------------------

def _config(argv, env):
    return srv.build_config(srv.parse_args(argv), env)


def test_refuses_without_token(tmp_path, capsys):
    assert srv.main(["--state-dir", str(tmp_path)], environ={}) == 2
    assert "COURIER_MCP_TOKEN is required" in capsys.readouterr().err


def test_refuses_short_token(tmp_path):
    with pytest.raises(srv.ConfigError):
        _config(["--state-dir", str(tmp_path)], {"COURIER_MCP_TOKEN": "short"})


def test_refuses_without_state_dir():
    with pytest.raises(srv.ConfigError):
        _config([], {"COURIER_MCP_TOKEN": TOKEN})


def test_demo_rejects_state_dir_and_public_bind_without_token(tmp_path):
    with pytest.raises(srv.ConfigError):
        _config(["--demo", "--state-dir", str(tmp_path)], {})
    with pytest.raises(srv.ConfigError):
        _config(["--demo", "--host", "192.0.2.1"], {})
    assert _config(["--demo"], {}).token is None


def test_refusal_message_never_contains_token(tmp_path, capsys):
    secret = "s" * 10
    assert srv.main(["--state-dir", str(tmp_path)], environ={"COURIER_MCP_TOKEN": secret}) == 2
    assert secret not in capsys.readouterr().err


# ---- HTTP transport -------------------------------------------------------------

@pytest.fixture()
def running():
    started = []

    def start(argv, env):
        config = _config(argv, env)
        server = srv.make_server(config, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in started:
        server.shutdown()
        server.server_close()


def _post(url, body, token=TOKEN, headers=None):
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None


def test_demo_handshake_and_every_tool(running):
    base = running(["--demo"], {"COURIER_MCP_TOKEN": TOKEN}) + "/mcp"
    status, body = _post(base, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                           "clientInfo": {"name": "test", "version": "0"}}})
    assert status == 200 and body["result"]["protocolVersion"] == "2025-06-18"
    assert body["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert _post(base, {"jsonrpc": "2.0", "method": "notifications/initialized"})[0] == 202
    status, body = _post(base, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(body["result"]["tools"]) == 6
    for index, tool in enumerate(TOOLS):
        args = {"mission_id": "demo-mission-001"} if tool["name"] == "get_mission" else {}
        status, body = _post(base, {"jsonrpc": "2.0", "id": 10 + index, "method": "tools/call",
                                    "params": {"name": tool["name"], "arguments": args}})
        assert status == 200 and body["result"]["isError"] is False, tool["name"]
        payload = json.loads(body["result"]["content"][0]["text"])
        assert payload == body["result"]["structuredContent"]
        if tool["name"] != "courier_about":
            assert payload["source"] == "DEMO"
    status, body = _post(base, {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                                "params": {"name": "courier_status", "arguments": {}}})
    assert body["result"]["structuredContent"]["card"]["state"] == "RUNNING"


def test_auth_is_required(running):
    base = running(["--demo"], {"COURIER_MCP_TOKEN": TOKEN}) + "/mcp"
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert _post(base, ping, token=None)[0] == 401
    assert _post(base, ping, token="x" * 40)[0] == 401
    assert _post(base, ping)[0] == 200
    assert _post(base + "/" + TOKEN, ping, token=None)[0] == 404  # path token is opt-in


def test_path_token_opt_in(running):
    base = running(["--demo", "--allow-path-token"], {"COURIER_MCP_TOKEN": TOKEN}) + "/mcp/"
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert _post(base + TOKEN, ping, token=None)[0] == 200
    assert _post(base + "y" * 40, ping, token=None)[0] == 401


def test_transport_rules(running):
    base = running(["--demo"], {"COURIER_MCP_TOKEN": TOKEN}) + "/mcp"
    assert _post(base, [{"jsonrpc": "2.0", "id": 1, "method": "ping"}])[0] == 400
    assert _post(base, {"jsonrpc": "2.0", "id": 1, "method": "nope"})[1]["error"]["code"] == -32601
    status, body = _post(base, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "rm_rf", "arguments": {}}})
    assert body["error"]["code"] == -32602
    status, body = _post(base, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "list_missions", "arguments": {"limit": 0}}})
    assert body["result"]["isError"] is True
    assert _post(base, {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                 headers={"Origin": "https://evil.example"})[0] == 403
    assert _post(base, {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                 headers={"MCP-Protocol-Version": "1999-01-01"})[0] == 400
    try:
        urllib.request.urlopen(base, timeout=10)
        raise AssertionError("GET must not succeed")
    except urllib.error.HTTPError as exc:
        assert exc.code == 405


def test_state_dir_mode_over_http(running, tmp_path):
    (tmp_path / STATE_NAME).write_text(json.dumps({"missions": _missions()}), encoding="utf-8")
    base = running(["--state-dir", str(tmp_path)], {"COURIER_MCP_TOKEN": TOKEN}) + "/mcp"
    status, body = _post(base, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "list_missions", "arguments": {}}})
    assert body["result"]["structuredContent"]["source"] == "OK"
    assert body["result"]["structuredContent"]["total"] == 2


def test_rejected_request_does_not_poison_keep_alive(running):
    import http.client
    base = running(["--demo"], {"COURIER_MCP_TOKEN": TOKEN})
    port = int(base.rsplit(":", 1)[1])
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    conn.request("POST", "/mcp", body=body, headers={"Content-Type": "application/json",
                                                     "Authorization": "Bearer " + "x" * 40})
    first = conn.getresponse()
    first.read()
    assert first.status == 401
    assert first.getheader("Connection") == "close"
    conn.close()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", "/mcp", body=body, headers={"Content-Type": "application/json",
                                                     "Authorization": "Bearer " + TOKEN})
    second = conn.getresponse()
    assert second.status == 200 and json.loads(second.read())["result"] == {}
    conn.close()
