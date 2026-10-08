"""Offline golden path: provider failover, then a verified return.

The work item starts with qualified provider A. A's version changes, the
qualification for that identity is marked stale, and the selector chooses
qualified provider B by total cost. B is executed once and the receipt chain
links that execution. A later returns through the registry: stale, then an
accepted probe, then a second accepted probe. The next work item may select
A again. Negative branches park with no execution.
"""

import hashlib
import json
from pathlib import Path

import pytest

from courier_core.provider_identity import ProviderIdentity
from courier_core.provider_invalidation import InvalidationLog, invalidate
from courier_core.provider_qualification import (
    STATUS_STALE,
    ProbeResult,
    QualificationStore,
    qualify,
)
from courier_core.provider_registry import (
    STATUS_ACTIVE,
    STATUS_STANDBY,
    ProbeTask,
    ProviderRegistry,
)
from courier_core.provider_selector import (
    STATUS_NO_ELIGIBLE,
    STATUS_NO_QUALIFIED,
    STATUS_SELECTED,
    WEIGHT_HEAVY,
    WEIGHT_LIGHT,
    ProviderCandidate,
    select,
)

AT = "2026-10-08T09:00:00Z"
BINARY = "ab" * 32
GENESIS = "0" * 64


class _Echo:
    probe_id = "echo"

    def run(self, identity):
        return ProbeResult("echo", True, "echo ok")


class _Pressure:
    def __init__(self, level):
        self.level = level
        self.admit_calls = 0

    def pressure(self):
        return self.level

    def admit_job(self, budget_class):
        self.admit_calls += 1
        return True


class DuplicateExecution(Exception):
    pass


class ReceiptChain:
    """Append-only execution receipts. One completion per work item."""

    def __init__(self, path: Path):
        self.path = path
        self.head = GENESIS

    def complete(self, work_id, identity):
        if any(row["receipt"]["work_id"] == work_id for row in self.rows()):
            raise DuplicateExecution(work_id)
        receipt = {
            "config_hash": identity.fingerprint(),
            "outcome": "complete",
            "prev_hash": self.head,
            "provider_id": identity.provider_id,
            "work_id": work_id,
        }
        encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        line = json.dumps({"hash": digest, "receipt": receipt}, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        self.head = digest
        return digest

    def rows(self):
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line:
                rows.append(json.loads(line))
        return rows

    def verify(self):
        prev = GENESIS
        for row in self.rows():
            receipt = row["receipt"]
            assert receipt["prev_hash"] == prev
            encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            assert hashlib.sha256(encoded.encode("utf-8")).hexdigest() == row["hash"]
            assert "/" not in encoded
            assert "\\" not in encoded
            prev = row["hash"]
        assert prev == self.head
        return prev


def _identity(provider_id, version):
    return ProviderIdentity(
        provider_id=provider_id,
        provider_kind="executable",
        version=version,
        version_source="config",
        binary_fingerprint=BINARY,
        captured_at=AT,
    )


def _qualify(store, identity):
    qualify(identity, [_Echo()], store, at=AT)


def _candidate(identity, total_cost, weight=WEIGHT_LIGHT, metered=False):
    return ProviderCandidate(identity, total_cost, weight, metered)


def _execute(chain, work_id, identity, decision):
    assert decision.status == STATUS_SELECTED
    assert decision.selected_provider_id == identity.provider_id
    assert decision.selected_config_hash == identity.fingerprint()
    chain.complete(work_id, identity)


def test_golden_provider_failover_end_to_end(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    invalidation = InvalidationLog(tmp_path / "invalidation.json")
    registry = ProviderRegistry(tmp_path / "registry.json")
    chain = ReceiptChain(tmp_path / "receipts.jsonl")
    provider_a = _identity("prov-a", "1.0.0")
    provider_b = _identity("prov-b", "1.0.0")
    _qualify(store, provider_a)
    _qualify(store, provider_b)

    stored = select(
        [_candidate(provider_a, 10), _candidate(provider_b, 40)],
        store,
        _Pressure("GREEN"),
    )
    assert stored.selected_provider_id == "prov-a"
    assert stored.total_cost == 10

    changed = _identity("prov-a", "1.1.0")
    assert changed.fingerprint() != provider_a.fingerprint()
    marked = invalidate(provider_a, changed, store, invalidation, at=AT)
    assert marked.reason == "version"
    assert marked.old_fingerprint == provider_a.fingerprint()
    assert marked.new_fingerprint == changed.fingerprint()
    stale = next(record for record in store.read() if record.config_hash == provider_a.fingerprint())
    assert stale.status == STATUS_STALE
    assert store.is_qualified(provider_a) is False

    failover = select(
        [_candidate(provider_a, 10), _candidate(provider_b, 40)],
        store,
        _Pressure("GREEN"),
    )
    assert failover.selected_provider_id == "prov-b"
    assert failover.total_cost == 40
    reasons = {item.provider_id: item.reason for item in failover.rejections}
    assert reasons["prov-a"] == "stale"
    assert failover.to_json() == select(
        [_candidate(provider_a, 10), _candidate(provider_b, 40)],
        store,
        _Pressure("GREEN"),
    ).to_json()
    _execute(chain, "work-1", provider_b, failover)
    snapshot = chain.path.read_bytes()
    with pytest.raises(DuplicateExecution):
        chain.complete("work-1", provider_b)
    assert chain.path.read_bytes() == snapshot
    assert [row["receipt"]["provider_id"] for row in chain.rows()] == ["prov-b"]

    registry.register("prov-a", at=AT)
    registry.register("prov-b", at=AT)
    registry.note_departure("prov-a", at=AT)
    returned = registry.note_return("prov-a", at="2026-10-08T09:10:00Z")
    assert returned.status == "STALE"
    _qualify(store, changed)
    while_stale = select(
        [_candidate(changed, 10), _candidate(provider_b, 40)],
        store,
        _Pressure("GREEN"),
        registry=registry,
    )
    assert while_stale.selected_provider_id == "prov-b"
    assert {item.provider_id: item.reason for item in while_stale.rejections}["prov-a"] == "registry_stale"

    standby = registry.apply_probe("prov-a", ProbeTask("probe-1", True, True, True), at="2026-10-08T09:20:00Z")
    assert standby.status == STATUS_STANDBY
    active = registry.apply_probe("prov-a", ProbeTask("probe-2", True, True, True), at="2026-10-08T09:30:00Z")
    assert active.status == STATUS_ACTIVE
    assert registry.in_rotation("prov-a") is True

    nxt = select(
        [_candidate(changed, 10), _candidate(provider_b, 40)],
        store,
        _Pressure("GREEN"),
        registry=registry,
    )
    assert nxt.selected_provider_id == "prov-a"
    assert nxt.total_cost == 10
    _execute(chain, "work-2", changed, nxt)
    assert [row["receipt"]["work_id"] for row in chain.rows()] == ["work-1", "work-2"]
    assert [row["receipt"]["provider_id"] for row in chain.rows()] == ["prov-b", "prov-a"]
    chain.verify()
    reloaded = ReceiptChain(chain.path)
    reloaded.head = chain.head
    reloaded.verify()
    tampered = chain.path.read_text(encoding="utf-8").replace(provider_b.fingerprint(), "f" * 64, 1)
    broken = tmp_path / "tampered.jsonl"
    broken.write_text(tampered, encoding="utf-8")
    with pytest.raises(AssertionError):
        ReceiptChain(broken).verify()


def test_golden_all_stale_candidates_execute_nothing(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    invalidation = InvalidationLog(tmp_path / "invalidation.json")
    provider_a = _identity("prov-a", "1.0.0")
    provider_b = _identity("prov-b", "1.0.0")
    _qualify(store, provider_a)
    _qualify(store, provider_b)
    invalidate(provider_a, _identity("prov-a", "2.0.0"), store, invalidation, at=AT)
    invalidate(provider_b, _identity("prov-b", "2.0.0"), store, invalidation, at=AT)
    chain = ReceiptChain(tmp_path / "receipts.jsonl")
    decision = select(
        [_candidate(provider_a, 1), _candidate(provider_b, 2)],
        store,
        _Pressure("GREEN"),
    )
    assert decision.status == STATUS_NO_QUALIFIED
    assert decision.selected_provider_id is None
    assert {item.reason for item in decision.rejections} == {"stale"}
    assert chain.rows() == []
    assert not chain.path.exists()


def test_golden_unknown_pressure_excludes_heavy(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    heavy = _identity("prov-heavy", "1.0.0")
    light = _identity("prov-light", "1.0.0")
    _qualify(store, heavy)
    _qualify(store, light)
    governor = _Pressure("UNKNOWN")
    decision = select(
        [_candidate(heavy, 1, weight=WEIGHT_HEAVY), _candidate(light, 20)],
        store,
        governor,
    )
    assert decision.status == STATUS_SELECTED
    assert decision.selected_provider_id == "prov-light"
    assert {item.provider_id: item.reason for item in decision.rejections}["prov-heavy"] == "heavy_excluded"
    assert governor.admit_calls == 0
    chain = ReceiptChain(tmp_path / "receipts.jsonl")
    _execute(chain, "work-light", light, decision)
    assert [row["receipt"]["provider_id"] for row in chain.rows()] == ["prov-light"]

    parked = select([_candidate(heavy, 1, weight=WEIGHT_HEAVY)], store, _Pressure("UNKNOWN"))
    assert parked.status == STATUS_NO_ELIGIBLE
    assert parked.selected_provider_id is None
    assert parked.rejections[0].reason == "heavy_excluded"


def test_golden_metered_without_escalation_is_refused(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    plain = _identity("prov-plain", "1.0.0")
    metered = _identity("prov-meter", "1.0.0")
    _qualify(store, plain)
    _qualify(store, metered)
    decision = select(
        [_candidate(plain, 30), _candidate(metered, 1, metered=True)],
        store,
        _Pressure("GREEN"),
    )
    assert decision.selected_provider_id == "prov-plain"
    assert decision.escalation_reason is None
    assert {item.provider_id: item.reason for item in decision.rejections}["prov-meter"] == (
        "metered_requires_escalation"
    )
    chain = ReceiptChain(tmp_path / "receipts.jsonl")
    _execute(chain, "work-plain", plain, decision)
    assert [row["receipt"]["provider_id"] for row in chain.rows()] == ["prov-plain"]

    refused = select([_candidate(metered, 1, metered=True)], store, _Pressure("GREEN"))
    assert refused.status == STATUS_NO_ELIGIBLE
    assert refused.selected_provider_id is None
    assert refused.rejections[0].reason == "metered_requires_escalation"
    assert chain.rows()[0]["receipt"]["work_id"] == "work-plain"
