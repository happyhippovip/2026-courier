"""Gate G4: outbox restart and cleanup do not replay a confirmed effect.

Crash is the on-disk state a new process sees. The executor stands in for
the effect. Cleanup may unlink only a confirmed outbox file in a temp home.
"""

import json

import pytest

from courier_worker.outbox_restart import (
    OutboxRestartError,
    cleanup_confirmed,
    record_confirmation,
    resume_outbox,
)

KEY = "effect-alpha"


def _entry(home, dispatch_id, effect_key=KEY, raw=None):
    outbox = home / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / f"{dispatch_id}.json"
    if raw is None:
        raw = json.dumps({"dispatch_id": dispatch_id, "effect_key": effect_key}, sort_keys=True)
    path.write_text(raw, encoding="utf-8")
    return path


def _artifact(home):
    path = home / "artifacts" / "real.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("keep-me", encoding="utf-8")
    return path


def test_crash_before_effect_continues_the_open_entry_once(tmp_path):
    _entry(tmp_path, "d1")
    artifact = _artifact(tmp_path)
    calls = []
    report = resume_outbox(tmp_path, lambda entry: calls.append(entry["effect_key"]))
    assert report["continued"] == ["d1"]
    assert report["skipped"] == []
    assert calls == [KEY]
    assert artifact.read_text(encoding="utf-8") == "keep-me"
    assert (tmp_path / "outbox" / "d1.json").is_file()


def test_crash_after_effect_does_not_run_again(tmp_path):
    _entry(tmp_path, "d1")
    record_confirmation(tmp_path, KEY, "d1")
    calls = []
    report = resume_outbox(tmp_path, lambda entry: calls.append(entry["dispatch_id"]))
    assert calls == []
    assert report["continued"] == []
    assert report["skipped"] == ["d1"]
    assert (tmp_path / "outbox" / "d1.json").is_file()


def test_double_restart_continues_an_open_entry_once(tmp_path):
    _entry(tmp_path, "d1")
    calls = []
    first = resume_outbox(tmp_path, lambda entry: calls.append(entry["dispatch_id"]))
    second = resume_outbox(tmp_path, lambda entry: calls.append(entry["dispatch_id"]))
    third = resume_outbox(tmp_path, lambda entry: calls.append(entry["dispatch_id"]))
    assert calls == ["d1"]
    assert first["continued"] == ["d1"]
    assert second["skipped"] == ["d1"]
    assert third["skipped"] == ["d1"]


def test_same_effect_key_is_not_executed_twice_in_one_pass(tmp_path):
    _entry(tmp_path, "d1", KEY)
    _entry(tmp_path, "d2", KEY)
    calls = []
    report = resume_outbox(tmp_path, lambda entry: calls.append(entry["dispatch_id"]))
    assert calls == ["d1"]
    assert report["continued"] == ["d1"]
    assert report["skipped"] == ["d2"]


def test_a_new_dispatch_of_a_confirmed_key_is_not_executed(tmp_path):
    record_confirmation(tmp_path, KEY, "d1")
    _entry(tmp_path, "d2", KEY)
    calls = []
    report = resume_outbox(tmp_path, lambda entry: calls.append(entry["dispatch_id"]))
    assert calls == []
    assert report["skipped"] == ["d2"]


def test_corrupt_outbox_entry_fails_and_does_not_replay(tmp_path):
    path = _entry(tmp_path, "d1", raw="{")
    artifact = _artifact(tmp_path)
    calls = []

    def execute(entry):
        calls.append(entry)
        raise AssertionError("corrupt outbox must not replay")

    with pytest.raises(OutboxRestartError, match="corrupt"):
        resume_outbox(tmp_path, execute)
    with pytest.raises(OutboxRestartError, match="corrupt"):
        cleanup_confirmed(tmp_path)
    assert calls == []
    assert path.read_text(encoding="utf-8") == "{"
    assert artifact.read_text(encoding="utf-8") == "keep-me"


def test_cleanup_removes_only_a_confirmed_entry_after_journal_proof(tmp_path):
    confirmed = _entry(tmp_path, "d1", KEY)
    open_entry = _entry(tmp_path, "d2", "effect-beta")
    artifact = _artifact(tmp_path)
    sibling = tmp_path / "customer-data.txt"
    sibling.write_text("do-not-delete", encoding="utf-8")
    record_confirmation(tmp_path, KEY, "d1")
    removed = cleanup_confirmed(tmp_path)
    assert removed == ["d1"]
    assert not confirmed.exists()
    assert open_entry.is_file()
    assert artifact.read_text(encoding="utf-8") == "keep-me"
    assert sibling.read_text(encoding="utf-8") == "do-not-delete"
    journal = tmp_path / "run" / "effect-journal.jsonl"
    assert journal.is_file()
    assert KEY in journal.read_text(encoding="utf-8")


def test_cleanup_without_journal_proof_removes_nothing(tmp_path):
    path = _entry(tmp_path, "d1")
    assert cleanup_confirmed(tmp_path) == []
    assert path.is_file()


def test_failed_effect_is_not_confirmed_and_stays_open(tmp_path):
    _entry(tmp_path, "d1")

    def boom(entry):
        raise RuntimeError("crashed during effect")

    with pytest.raises(RuntimeError, match="crashed during effect"):
        resume_outbox(tmp_path, boom)
    journal = tmp_path / "run" / "effect-journal.jsonl"
    assert not journal.exists()
    calls = []
    report = resume_outbox(tmp_path, lambda entry: calls.append(entry["dispatch_id"]))
    assert calls == ["d1"]
    assert report["continued"] == ["d1"]


def test_missing_or_empty_effect_key_fails_closed(tmp_path):
    _entry(tmp_path, "d-no-key", raw=json.dumps({"dispatch_id": "d-no-key"}))
    calls = []
    with pytest.raises(OutboxRestartError, match="missing or empty effect_key"):
        resume_outbox(tmp_path, lambda entry: calls.append(entry))
    with pytest.raises(OutboxRestartError, match="missing or empty effect_key"):
        cleanup_confirmed(tmp_path)
    with pytest.raises(OutboxRestartError, match="effect_key must be a non-empty string"):
        record_confirmation(tmp_path, "", "d-no-key")
    assert calls == []

def test_corrupt_journal_line_fails_closed_and_does_not_replay(tmp_path):
    _entry(tmp_path, "d1")
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    journal = run_dir / "effect-journal.jsonl"
    journal.write_text('{"effect_key": "effect-alpha",\n', encoding="utf-8")

    calls = []
    with pytest.raises(OutboxRestartError, match="corrupt journal line"):
        resume_outbox(tmp_path, lambda entry: calls.append(entry))

    with pytest.raises(OutboxRestartError, match="corrupt journal line"):
        cleanup_confirmed(tmp_path)

    assert calls == []
    assert (tmp_path / "outbox" / "d1.json").is_file()


def test_non_dict_journal_line_fails_closed(tmp_path):
    _entry(tmp_path, "d1")
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    journal = run_dir / "effect-journal.jsonl"
    journal.write_text('"not a dict"\n', encoding="utf-8")

    calls = []
    with pytest.raises(OutboxRestartError, match="not a dict"):
        resume_outbox(tmp_path, lambda entry: calls.append(entry))

    with pytest.raises(OutboxRestartError, match="not a dict"):
        cleanup_confirmed(tmp_path)

    assert calls == []

