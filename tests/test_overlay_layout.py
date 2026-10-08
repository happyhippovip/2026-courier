import pytest
from courier_overlay.layout_engine import LayoutEngine, WindowAdapter, Screen, Rect

class DummyAdapter(WindowAdapter):
    def get_screen(self):
        return Screen(1920, 1080, Rect(0, 0, 1920, 1080))
    def list_windows(self):
        return []
    def move_window(self, win_id, rect):
        return True

def test_geometry_12_profiles():
    engine = LayoutEngine(DummyAdapter())
    screen = engine.adapter.get_screen()
    rects = engine.calculate_grid(screen, 12)
    assert len(rects) == 12
    # 12 profiles in 4 cols => 3 rows
    assert rects[0].width == 1920 // 4
    assert rects[0].height == 1080 // 3
    assert rects[0].x == 0
    assert rects[0].y == 0
    assert rects[11].x == (3 * (1920 // 4))
    assert rects[11].y == (2 * (1080 // 3))

def test_geometry_16_profiles():
    engine = LayoutEngine(DummyAdapter())
    screen = engine.adapter.get_screen()
    rects = engine.calculate_grid(screen, 16)
    assert len(rects) == 16
    # 16 profiles in 4 cols => 4 rows
    assert rects[0].width == 1920 // 4
    assert rects[0].height == 1080 // 4

def test_invalid_profile_count():
    engine = LayoutEngine(DummyAdapter())
    screen = engine.adapter.get_screen()
    with pytest.raises(ValueError):
        engine.calculate_grid(screen, 10)

