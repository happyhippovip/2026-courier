"""Identity changes mark the bound qualification stale and stay stale across reload."""

import json
from pathlib import Path

import pytest

from courier_core.provider_identity import ProviderIdentity
from courier_core.provider_qualification import (
    STATUS_QUALIFIED,
    STATUS_STALE,
    ProbeResult,
    QualificationStore,
    is_qualified,
    qualify,
)
from courier_core.provider_invalidation import (
    REASON_BINARY,
    REASON_PROFILE,
    REASON_VERSION,
    InvalidationError,
    InvalidationLog,
    change_reason,
    invalidated_records,
    invalidate,
    profile_flags,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "courier_core" / "schemas" / "provider_invalidation.schema.json"
AT = "2026-10-08T08:00:00Z"
BINARY_A = "a" * 64
BINARY_B = "b" * 64


class _Probe:
    probe_id = "echo"

    def run(self, identity):
        return ProbeResult(self.probe_id, True, "echo ok")


def _identity(
    version="1.2.3",
    provider_id="tool-a",
    provider_kind="executable",
    version_source="config",
    binary_fingerprint=BINARY_A,
    captured_at=AT,
):
    return ProviderIdentity(
        provider_id=provider_id,
        provider_kind=provider_kind,
        version=version,
        version_source=version_source,
        binary_fingerprint=binary_fingerprint,
        captured_at=captured_at,
    )


def _stores(tmp_path):
    return QualificationStore(tmp_path / "qual.json"), InvalidationLog(tmp_path / "invalidation.json")


def _qualify(store, identity):
    return qualify(identity, [_Probe()], store, at=AT)


def test_unchanged_identity_marks_nothing_stale(tmp_path):
    store, log = _stores(tmp_path)
    current = _identity()
    _qualify(store, current)
    later = _identity(captured_at="2026-10-08T09:30:00Z")
    assert later.fingerprint() == current.fingerprint()
    assert profile_flags(later) == ("executable", "config")
    assert invalidated_records(store.read(), current, later) == ()
    assert change_reason(current, later) is None
    result = invalidate(current, later, store, log, at=AT)
    assert result.reason is None
    assert result.marked_stale == 0
    assert result.records == ()
    assert store.is_qualified(current) is True
    assert is_qualified(current, store) is True
    assert log.read() == ()
    assert not (tmp_path / "invalidation.json").exists()


def test_version_change_marks_old_identity_stale(tmp_path):
    store, log = _stores(tmp_path)
    current = _identity(version="1.2.3")
    _qualify(store, current)
    newer = _identity(version="1.2.4")
    selected = invalidated_records(store.read(), current, newer)
    assert [record.config_hash for record in selected] == [current.fingerprint()]
    assert change_reason(current, newer) == REASON_VERSION
    result = invalidate(current, newer, store, log, at=AT)
    assert result.reason == REASON_VERSION
    assert result.marked_stale == 1
    assert store.is_qualified(current) is False
    assert store.is_qualified(newer) is False
    stored = store.read()[0]
    assert stored.status == STATUS_STALE
    event = log.read()[0]
    assert event.reason == REASON_VERSION
    assert event.old_fingerprint == current.fingerprint()
    assert event.new_fingerprint == newer.fingerprint()
    assert event.provider_name == "tool-a"
    text = (tmp_path / "invalidation.json").read_text(encoding="utf-8")
    assert "/" not in text
    assert "\\" not in text
    qualify(newer, [_Probe()], store, at=AT)
    assert store.is_qualified(newer) is True
    assert store.is_qualified(current) is False
    by_hash = {record.config_hash: record.status for record in store.read()}
    assert by_hash[current.fingerprint()] == STATUS_STALE
    assert by_hash[newer.fingerprint()] == STATUS_QUALIFIED


def test_profile_flag_change_marks_old_identity_stale(tmp_path):
    store, log = _stores(tmp_path)
    current = _identity(provider_kind="executable")
    _qualify(store, current)
    shifted = _identity(provider_kind="service")
    assert shifted.version == current.version
    assert shifted.binary_fingerprint == current.binary_fingerprint
    assert profile_flags(shifted) != profile_flags(current)
    assert change_reason(current, shifted) == REASON_PROFILE
    result = invalidate(current, shifted, store, log, at=AT)
    assert result.marked_stale == 1
    assert result.records[0].config_hash == current.fingerprint()
    assert store.is_qualified(current) is False
    assert log.read()[0].reason == REASON_PROFILE
    assert log.read()[0].old_fingerprint == current.fingerprint()
    assert log.read()[0].new_fingerprint == shifted.fingerprint()


def test_binary_change_marks_old_identity_stale(tmp_path):
    store, log = _stores(tmp_path)
    current = _identity(binary_fingerprint=BINARY_A)
    _qualify(store, current)
    shifted = _identity(binary_fingerprint=BINARY_B)
    assert change_reason(current, shifted) == REASON_BINARY
    result = invalidate(current, shifted, store, log, at=AT)
    assert result.marked_stale == 1
    assert store.is_qualified(current) is False
    assert log.read()[0].reason == REASON_BINARY


def test_second_call_is_idempotent(tmp_path):
    store, log = _stores(tmp_path)
    current = _identity(version="1.0.0")
    newer = _identity(version="1.1.0")
    _qualify(store, current)
    first = invalidate(current, newer, store, log, at=AT)
    snapshot = (tmp_path / "qual.json").read_bytes()
    log_snapshot = (tmp_path / "invalidation.json").read_bytes()
    second = invalidate(current, newer, store, log, at="2026-10-08T08:05:00Z")
    assert first.marked_stale == 1
    assert second.marked_stale == 0
    assert second.reason == REASON_VERSION
    assert len(second.records) == 1
    assert (tmp_path / "qual.json").read_bytes() == snapshot
    assert (tmp_path / "invalidation.json").read_bytes() == log_snapshot
    assert len(log.read()) == 1
    assert store.is_qualified(current) is False


def test_restart_reload_keeps_stale_state(tmp_path):
    qual_path = tmp_path / "qual.json"
    log_path = tmp_path / "invalidation.json"
    current = _identity(version="2.0.0")
    newer = _identity(version="2.1.0")
    invalidate(current, newer, *_qualify_then(qual_path, log_path, current), at=AT)
    reloaded_store = QualificationStore(qual_path)
    reloaded_log = InvalidationLog(log_path)
    assert reloaded_store.is_qualified(current) is False
    assert reloaded_store.is_qualified(newer) is False
    events = reloaded_log.read()
    assert len(events) == 1
    assert events[0].reason == REASON_VERSION
    assert events[0].old_fingerprint == current.fingerprint()
    assert events[0].new_fingerprint == newer.fingerprint()
    assert reloaded_store.read()[0].status == STATUS_STALE


def _qualify_then(qual_path, log_path, identity):
    store = QualificationStore(qual_path)
    log = InvalidationLog(log_path)
    _qualify(store, identity)
    return store, log


def test_unknown_provider_fails_closed(tmp_path):
    store, log = _stores(tmp_path)
    known = _identity(provider_id="known-tool")
    _qualify(store, known)
    missing = _identity(provider_id="missing-tool", version="1.0.0")
    missing_next = _identity(provider_id="missing-tool", version="1.0.1")
    with pytest.raises(InvalidationError, match="unknown provider"):
        invalidate(missing, missing_next, store, log, at=AT)
    assert store.is_qualified(known) is True
    assert log.read() == ()
    assert not (tmp_path / "invalidation.json").exists()
    other = _identity(provider_id="other-tool", version="9.0.0")
    with pytest.raises(InvalidationError, match="provider name does not match"):
        invalidate(known, other, store, log, at=AT)
    assert store.is_qualified(known) is True
    assert store.read()[0].status == STATUS_QUALIFIED


def test_schema_rejects_unknown_fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["events"]
    event = schema["properties"]["events"]["items"]
    assert event["additionalProperties"] is False
    assert event["properties"]["reason"]["enum"] == ["version", "binary", "profile", "identity"]
