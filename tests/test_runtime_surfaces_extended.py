import pytest
from courier_runtime.surfaces import (
    SurfaceSupervisor,
    Budget,
    NORMAL,
    CONSERVE,
    NO_NEW_VISIBLE,
    pressure_level,
    adapter_for,
    MacAdapter,
    WindowsAdapter,
)


class MockIdentity:
    def __init__(self):
        self.alive = {}

    def __call__(self, s):
        return self.alive.get(s.pid) == s.create_time


def test_pressure_level_ram_thresholds():
    b = Budget(soft=2, hard=4, ram_conserve_pct=80.0, ram_stop_pct=90.0)

    # 1 visible, normal ram -> NORMAL
    assert pressure_level(b, visible_count=1, ram_used_pct=75.0) == NORMAL

    # 1 visible, ram >= 80 -> CONSERVE
    assert pressure_level(b, visible_count=1, ram_used_pct=85.0) == CONSERVE

    # 1 visible, ram >= 90 -> NO_NEW_VISIBLE
    assert pressure_level(b, visible_count=1, ram_used_pct=92.0) == NO_NEW_VISIBLE

    # Ram None falls back to count
    assert pressure_level(b, visible_count=2, ram_used_pct=None) == CONSERVE
    assert pressure_level(b, visible_count=4, ram_used_pct=None) == NO_NEW_VISIBLE


def test_adapter_for_lookup():
    mac = adapter_for("darwin")
    assert isinstance(mac, MacAdapter)

    win = adapter_for("win32")
    assert isinstance(win, WindowsAdapter)

    # Fallback to base adapter for linux or unknown
    other = adapter_for("linux")
    assert other is not None


def test_surface_headless_admission_under_pressure(tmp_path):
    ident = MockIdentity()
    sup = SurfaceSupervisor(
        tmp_path / "surfaces.json",
        host="mac-1",
        os_name="darwin",
        budget=Budget(soft=1, hard=2),
        identity=ident,
        clock=lambda: 1000.0,
    )

    # Open first visible surface
    d1 = sup.admit("muse", "W1", "prompt 1", needs_visible=True)
    assert d1.action == "OPEN"
    sup.attach(d1.surface_id, 101, 101.0)
    ident.alive[101] = 101.0

    # Next workkey allows headless: under soft limit (visible=1 >= soft=1) it should admit as HEADLESS
    d2 = sup.admit("muse", "W2", "prompt 2", needs_visible=False, allow_headless=True)
    assert d2.action == "HEADLESS"
