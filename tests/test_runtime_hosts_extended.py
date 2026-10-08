import pytest
import datetime as dt

from courier_runtime.hosts import (
    Host,
    Requirement,
    Evidence,
    HEALTHY,
    BUSY,
    IDLE,
    DEGRADED,
    OFFLINE,
    RECOVERING,
    eligible,
    select,
    accept_evidence,
    NoEligibleHost,
)
from courier_runtime.deadlines import (
    easter,
    holidays_niedersachsen,
    next_working_day,
    add_months,
    deadline,
)


def test_hosts_eligible_filtering():
    req = Requirement(capabilities=frozenset({"python", "linux"}), privacy="hosted")
    
    h1 = Host(device_id="h1", capabilities=frozenset({"python", "linux"}), health=HEALTHY, privacy="hosted", active_leases=0, max_leases=1)
    h2 = Host(device_id="h2", capabilities=frozenset({"python"}), health=HEALTHY, privacy="hosted", active_leases=0, max_leases=1)
    h3 = Host(device_id="h3", capabilities=frozenset({"python", "linux"}), health=DEGRADED, privacy="hosted", active_leases=0, max_leases=1)
    h4 = Host(device_id="h4", capabilities=frozenset({"python", "linux"}), health=OFFLINE, privacy="hosted", active_leases=0, max_leases=1)
    h5 = Host(device_id="h5", capabilities=frozenset({"python", "linux"}), health=RECOVERING, privacy="hosted", active_leases=0, max_leases=1)
    h6 = Host(device_id="h6", capabilities=frozenset({"python", "linux"}), health=HEALTHY, privacy="hosted", active_leases=1, max_leases=1) # fully leased
    h7 = Host(device_id="h7", capabilities=frozenset({"python", "linux"}), health=HEALTHY, privacy="own", active_leases=0, max_leases=1) # wrong privacy
    h8 = Host(device_id="h8", capabilities=frozenset({"python", "linux", "gpu"}), health=IDLE, privacy="hosted", active_leases=0, max_leases=2)

    all_hosts = [h1, h2, h3, h4, h5, h6, h7, h8]
    res = eligible(req, all_hosts)
    assert res == [h1, h8]


def test_hosts_select_priority_and_error():
    req = Requirement(capabilities=frozenset({"python"}), privacy=None)

    # h1 is 0.10/hr, IDLE
    h1 = Host(device_id="b-host", capabilities=frozenset({"python"}), health=IDLE, cost_per_hour_eur=0.10)
    # h2 is 0.05/hr, BUSY
    h2 = Host(device_id="a-host", capabilities=frozenset({"python"}), health=BUSY, cost_per_hour_eur=0.05, active_leases=1, max_leases=2)
    # h3 is 0.05/hr, IDLE
    h3 = Host(device_id="c-host", capabilities=frozenset({"python"}), health=IDLE, cost_per_hour_eur=0.05)
    # h4 is 0.05/hr, IDLE, alphabetically earlier
    h4 = Host(device_id="b-host-cheap", capabilities=frozenset({"python"}), health=IDLE, cost_per_hour_eur=0.05)

    # Cheapest first: 0.05 (h2, h3, h4). Then non-busy first (h3, h4). Then stable by device_id ("b-host-cheap" < "c-host").
    selected = select(req, [h1, h2, h3, h4])
    assert selected == h4

    # Empty candidate pool raises NoEligibleHost
    empty_req = Requirement(capabilities=frozenset({"quantum_computing"}))
    with pytest.raises(NoEligibleHost) as exc_info:
        select(empty_req, [h1, h2, h3, h4])
    assert "no healthy host offers ['quantum_computing']" in str(exc_info.value)


def test_hosts_accept_evidence():
    hosts = [
        Host(device_id="dev-win", capabilities=frozenset({"windows_native", "python"})),
        Host(device_id="dev-lin", capabilities=frozenset({"linux", "python"})),
    ]

    # Unknown device
    e_unknown = Evidence(workkey="wk-1", capability="windows_native", device_id="dev-mac", artifact_sha256="abc", passed=True)
    ok, reason = accept_evidence(e_unknown, "windows_native", hosts)
    assert not ok
    assert "unknown device dev-mac" in reason

    # Device lacks capability or requirement mismatch
    e_wrong_cap = Evidence(workkey="wk-1", capability="windows_native", device_id="dev-lin", artifact_sha256="abc", passed=True)
    ok, reason = accept_evidence(e_wrong_cap, "windows_native", hosts)
    assert not ok
    assert "dev-lin cannot evidence windows_native" in reason

    e_mismatch = Evidence(workkey="wk-1", capability="linux", device_id="dev-lin", artifact_sha256="abc", passed=True)
    ok, reason = accept_evidence(e_mismatch, "windows_native", hosts)
    assert not ok
    assert "dev-lin cannot evidence windows_native" in reason

    # Failed evidence
    e_failed = Evidence(workkey="wk-1", capability="windows_native", device_id="dev-win", artifact_sha256="abc", passed=False)
    ok, reason = accept_evidence(e_failed, "windows_native", hosts)
    assert not ok
    assert reason == "evidence did not pass"

    # Valid passed evidence
    e_valid = Evidence(workkey="wk-1", capability="windows_native", device_id="dev-win", artifact_sha256="abc", passed=True)
    ok, reason = accept_evidence(e_valid, "windows_native", hosts)
    assert ok
    assert reason == "accepted"


def test_deadlines_edge_cases():
    # Month calculation edge cases (e.g. leap year Feb 29)
    # Feb 2024 is leap year, Feb 2025 is not
    assert add_months(dt.date(2024, 1, 31), 1) == dt.date(2024, 2, 29)
    assert add_months(dt.date(2025, 1, 31), 1) == dt.date(2025, 2, 28)
    assert add_months(dt.date(2024, 2, 29), 12) == dt.date(2025, 2, 28)

    # Custom fiction_days and posted_on parameter
    res = deadline(
        letter_date=dt.date(2026, 3, 1),
        months=2,
        posted_on=dt.date(2026, 3, 5),
        fiction_days=3,
        received_on=None
    )
    # Posted March 5 + 3 days = March 8 (Sunday). Bekanntgabe is March 8.
    # 2 months after March 8 is May 8, 2026 (Friday).
    # May 8, 2026 is a regular working day.
    assert res["bekanntgabe"] == dt.date(2026, 3, 8)
    assert res["deadline"] == dt.date(2026, 5, 8)
    assert res["target"] == dt.date(2026, 5, 1) # Note: target is strictly deadline - 7 days
