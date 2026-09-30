"""fetch_artifact retries transient transport errors only (AUTO-103)."""
import importlib.util
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent


def load_verifier(monkeypatch):
    # Production runs the verifier with scripts/ on sys.path (resource_governor).
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    spec = importlib.util.spec_from_file_location(
        "courier_verifier_retry_under_test", ROOT / "scripts" / "courier_verifier.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeResponse:
    def __init__(self, payload=None, content=b"", fail=None):
        self._payload = payload
        self.content = content
        self._fail = fail

    def raise_for_status(self):
        if self._fail is not None:
            raise self._fail

    def json(self):
        return self._payload


def test_fetch_retries_transient_timeout_then_succeeds(monkeypatch):
    v = load_verifier(monkeypatch)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith("/meta") and len([c for c in calls if c.endswith("/meta")]) == 1:
            raise requests.exceptions.Timeout("boom")
        if url.endswith("/meta"):
            return FakeResponse(payload={"artifact_id": "a1"})
        return FakeResponse(content=b"data")

    monkeypatch.setattr(v.requests, "get", fake_get)
    meta, blob = v.fetch_artifact("a1")
    assert meta == {"artifact_id": "a1"}
    assert blob == b"data"
    assert len([c for c in calls if c.endswith("/meta")]) == 2


def test_fetch_does_not_retry_http_errors(monkeypatch):
    v = load_verifier(monkeypatch)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(fail=requests.exceptions.HTTPError("500"))

    monkeypatch.setattr(v.requests, "get", fake_get)
    with pytest.raises(requests.exceptions.HTTPError):
        v.fetch_artifact("a1")
    assert len(calls) == 1


def test_fetch_gives_up_after_bounded_attempts(monkeypatch):
    v = load_verifier(monkeypatch)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(v.requests, "get", fake_get)
    monkeypatch.setattr(v, "FETCH_BACKOFF_SECONDS", (0, 0))
    with pytest.raises(requests.exceptions.ConnectionError):
        v.fetch_artifact("a1")
    assert len(calls) == v.FETCH_MAX_ATTEMPTS
