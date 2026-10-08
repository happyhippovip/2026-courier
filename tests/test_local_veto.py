"""Offline tests for local host veto. No live governor probe and no network."""

import json
from datetime import datetime, timezone

import pytest

from courier_worker.local_veto import (
    ACCEPT,
    CONFIG_UNREADABLE,
    PROTECTED_PATH,
    PROVIDER_UNAVAILABLE,
    QUIET_HOURS,
    RESOURCE_PAUSE,
    USER_PAUSE,
    VETO,
    consider,
    evaluate,
    hash_path,
)

UTC = timezone.utc
SECRET = "super-secret-token-value"
PRIVATE = "/home/owner/private/notes.txt"


class FakeGovernor:
    def __init__(self, health="GREEN"):
        self._health = health
        self.admit_calls = 0
        self.measure_calls = 0

    def health(self):
        return self._health

    def admit_job(self, budget_class):
        self.admit_calls += 1
        raise AssertionError("veto must not admit work")

    def measure_pressure(self):
        self.measure_calls += 1
        raise AssertionError("veto must not probe the host")


class StateOnlyGovernor:
    def __init__(self, state):
        self.state = state


class FakeQueue:
    def __init__(self, items):
        self.items = [dict(item) for item in items]
        self.released = []
        self.failed = []
        self.held = None

    def claim(self, worker_id):
        if not self.items:
            return None
        item = self.items.pop(0)
        item["worker_id"] = worker_id
        self.held = item
        return item

    def release(self, item):
        self.released.append(item)
        self.items.append(item)
        self.held = None

    def fail(self, item):
        self.failed.append(item)


def _config(tmp_path, **overrides):
    body = {
        "pause_file": str(tmp_path / "PAUSE"),
        "protected_paths_file": str(tmp_path / "protected.txt"),
        "quiet_hours": {"start": "22:00", "end": "07:00", "tz": "UTC"},
        "providers": {"codex": {"installed": True, "logged_in": True}},
    }
    body.update(overrides)
    path = tmp_path / "local_veto.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    (tmp_path / "protected.txt").write_text("# local\n/home/owner/private\n", encoding="utf-8")
    return str(path)


def _item(**overrides):
    item = {
        "dispatch_id": "d1",
        "task_id": "t1",
        "provider": "codex",
        "files_scope": ["/work/src/main.py"],
        "api_token": SECRET,
    }
    item.update(overrides)
    return item


def _eval(tmp_path, item=None, governor="GREEN", now=None, **config):
    path = _config(tmp_path, **config)
    gov = governor if not isinstance(governor, str) else FakeGovernor(governor)
    moment = now or datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    return evaluate(item if item is not None else _item(), config_path=path, governor=gov, now=moment)


def test_accept_when_no_rule_matches(tmp_path):
    verdict = _eval(tmp_path)
    assert str(verdict) == ACCEPT
    assert verdict.decision == ACCEPT
    assert verdict.reason_code == ""


def test_user_pause_file(tmp_path):
    pause = tmp_path / "PAUSE"
    pause.write_text("paused\n", encoding="utf-8")
    verdict = _eval(tmp_path)
    assert verdict.decision == VETO
    assert verdict.reason_code == USER_PAUSE
    assert str(verdict) == "VETO(user_pause, user pause file is present)"
    assert verdict.path_hashes == (hash_path(str(pause)),)
    assert str(pause) not in str(verdict)


def test_resource_pause_from_health_api(tmp_path):
    governor = FakeGovernor("RESOURCE_PAUSE")
    verdict = _eval(tmp_path, governor=governor)
    assert verdict.reason_code == RESOURCE_PAUSE
    assert verdict.detail == "host is in RESOURCE_PAUSE"
    assert governor.admit_calls == 0 and governor.measure_calls == 0


def test_resource_pause_from_state_attribute(tmp_path):
    verdict = _eval(tmp_path, governor=StateOnlyGovernor("RESOURCE_PAUSE"))
    assert verdict.reason_code == RESOURCE_PAUSE


def test_green_state_does_not_pause(tmp_path):
    verdict = _eval(tmp_path, governor=StateOnlyGovernor("GREEN"))
    assert verdict.decision == ACCEPT


def test_provider_not_installed(tmp_path):
    verdict = _eval(tmp_path, providers={"codex": {"installed": False, "logged_in": True}})
    assert verdict.reason_code == PROVIDER_UNAVAILABLE
    assert verdict.detail == "provider codex is not installed"


def test_provider_not_logged_in(tmp_path):
    verdict = _eval(tmp_path, providers={"codex": {"installed": True, "logged_in": False}})
    assert verdict.reason_code == PROVIDER_UNAVAILABLE
    assert verdict.detail == "provider codex is not logged in"


def test_provider_missing_from_config(tmp_path):
    verdict = _eval(tmp_path, providers={})
    assert verdict.reason_code == PROVIDER_UNAVAILABLE
    assert "not installed" in verdict.detail


def test_protected_path_child_and_parent(tmp_path):
    child = _eval(tmp_path, item=_item(files_scope=[PRIVATE]))
    assert child.reason_code == PROTECTED_PATH
    assert hash_path(PRIVATE) in child.path_hashes
    assert hash_path("/home/owner/private") in child.path_hashes
    assert PRIVATE not in child.detail
    parent = _eval(tmp_path, item=_item(files_scope=["/home/owner"]))
    assert parent.reason_code == PROTECTED_PATH


def test_protected_path_prefix_is_not_a_sibling(tmp_path):
    verdict = _eval(tmp_path, item=_item(files_scope=["/home/owner/privateer/notes.txt"]))
    assert verdict.decision == ACCEPT


def test_quiet_hours_window(tmp_path):
    inside_night = _eval(tmp_path, now=datetime(2026, 10, 8, 22, 0, tzinfo=UTC))
    inside_morning = _eval(tmp_path, now=datetime(2026, 10, 8, 6, 59, tzinfo=UTC))
    before = _eval(tmp_path, now=datetime(2026, 10, 8, 21, 59, tzinfo=UTC))
    at_end = _eval(tmp_path, now=datetime(2026, 10, 8, 7, 0, tzinfo=UTC))
    assert inside_night.reason_code == QUIET_HOURS
    assert inside_morning.reason_code == QUIET_HOURS
    assert "22:00-07:00" in inside_night.detail
    assert before.decision == ACCEPT
    assert at_end.decision == ACCEPT


def test_combined_rules_use_stable_priority(tmp_path):
    (tmp_path / "PAUSE").write_text("1", encoding="utf-8")
    item = _item(files_scope=[PRIVATE], provider="codex")
    verdict = _eval(
        tmp_path,
        item=item,
        governor="RESOURCE_PAUSE",
        now=datetime(2026, 10, 8, 23, 0, tzinfo=UTC),
        providers={"codex": {"installed": False, "logged_in": False}},
    )
    assert verdict.reason_code == USER_PAUSE

    later = _eval(
        tmp_path,
        item=item,
        governor="RESOURCE_PAUSE",
        now=datetime(2026, 10, 8, 23, 0, tzinfo=UTC),
        providers={"codex": {"installed": False, "logged_in": False}},
        pause_file=str(tmp_path / "not-paused"),
    )
    assert later.reason_code == RESOURCE_PAUSE


def test_unreadable_config_fails_closed(tmp_path):
    missing = evaluate(_item(), config_path=str(tmp_path / "missing.json"), governor=FakeGovernor(),
                       now=datetime(2026, 10, 8, 12, 0, tzinfo=UTC))
    assert missing.reason_code == CONFIG_UNREADABLE
    assert missing.detail == "host config is unreadable"
    assert str(tmp_path) not in missing.detail

    directory = tmp_path / "not-a-file"
    directory.mkdir()
    as_dir = evaluate(_item(), config_path=str(directory), governor=FakeGovernor(),
                      now=datetime(2026, 10, 8, 12, 0, tzinfo=UTC))
    assert as_dir.reason_code == CONFIG_UNREADABLE

    garbage = tmp_path / "garbage.json"
    garbage.write_text("{not json", encoding="utf-8")
    bad = evaluate(_item(), config_path=str(garbage), governor=FakeGovernor(),
                   now=datetime(2026, 10, 8, 12, 0, tzinfo=UTC))
    assert bad.reason_code == CONFIG_UNREADABLE


def test_unreadable_protected_paths_fail_closed(tmp_path):
    path = _config(tmp_path, protected_paths_file=str(tmp_path / "absent-protected.txt"))
    verdict = evaluate(_item(), config_path=path, governor=FakeGovernor(),
                       now=datetime(2026, 10, 8, 12, 0, tzinfo=UTC))
    assert verdict.reason_code == CONFIG_UNREADABLE


def test_malformed_quiet_hours_fail_closed(tmp_path):
    verdict = _eval(tmp_path, quiet_hours={"start": "25:99", "end": "07:00", "tz": "UTC"})
    assert verdict.reason_code == CONFIG_UNREADABLE


def test_governor_exception_fails_closed(tmp_path):
    class Broken:
        def health(self):
            raise OSError("metrics unreadable")

    verdict = _eval(tmp_path, governor=Broken())
    assert verdict.reason_code == CONFIG_UNREADABLE


def test_veto_releases_item_and_records_receipt_without_secrets(tmp_path):
    (tmp_path / "PAUSE").write_text("1", encoding="utf-8")
    queue = FakeQueue([_item()])
    moment = datetime(2026, 10, 8, 12, 30, tzinfo=UTC)
    verdict, kept = consider(
        queue, "host-a",
        config_path=_config(tmp_path),
        receipt_dir=str(tmp_path / "receipts"),
        governor=FakeGovernor(),
        now=moment,
    )
    assert kept is None
    assert verdict.reason_code == USER_PAUSE
    assert queue.failed == []
    assert len(queue.released) == 1
    assert queue.held is None
    assert queue.items[0]["dispatch_id"] == "d1"
    receipt_path = tmp_path / "receipts" / "local-veto-d1.json"
    text = receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(text)
    assert receipt["schema"] == "courier.local_veto.v1"
    assert receipt["decision"] == VETO
    assert receipt["reason_code"] == USER_PAUSE
    assert receipt["dispatch_id"] == "d1"
    assert receipt["task_id"] == "t1"
    assert receipt["worker_id"] == "host-a"
    assert receipt["recorded_at"] == "2026-10-08T12:30:00Z"
    assert receipt["path_hashes"] == [hash_path(str(tmp_path / "PAUSE"))]
    assert SECRET not in text
    assert PRIVATE not in text
    assert "api_token" not in text
    assert str(tmp_path / "PAUSE") not in text


def test_accept_does_not_release(tmp_path):
    queue = FakeQueue([_item()])
    verdict, kept = consider(
        queue, "host-a",
        config_path=_config(tmp_path),
        receipt_dir=str(tmp_path / "receipts"),
        governor=FakeGovernor(),
        now=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
    )
    assert verdict.decision == ACCEPT
    assert kept["dispatch_id"] == "d1"
    assert queue.released == []
    assert queue.held["dispatch_id"] == "d1"
    assert list((tmp_path / "receipts").glob("*.json")) == []


def test_empty_queue_accepts_without_release(tmp_path):
    queue = FakeQueue([])
    verdict, kept = consider(
        queue, "host-a",
        config_path=_config(tmp_path),
        receipt_dir=str(tmp_path / "receipts"),
        governor=FakeGovernor(),
    )
    assert str(verdict) == ACCEPT
    assert kept is None
    assert queue.released == []


def test_unreadable_config_releases_instead_of_failing(tmp_path):
    queue = FakeQueue([_item()])
    verdict, kept = consider(
        queue, "host-a",
        config_path=str(tmp_path / "no-config.json"),
        receipt_dir=str(tmp_path / "receipts"),
        governor=FakeGovernor(),
        now=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
    )
    assert kept is None
    assert verdict.reason_code == CONFIG_UNREADABLE
    assert queue.failed == []
    assert [item["dispatch_id"] for item in queue.released] == ["d1"]
    receipt = json.loads((tmp_path / "receipts" / "local-veto-d1.json").read_text(encoding="utf-8"))
    assert receipt["reason_code"] == CONFIG_UNREADABLE
    assert SECRET not in json.dumps(receipt)


def test_same_inputs_repeat(tmp_path):
    item = _item(files_scope=[PRIVATE])
    moment = datetime(2026, 10, 8, 23, 15, tzinfo=UTC)
    first = _eval(tmp_path, item=item, now=moment)
    second = _eval(tmp_path, item=item, now=moment)
    assert first == second
    assert first.reason_code == PROTECTED_PATH
