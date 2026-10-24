"""O7-16 (W14): a result without the receiver's ACK is not "delivered".

The server answers POST /tasks/result with 200 {"status": "ACK_RESULT_RECEIVED"}
or {"status": "ACK_DUPLICATE"} (server/app.py:514-577, read only;
docs/SVSD_COURIER_E2E.md:107). The Windows worker
(scripts/windows_worker/daemon.py:202-224, http_post_result) returns DELIVERED for
*any* 2xx and never reads the body; the main loop then deletes the only local
copy of the result (daemon.py:771-774, state_file.unlink()). A 200 without an
ACK (proxy/captive page, wrong service on the port, an error body with 200)
loses the result while the worker believes it was delivered.
PR #845 pins the ACK *crash* paths (after a real ACK); this pins the missing ACK.
No network: urlopen is replaced. W14 patch not applied.
"""
import io
import urllib.error

import pytest

from tests.test_windows_costgate_and_writer_lease import load_daemon


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def getcode(self):
        return self.status


def _daemon(tmp_path, monkeypatch, body=None, http_error=None):
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon, "require_api_key", lambda: None)
    monkeypatch.setattr(daemon, "API_URL", "http://127.0.0.1:9")   # never contacted: urlopen is replaced
    monkeypatch.setattr(daemon.time, "sleep", lambda s: None)

    def fake_urlopen(req, data=None, timeout=None):
        if http_error is not None:
            raise urllib.error.HTTPError(req.full_url, http_error, "err", {}, io.BytesIO(b"{}"))
        return _Resp(body)
    monkeypatch.setattr(daemon.urllib.request, "urlopen", fake_urlopen)
    return daemon


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-16/W14: any 2xx counts as DELIVERED, the ACK body is never checked")
@pytest.mark.parametrize("body", [b"<html>captive portal</html>", b'{"error": "not the courier hub"}', b""])
def test_2xx_without_ack_is_not_delivered(tmp_path, monkeypatch, body):
    daemon = _daemon(tmp_path, monkeypatch, body=body)
    assert daemon.http_post_result({"task_id": "t", "result_id": "r"}) != "DELIVERED"


@pytest.mark.parametrize("ack", [b'{"status": "ACK_RESULT_RECEIVED"}', b'{"status": "ACK_DUPLICATE"}'])
def test_guard_real_ack_is_delivered(tmp_path, monkeypatch, ack):
    daemon = _daemon(tmp_path, monkeypatch, body=ack)
    assert daemon.http_post_result({"task_id": "t", "result_id": "r"}) == "DELIVERED"


def test_guard_4xx_is_rejected_not_delivered(tmp_path, monkeypatch):
    daemon = _daemon(tmp_path, monkeypatch, http_error=409)
    assert daemon.http_post_result({"task_id": "t", "result_id": "r"}) == "REJECTED"
