"""Qualification probes and the fail-closed qualification store."""

import json
import threading
from pathlib import Path

import pytest

from courier_core.provider_identity import ProviderIdentity
from courier_core.provider_qualification import (
    MAX_STORE_BYTES,
    STATUS_QUALIFIED,
    STATUS_STALE,
    STATUS_UNQUALIFIED,
    ProbeResult,
    QualificationError,
    QualificationStore,
    is_qualified,
    qualify,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "courier_core" / "schemas" / "provider_qualification.schema.json"
AT = "2026-10-08T07:00:00Z"


class _Probe:
    def __init__(self, probe_id, passed, evidence):
        self.probe_id = probe_id
        self._passed = passed
        self._evidence = evidence

    def run(self, identity):
        return ProbeResult(self.probe_id, self._passed, self._evidence)


class _Boom:
    probe_id = "boom"

    def run(self, identity):
        raise RuntimeError("probe broke")


def _identity(version="1.2.3", provider_id="tool-a"):
    return ProviderIdentity(
        provider_id=provider_id,
        provider_kind="executable",
        version=version,
        version_source="config",
        binary_fingerprint=None,
        captured_at=AT,
    )


def test_qualify_records_pass_and_is_qualified(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    identity = _identity()
    record = qualify(identity, [_Probe("echo", True, "echo ok")], store, at=AT)
    assert record.status == STATUS_QUALIFIED
    assert record.name == "tool-a"
    assert record.version == "1.2.3"
    assert record.config_hash == identity.fingerprint()
    assert record.probe_results == (ProbeResult("echo", True, "echo ok"),)
    assert store.is_qualified(identity) is True
    assert is_qualified(identity, store) is True
    assert store.read()[0].status == STATUS_QUALIFIED


def test_failed_probe_is_unqualified(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    identity = _identity()
    record = qualify(
        identity,
        [_Probe("echo", True, "echo ok"), _Probe("shape", False, "shape mismatch")],
        store,
        at=AT,
    )
    assert record.status == STATUS_UNQUALIFIED
    assert [item.passed for item in record.probe_results] == [True, False]
    assert store.is_qualified(identity) is False

    broken = qualify(identity, [_Boom()], store, at=AT)
    assert broken.status == STATUS_UNQUALIFIED
    assert broken.probe_results[0].evidence == "probe failed to finish"
    assert store.is_qualified(identity) is False

    empty = qualify(_identity(provider_id="tool-b"), [], store, at=AT)
    assert empty.status == STATUS_UNQUALIFIED
    assert empty.probe_results == ()
    assert store.is_qualified(_identity(provider_id="tool-b")) is False


def test_version_change_is_not_qualified(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    current = _identity(version="1.2.3")
    qualify(current, [_Probe("echo", True, "echo ok")], store, at=AT)
    newer = _identity(version="1.2.4")
    assert newer.fingerprint() != current.fingerprint()
    assert store.is_qualified(current) is True
    assert store.is_qualified(newer) is False
    assert is_qualified(newer, store) is False


def test_malformed_store_fails_closed(tmp_path):
    identity = _identity()
    path = tmp_path / "qual.json"
    store = QualificationStore(path)

    path.write_text("{", encoding="utf-8")
    assert store.is_qualified(identity) is False
    with pytest.raises(QualificationError):
        store.read()
    assert path.read_text(encoding="utf-8") == "{"

    path.write_text(json.dumps({"records": [], "note": "x"}) + "\n", encoding="utf-8")
    assert store.is_qualified(identity) is False

    path.write_bytes(b" " * (MAX_STORE_BYTES + 1))
    assert store.is_qualified(identity) is False
    with pytest.raises(QualificationError):
        store.mark_stale(lambda record: True)
    assert path.stat().st_size == MAX_STORE_BYTES + 1

    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "name": "tool-a",
                        "version": "9.9.9",
                        "config_hash": identity.fingerprint(),
                        "probe_results": [
                            {"probe_id": "echo", "passed": True, "evidence": "echo ok"}
                        ],
                        "recorded_at": AT,
                        "status": "QUALIFIED",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert store.is_qualified(identity) is False


def test_concurrent_writes_do_not_corrupt(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    identities = [_identity(version=f"1.{i}.0", provider_id=f"tool-{i}") for i in range(12)]
    barrier = threading.Barrier(len(identities))
    errors = []

    def work(identity):
        try:
            barrier.wait(timeout=10)
            qualify(identity, [_Probe("echo", True, "echo ok")], store, at=AT)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(identity,)) for identity in identities]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    assert all(not thread.is_alive() for thread in threads)
    parsed = json.loads((tmp_path / "qual.json").read_text(encoding="utf-8"))
    assert len(parsed["records"]) == 12
    hashes = [row["config_hash"] for row in parsed["records"]]
    assert hashes == sorted(hashes)
    assert len(set(hashes)) == 12
    for identity in identities:
        assert store.is_qualified(identity) is True


def test_mark_stale_drops_one_provider(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    older = _identity(version="1.0.0", provider_id="old")
    newer = _identity(version="2.0.0", provider_id="new")
    qualify(older, [_Probe("echo", True, "echo ok")], store, at=AT)
    qualify(newer, [_Probe("echo", True, "echo ok")], store, at=AT)
    changed = store.mark_stale(lambda record: record.name == "old")
    assert changed == 1
    assert store.is_qualified(older) is False
    assert store.is_qualified(newer) is True
    stored = {record.name: record.status for record in store.read()}
    assert stored == {"old": STATUS_STALE, "new": STATUS_QUALIFIED}
    assert store.mark_stale(lambda record: record.name == "old") == 0


def test_schema_rejects_unknown_fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["records"]
    record = schema["properties"]["records"]["items"]
    assert record["additionalProperties"] is False
    assert record["properties"]["status"]["enum"] == ["QUALIFIED", "UNQUALIFIED", "STALE"]
    probe = record["properties"]["probe_results"]["items"]
    assert probe["additionalProperties"] is False
