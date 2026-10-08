import pytest
from courier_runtime.surfaces import (
    SurfaceSupervisor, Budget, MacAdapter, WindowsAdapter, adapter_for,
    NORMAL, CONSERVE, NO_NEW_VISIBLE, SURFACE_BUDGET_EXHAUSTED,
    STARTING, WORKING, IDLE_READY, PARKED, COMPLETED
)


class DummyIdentity:
    def __init__(self):
        self.alive = {}

    def __call__(self, s):
        return self.alive.get(s.pid) == s.create_time


def test_budget_levels_under_pressure(tmp_path):
    budget = Budget(soft=2, hard=4, ram_conserve_pct=75.0, ram_stop_pct=88.0)
    ident = DummyIdentity()
    
    # 1. Normal state
    s = SurfaceSupervisor(tmp_path / "surfaces.json", "host-1", "darwin", budget=budget, identity=ident)
    assert s.level(ram_used_pct=50.0) == NORMAL

    # 2. Ram pressure triggers CONSERVE
    assert s.level(ram_used_pct=78.0) == CONSERVE

    # 3. Ram pressure triggers NO_NEW_VISIBLE
    assert s.level(ram_used_pct=92.0) == NO_NEW_VISIBLE


def test_headless_preference_under_conserve_pressure(tmp_path):
    budget = Budget(soft=2, hard=4, ram_conserve_pct=70.0, ram_stop_pct=90.0)
    ident = DummyIdentity()
    s = SurfaceSupervisor(tmp_path / "surfaces.json", "host-1", "darwin", budget=budget, identity=ident)
    
    # Fill soft budget (2 surfaces)
    d1 = s.admit("codex", "W1", "prompt1")
    s.attach(d1.surface_id, 101, 101.0)
    ident.alive[101] = 101.0

    d2 = s.admit("codex", "W2", "prompt2")
    s.attach(d2.surface_id, 102, 102.0)
    ident.alive[102] = 102.0

    # Next work with allow_headless=True under soft limit reach -> HEADLESS
    d3 = s.admit("codex", "W3", "prompt3", allow_headless=True)
    assert d3.action == "HEADLESS"


def test_why_not_closable_reasons(tmp_path):
    ident = DummyIdentity()
    s = SurfaceSupervisor(tmp_path / "surfaces.json", "host-1", "darwin", budget=Budget(soft=2, hard=3), identity=ident)
    d = s.admit("muse", "W1", "prompt")
    s.attach(d.surface_id, 201, 201.0)
    ident.alive[201] = 201.0

    # Mark surface as having unsaved state and active work
    s.surfaces[d.surface_id].unsaved = True
    
    reasons = s.why_not_closable(d.surface_id)
    assert any("unsaved work" in r for r in reasons)
    assert any("active work" in r for r in reasons)
    assert any("no durable checkpoint" in r for r in reasons)

    # Reclaim attempt fails closed
    rec = s.reclaim(d.surface_id, lambda surf: True)
    assert rec["closed"] is False
    assert len(rec["reasons"]) > 0


def test_adapter_for_resolution():
    mac_ad = adapter_for("darwin")
    assert isinstance(mac_ad, MacAdapter)
    assert mac_ad.name == "darwin"
    
    win_ad = adapter_for("win32")
    assert isinstance(win_ad, WindowsAdapter)
    assert win_ad.name == "win32"

    default_ad = adapter_for("linux")
    assert default_ad.name == "generic"
