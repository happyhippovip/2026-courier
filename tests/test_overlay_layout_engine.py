import pytest
from courier_overlay.layout_engine import LayoutEngine, WindowAdapter, Screen, Rect, WindowState

class MockAdapter(WindowAdapter):
    def __init__(self, screen_width=1920, screen_height=1080):
        self.screen = Screen(screen_width, screen_height, Rect(0, 0, screen_width, screen_height))
        self.windows = {}

    def get_screen(self):
        return self.screen

    def list_windows(self):
        return [WindowState(wid, f"Window {wid}", r) for wid, r in self.windows.items()]

    def move_window(self, window_id, rect):
        self.windows[window_id] = rect
        return True

def test_layout_engine_calculates_grid():
    adapter = MockAdapter()
    engine = LayoutEngine(adapter)
    
    # 12 profiles -> 3 rows, 4 cols
    rects = engine.calculate_grid(adapter.get_screen(), 12)
    assert len(rects) == 12
    assert rects[0] == Rect(0, 0, 1920//4, 1080//3)
    assert rects[-1] == Rect(1920//4 * 3, 1080//3 * 2, 1920//4, 1080//3)

def test_layout_engine_unsupported_profiles():
    adapter = MockAdapter()
    engine = LayoutEngine(adapter)
    with pytest.raises(ValueError):
        engine.calculate_grid(adapter.get_screen(), 15)

def test_layout_engine_snapshot_restore():
    adapter = MockAdapter()
    adapter.windows = {"w1": Rect(10, 10, 100, 100)}
    engine = LayoutEngine(adapter)
    
    engine.snapshot()
    adapter.move_window("w1", Rect(20, 20, 200, 200))
    assert adapter.windows["w1"].width == 200
    
    success = engine.restore()
    assert success
    assert adapter.windows["w1"].width == 100

def test_layout_engine_apply_layout():
    adapter = MockAdapter()
    adapter.windows = {"w1": Rect(0,0,0,0), "w2": Rect(0,0,0,0)}
    engine = LayoutEngine(adapter)
    
    success = engine.apply_layout(["w1", "w2"], 12)
    assert success
    
    assert adapter.windows["w1"] == Rect(0, 0, 1920//4, 1080//3)
    assert adapter.windows["w2"] == Rect(1920//4, 0, 1920//4, 1080//3)
