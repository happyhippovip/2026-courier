"""Dedicated tests for mcp/server.py (P9: mcp.server).

Covers the stdio JSON-RPC bridge without network: tool listing, unknown
tools, status/claim HTTP paths (mocked) including failure modes, and the
stdin main loop's blank/malformed-line handling.
"""

import io
import json
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

from mcp.server import handle_request, main


def _call(req):
    buf = io.StringIO()
    with redirect_stdout(buf):
        handle_request(req)
    return json.loads(buf.getvalue().strip().splitlines()[-1])


def test_tools_list_names_both_tools():
    out = _call({"method": "tools/list", "params": {}})
    names = {t["name"] for t in out["tools"]}
    assert names == {"mcp_courier_status", "mcp_courier_claim"}


def test_unknown_tool_is_error_not_crash():
    out = _call({"method": "tools/call",
                 "params": {"name": "nope", "arguments": {}}})
    assert out == {"error": "Unknown tool"}


def test_unknown_method_is_silent():
    buf = io.StringIO()
    with redirect_stdout(buf):
        handle_request({"method": "bogus", "params": {}})
    assert buf.getvalue() == ""


def test_status_returns_server_payload():
    fake = mock.MagicMock()
    fake.read.return_value = json.dumps({"tasks": 3}).encode()
    fake.__enter__.return_value = fake
    with mock.patch("mcp.server.urllib.request.urlopen", return_value=fake):
        out = _call({"method": "tools/call",
                     "params": {"name": "mcp_courier_status",
                                "arguments": {}}})
    assert json.loads(out["content"][0]["text"]) == {"tasks": 3}


def test_status_connection_refused_is_error_payload():
    with mock.patch("mcp.server.urllib.request.urlopen",
                    side_effect=urllib.error.URLError("refused")):
        out = _call({"method": "tools/call",
                     "params": {"name": "mcp_courier_status",
                                "arguments": {}}})
    assert "refused" in out["error"]


def test_claim_posts_worker_id_default():
    seen = {}

    def fake_urlopen(req, *a, **k):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode())
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps({"claimed": 1}).encode()
        resp.__enter__.return_value = resp
        return resp

    with mock.patch("mcp.server.urllib.request.urlopen",
                    side_effect=fake_urlopen):
        out = _call({"method": "tools/call",
                     "params": {"name": "mcp_courier_claim",
                                "arguments": {}}})
    assert seen["url"].endswith("/tasks/claim")
    assert seen["body"] == {"worker_id": "mcp-agent"}
    assert json.loads(out["content"][0]["text"]) == {"claimed": 1}


def test_main_skips_blank_and_malformed_lines(monkeypatch, capsys):
    payload = json.dumps({"method": "tools/list", "params": {}})
    monkeypatch.setattr("sys.stdin", io.StringIO("\nnot-json\n" + payload + "\n"))
    main()
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert "mcp_courier_status" in out[0]
