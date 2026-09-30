"""Verifier per-task backoff: a stuck task must not re-verify every poll (Wave 4 H3)."""
import importlib.util
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class LoopDone(Exception):
    pass


class Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


TASK = {"task_id": "t1", "capabilities": [],
        "result": {"result_id": "r1", "artifacts": []}}


@pytest.fixture
def verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    spec = importlib.util.spec_from_file_location(
        "courier_verifier_backoff_under_test",
        ROOT / "scripts" / "courier_verifier.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_polls(verifier, monkeypatch, post_status, n_polls=6):
    posts = []

    def fake_get(url, **kwargs):
        return Resp(200, {"tasks": [dict(TASK)]})

    def fake_post(url, **kwargs):
        posts.append(kwargs.get("json", {}))
        return Resp(post_status, text="err" if post_status != 200 else "")

    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= n_polls:
            raise LoopDone()

    monkeypatch.setattr(verifier.requests, "get", fake_get)
    monkeypatch.setattr(verifier.requests, "post", fake_post)
    monkeypatch.setattr(time, "sleep", fake_sleep)
    with pytest.raises(LoopDone):
        verifier.run_loop()
    return posts


def test_backoff_helpers(verifier):
    assert not verifier._should_skip_task("t", 0)
    verifier._record_task_failure("t", 0)
    verifier._record_task_failure("t", 1)
    assert not verifier._should_skip_task("t", 2)
    verifier._record_task_failure("t", 2)
    assert verifier._should_skip_task("t", 3)
    assert not verifier._should_skip_task("t", 2 + verifier.SUBMIT_BACKOFF_POLLS)
    verifier._record_task_success("t")
    assert not verifier._should_skip_task("t", 3)


def test_stuck_submit_is_rate_limited(verifier, monkeypatch):
    posts = run_polls(verifier, monkeypatch, post_status=500, n_polls=6)
    # 3 attempts (polls 0-2), then backoff: unfixed code would POST 6 times.
    assert len(posts) == verifier.SUBMIT_MAX_FAILURES == 3


def test_successful_submit_keeps_processing(verifier, monkeypatch):
    posts = run_polls(verifier, monkeypatch, post_status=200, n_polls=4)
    assert len(posts) == 4
    assert verifier._task_skip_until == {}
