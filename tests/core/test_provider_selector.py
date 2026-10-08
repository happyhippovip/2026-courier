"""Qualified providers are ranked by total cost. Unqualified ones are never chosen."""

import json

import pytest

from courier_core.provider_identity import ProviderIdentity
from courier_core.provider_qualification import (
    STATUS_STALE,
    ProbeResult,
    QualificationStore,
    qualify,
)
from courier_core.provider_selector import (
    STATUS_NO_ELIGIBLE,
    STATUS_NO_QUALIFIED,
    STATUS_SELECTED,
    WEIGHT_HEAVY,
    WEIGHT_LIGHT,
    ProviderCandidate,
    SelectorError,
    select,
)

AT = "2026-10-08T08:40:00Z"
BINARY = "ab" * 32


class _Probe:
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


class _MeasureOnly:
    def __init__(self, level):
        self.level = level
        self.admit_calls = 0

    def measure_pressure(self):
        return self.level

    def admit_job(self, budget_class):
        self.admit_calls += 1
        return True


def _identity(provider_id, version="1.0.0", kind="executable"):
    return ProviderIdentity(
        provider_id=provider_id,
        provider_kind=kind,
        version=version,
        version_source="config",
        binary_fingerprint=BINARY,
        captured_at=AT,
    )


def _candidate(identity, total_cost, weight=WEIGHT_LIGHT, metered=False):
    return ProviderCandidate(identity, total_cost, weight, metered)


def _qualify(store, identity):
    qualify(identity, [_Probe()], store, at=AT)


def test_cheapest_unqualified_is_not_chosen(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    cheap = _identity("cheap")
    pricey = _identity("pricey")
    _qualify(store, pricey)
    governor = _Pressure("GREEN")
    decision = select(
        [_candidate(cheap, 1), _candidate(pricey, 50)],
        store,
        governor,
    )
    assert decision.status == STATUS_SELECTED
    assert decision.selected_provider_id == "pricey"
    assert decision.total_cost == 50
    assert decision.rejections[0].provider_id == "cheap"
    assert decision.rejections[0].reason == "unqualified"
    assert governor.admit_calls == 0
    again = select([_candidate(cheap, 1), _candidate(pricey, 50)], store, governor)
    assert again.to_json() == decision.to_json()
    parsed = json.loads(decision.to_json())
    assert parsed["selected_provider_id"] == "pricey"
    assert parsed["rejections"][0]["reason"] == "unqualified"


def test_all_unqualified_or_stale_parks(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    missing = _identity("missing")
    stale = _identity("stale-tool")
    _qualify(store, stale)
    store.mark_stale(lambda record: record.name == "stale-tool")
    assert store.read()[0].status == STATUS_STALE
    governor = _Pressure("GREEN")
    decision = select(
        [_candidate(missing, 1), _candidate(stale, 2)],
        store,
        governor,
    )
    assert decision.status == STATUS_NO_QUALIFIED
    assert decision.selected_provider_id is None
    assert decision.total_cost is None
    reasons = {item.provider_id: item.reason for item in decision.rejections}
    assert reasons == {"missing": "unqualified", "stale-tool": "stale"}
    assert governor.admit_calls == 0

    (tmp_path / "qual.json").write_text("{", encoding="utf-8")
    parked = select([_candidate(stale, 2)], store, governor)
    assert parked.status == STATUS_NO_QUALIFIED
    assert parked.rejections[0].reason == "unqualified"


def test_unknown_and_orange_exclude_heavy(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    heavy = _identity("heavy-tool")
    light = _identity("light-tool")
    cheap = _identity("cheap-tool")
    _qualify(store, heavy)
    _qualify(store, light)
    candidates = [
        _candidate(cheap, 1),
        _candidate(heavy, 3, weight=WEIGHT_HEAVY),
        _candidate(light, 9),
    ]
    for level in ("ORANGE", "UNKNOWN"):
        governor = _MeasureOnly(level)
        decision = select(candidates, store, governor)
        assert decision.status == STATUS_SELECTED
        assert decision.selected_provider_id == "light-tool"
        assert decision.governor_pressure == level
        reasons = {item.provider_id: item.reason for item in decision.rejections}
        assert reasons["heavy-tool"] == "heavy_excluded"
        assert reasons["cheap-tool"] == "unqualified"
        assert governor.admit_calls == 0

    only_heavy = select(
        [_candidate(cheap, 1), _candidate(heavy, 3, weight=WEIGHT_HEAVY)],
        store,
        _Pressure("ORANGE"),
    )
    assert only_heavy.status == STATUS_NO_ELIGIBLE
    assert only_heavy.selected_provider_id is None
    assert "cheap-tool" in {item.provider_id for item in only_heavy.rejections}

    green = select(
        [_candidate(heavy, 3, weight=WEIGHT_HEAVY), _candidate(light, 9)],
        store,
        _Pressure("GREEN"),
    )
    assert green.status == STATUS_SELECTED
    assert green.selected_provider_id == "heavy-tool"
    assert green.total_cost == 3


def test_metered_requires_explicit_escalation(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    metered = _identity("metered-tool")
    plain = _identity("plain-tool")
    _qualify(store, metered)
    _qualify(store, plain)
    candidates = [
        _candidate(metered, 1, metered=True),
        _candidate(plain, 8),
    ]
    blocked = select(candidates, store, _Pressure("GREEN"))
    assert blocked.selected_provider_id == "plain-tool"
    assert blocked.escalation_reason is None
    assert {item.provider_id: item.reason for item in blocked.rejections}["metered-tool"] == (
        "metered_requires_escalation"
    )

    allowed = select(
        candidates,
        store,
        _Pressure("YELLOW"),
        escalation_reason="operator approved this run",
    )
    assert allowed.status == STATUS_SELECTED
    assert allowed.selected_provider_id == "metered-tool"
    assert allowed.total_cost == 1
    assert allowed.metered is True
    assert allowed.escalation_reason == "operator approved this run"
    assert allowed.rejections[0].reason == "higher_cost"

    with pytest.raises(SelectorError):
        select(candidates, store, _Pressure("GREEN"), escalation_reason="bad\nreason")


def test_ties_break_deterministically(tmp_path):
    store = QualificationStore(tmp_path / "qual.json")
    beta = _identity("beta")
    alpha = _identity("alpha")
    gamma = _identity("gamma")
    for identity in (beta, alpha, gamma):
        _qualify(store, identity)
    candidates = [
        _candidate(beta, 4),
        _candidate(gamma, 4),
        _candidate(alpha, 4),
    ]
    first = select(candidates, store, _Pressure("GREEN"))
    second = select(list(reversed(candidates)), store, _Pressure("GREEN"))
    assert first.selected_provider_id == "alpha"
    assert second.selected_provider_id == "alpha"
    assert first.to_dict()["rejections"] == second.to_dict()["rejections"]
    assert [item.reason for item in first.rejections] == ["tie_broken", "tie_broken"]
    assert [item.provider_id for item in first.rejections] == ["beta", "gamma"]
    higher = select(
        [_candidate(alpha, 4), _candidate(beta, 7)],
        store,
        _Pressure("GREEN"),
    )
    assert higher.selected_provider_id == "alpha"
    assert higher.rejections[0].provider_id == "beta"
    assert higher.rejections[0].reason == "higher_cost"
