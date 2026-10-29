"""P9 pins for courier_worker.service: main() argv contract (offline only).

Tests only; no behavior change. No network calls and no filesystem writes:
invalid argv exits via argparse before any object is built, and valid-argv
paths run against a stubbed WorkerLoop so no home lock, token read, or
controller contact happens.
"""

import pytest

import courier_worker.service as S


def _exits_2(argv):
    with pytest.raises(SystemExit) as excinfo:
        S.main(argv)
    assert excinfo.value.code == 2


def test_missing_controller_exits_2():
    _exits_2([])


def test_max_tasks_not_one_exits_2():
    base = ["--controller", "http://127.0.0.1:9"]
    for bad in ("0", "2", "3"):
        _exits_2(base + ["--max-tasks", bad])


def test_max_tasks_non_integer_exits_2():
    _exits_2(["--controller", "http://127.0.0.1:9", "--max-tasks", "many"])


def test_heartbeat_below_min_exits_2():
    _exits_2(["--controller", "http://127.0.0.1:9", "--heartbeat", "0.1"])


def test_heartbeat_above_max_exits_2():
    _exits_2(["--controller", "http://127.0.0.1:9", "--heartbeat", "30.1"])


def test_heartbeat_non_numeric_exits_2():
    _exits_2(["--controller", "http://127.0.0.1:9", "--heartbeat", "fast"])


class _LoopStub:
    seen = None

    def __init__(self, home, base_url, worker_id, heartbeat_s):
        type(self).seen = {
            "home": home,
            "base_url": base_url,
            "worker_id": worker_id,
            "heartbeat_s": heartbeat_s,
        }

    def run(self, stop=None):
        return 7


@pytest.fixture
def stub_loop(monkeypatch):
    _LoopStub.seen = None
    monkeypatch.setattr(S, "WorkerLoop", _LoopStub)
    return _LoopStub


def test_valid_args_reach_loop(tmp_path, stub_loop):
    rc = S.main(["--controller", "http://127.0.0.1:9",
                 "--home", str(tmp_path),
                 "--worker-id", "w-1", "--heartbeat", "2.0"])
    assert rc == 7
    assert stub_loop.seen == {
        "home": str(tmp_path),
        "base_url": "http://127.0.0.1:9",
        "worker_id": "w-1",
        "heartbeat_s": 2.0,
    }


def test_heartbeat_boundaries_accepted(tmp_path, stub_loop):
    for edge in ("0.2", "30.0"):
        rc = S.main(["--controller", "http://127.0.0.1:9",
                     "--home", str(tmp_path), "--heartbeat", edge])
        assert rc == 7
        assert stub_loop.seen["heartbeat_s"] == float(edge)


def test_home_defaults_to_courier_home_env(tmp_path, monkeypatch, stub_loop):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    rc = S.main(["--controller", "http://127.0.0.1:9"])
    assert rc == 7
    assert stub_loop.seen["home"] == str(tmp_path)


def test_home_defaults_to_cwd(tmp_path, monkeypatch, stub_loop):
    monkeypatch.delenv("COURIER_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    rc = S.main(["--controller", "http://127.0.0.1:9"])
    assert rc == 7
    assert stub_loop.seen["home"] == str(tmp_path)
