"""A returning provider stays out of rotation until a probe is accepted."""

import pytest

from courier_core.provider_identity import ProviderIdentity
from courier_core.provider_qualification import ProbeResult, QualificationStore, qualify
from courier_core.provider_registry import (
    STATUS_ACTIVE,
    STATUS_QUARANTINED,
    STATUS_STALE,
    STATUS_STANDBY,
    ProbeTask,
    ProviderRegistry,
    RegistryError,
)
from courier_core.provider_selector import (
    STATUS_NO_ELIGIBLE,
    STATUS_SELECTED,
    WEIGHT_LIGHT,
    ProviderCandidate,
    select,
)

AT = "2026-10-08T08:40:00Z"
BINARY = "cd" * 32


class _Probe:
    probe_id = "echo"

    def run(self, identity):
        return ProbeResult("echo", True, "echo ok")


class _Gov:
    def pressure(self):
        return "GREEN"


def _identity(provider_id="tool-a"):
    return ProviderIdentity(
        provider_id=provider_id,
        provider_kind="executable",
        version="1.0.0",
        version_source="config",
        binary_fingerprint=BINARY,
        captured_at=AT,
    )


def _task(task_id, accepted, idempotent=True, harmless=True):
    return ProbeTask(task_id, idempotent, harmless, accepted)


def _depart_and_return(registry, provider_id="tool-a"):
    registry.register(provider_id, at=AT)
    registry.note_departure(provider_id, at=AT)
    return registry.note_return(provider_id, at="2026-10-08T09:00:00Z")


def test_return_is_stale_and_selector_excludes_it(tmp_path):
    registry = ProviderRegistry(tmp_path / "registry.json")
    store = QualificationStore(tmp_path / "qual.json")
    identity = _identity()
    qualify(identity, [_Probe()], store, at=AT)
    returned = _depart_and_return(registry)
    assert returned.status == STATUS_STALE
    assert registry.in_rotation("tool-a") is False
    decision = select(
        [ProviderCandidate(identity, 1, WEIGHT_LIGHT, False)],
        store,
        _Gov(),
        registry=registry,
    )
    assert decision.status == STATUS_NO_ELIGIBLE
    assert decision.selected_provider_id is None
    assert decision.rejections[0].reason == "registry_stale"
    reloaded = ProviderRegistry(tmp_path / "registry.json")
    assert reloaded.status_of("tool-a") == STATUS_STALE
    assert reloaded.read()[0].status == STATUS_STALE


def test_accepted_probe_returns_provider_to_rotation(tmp_path):
    registry = ProviderRegistry(tmp_path / "registry.json")
    store = QualificationStore(tmp_path / "qual.json")
    identity = _identity()
    qualify(identity, [_Probe()], store, at=AT)
    _depart_and_return(registry)
    standby = registry.apply_probe("tool-a", _task("probe-1", True), at="2026-10-08T09:05:00Z")
    assert standby.status == STATUS_STANDBY
    assert standby.probe_failures == 0
    decision = select(
        [ProviderCandidate(identity, 4, WEIGHT_LIGHT, False)],
        store,
        _Gov(),
        registry=registry,
    )
    assert decision.status == STATUS_SELECTED
    assert decision.selected_provider_id == "tool-a"
    active = registry.apply_probe("tool-a", _task("probe-2", True), at="2026-10-08T09:06:00Z")
    assert active.status == STATUS_ACTIVE
    assert registry.in_rotation("tool-a") is True


def test_probe_must_be_harmless_and_idempotent(tmp_path):
    registry = ProviderRegistry(tmp_path / "registry.json")
    _depart_and_return(registry)
    with pytest.raises(RegistryError, match="harmless idempotent"):
        _task("probe-x", True, harmless=False)
    with pytest.raises(RegistryError, match="harmless idempotent"):
        _task("probe-y", True, idempotent=False)
    assert registry.status_of("tool-a") == STATUS_STALE


def test_two_failures_quarantine_and_replay_does_not(tmp_path):
    registry = ProviderRegistry(tmp_path / "registry.json")
    store = QualificationStore(tmp_path / "qual.json")
    identity = _identity()
    qualify(identity, [_Probe()], store, at=AT)
    _depart_and_return(registry)
    once = registry.apply_probe("tool-a", _task("probe-1", False), at="2026-10-08T09:05:00Z")
    assert once.status == STATUS_STALE
    assert once.probe_failures == 1
    replay = registry.apply_probe("tool-a", _task("probe-1", False), at="2026-10-08T09:06:00Z")
    assert replay.probe_failures == 1
    assert replay.status == STATUS_STALE
    twice = registry.apply_probe("tool-a", _task("probe-2", False), at="2026-10-08T09:07:00Z")
    assert twice.status == STATUS_QUARANTINED
    assert registry.in_rotation("tool-a") is False
    decision = select(
        [ProviderCandidate(identity, 1, WEIGHT_LIGHT, False)],
        store,
        _Gov(),
        registry=registry,
    )
    assert decision.selected_provider_id is None
    assert decision.rejections[0].reason == "registry_quarantined"
    restored = registry.apply_probe("tool-a", _task("probe-3", True), at="2026-10-08T09:08:00Z")
    assert restored.status == STATUS_STANDBY


def test_return_does_not_rebind_without_a_probe(tmp_path):
    registry = ProviderRegistry(tmp_path / "registry.json")
    registry.register("tool-a", at=AT)
    registry.apply_probe("tool-a", _task("probe-1", True), at=AT)
    assert registry.status_of("tool-a") == STATUS_ACTIVE
    registry.note_departure("tool-a", at=AT)
    returned = registry.note_return("tool-a", at="2026-10-08T09:00:00Z")
    assert returned.status == STATUS_STALE
    again = registry.note_return("tool-a", at="2026-10-08T09:01:00Z")
    assert again.status == STATUS_STALE
    assert again.updated_at == returned.updated_at
    with pytest.raises(RegistryError, match="unknown provider"):
        registry.note_return("missing-tool", at=AT)


def test_malformed_registry_fails_closed(tmp_path):
    path = tmp_path / "registry.json"
    registry = ProviderRegistry(path)
    registry.register("tool-a", at=AT)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(RegistryError, match="malformed"):
        registry.status_of("tool-a")
    store = QualificationStore(tmp_path / "qual.json")
    identity = _identity()
    qualify(identity, [_Probe()], store, at=AT)
    decision = select(
        [ProviderCandidate(identity, 1, WEIGHT_LIGHT, False)],
        store,
        _Gov(),
        registry=registry,
    )
    assert decision.selected_provider_id is None
    assert decision.rejections[0].reason == "registry_unknown"
