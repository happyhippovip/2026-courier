import tempfile
import os
import pytest
from datetime import datetime

from courier_overlay.event_bus import emit
from courier_overlay.state_machine import OverlayStateMachine, WorkerState
from courier_overlay.layout_engine import (
    LayoutEngine,
    Rect,
    Screen,
    WindowAdapter,
    WindowState,
)


class FakeWindowAdapter(WindowAdapter):
    def __init__(self, screen: Screen, initial_windows=None):
        self._screen = screen
        self._windows = initial_windows or []
        self.moved_log = []

    def get_screen(self) -> Screen:
        return self._screen

    def list_windows(self):
        return list(self._windows)

    def move_window(self, window_id: str, rect: Rect) -> bool:
        self.moved_log.append((window_id, rect))
        # Update matching window rect
        for i, w in enumerate(self._windows):
            if w.window_id == window_id:
                self._windows[i] = WindowState(window_id, w.title, rect)
                break
        return True


class TestOverlayTrayExtended:
    """Rigorous edge-case coverage for desktop overlay state transitions and layout contracts."""

    def test_state_machine_all_event_types(self):
        with tempfile.TemporaryDirectory() as td:
            bus = os.path.join(td, "bus.jsonl")
            sm = OverlayStateMachine(bus)

            # 1. TASK_ASSIGNED -> ASSIGNED
            emit(bus, "agent-x", "task-100", "TASK_ASSIGNED", "Task assigned to agent")
            sm.sync()
            w = sm.workers["agent-x"]
            assert w.status == "ASSIGNED"
            assert w.current_task == "task-100"

            # 2. WORKER_STARTED -> WORKING
            emit(bus, "agent-x", "task-100", "WORKER_STARTED", "Starting execution")
            sm.sync()
            assert sm.workers["agent-x"].status == "WORKING"

            # 3. CUSTOMS_ENTER -> WORKING
            emit(bus, "agent-x", "task-100", "CUSTOMS_ENTER", "Entering customs verification")
            sm.sync()
            assert sm.workers["agent-x"].status == "WORKING"

            # 4. CUSTOMS_REJECTED -> BLOCKED
            emit(bus, "agent-x", "task-100", "CUSTOMS_REJECTED", "Rejected by policy gate")
            sm.sync()
            assert sm.workers["agent-x"].status == "BLOCKED"

            # 5. RESULT_APPROVED -> IDLE and task cleared
            emit(bus, "agent-x", "task-100", "RESULT_APPROVED", "Outcome approved")
            sm.sync()
            assert sm.workers["agent-x"].status == "IDLE"
            assert sm.workers["agent-x"].current_task is None

            # 6. RESULT_REJECTED -> BLOCKED
            emit(bus, "agent-x", "task-200", "RESULT_REJECTED", "Digest drift detected")
            sm.sync()
            assert sm.workers["agent-x"].status == "BLOCKED"

    def test_layout_engine_unsupported_profile_counts_rejected(self):
        adapter = FakeWindowAdapter(Screen(1920, 1080, Rect(0, 0, 1920, 1080)))
        engine = LayoutEngine(adapter)

        for invalid_count in [1, 5, 8, 10, 13, 15, 20]:
            with pytest.raises(ValueError, match="Unsupported profile count"):
                engine.calculate_grid(adapter.get_screen(), invalid_count)

    def test_layout_engine_grid_geometry_bounds(self):
        screen = Screen(2560, 1440, Rect(100, 50, 2360, 1340))
        adapter = FakeWindowAdapter(screen)
        engine = LayoutEngine(adapter)

        for count in [12, 14, 16]:
            rects = engine.calculate_grid(screen, count)
            assert len(rects) == count
            for r in rects:
                # Every grid window must sit inside usable bounds
                assert r.x >= screen.usable_rect.x
                assert r.y >= screen.usable_rect.y
                assert r.x + r.width <= screen.usable_rect.x + screen.usable_rect.width
                assert r.y + r.height <= screen.usable_rect.y + screen.usable_rect.height
                assert r.width > 0
                assert r.height > 0

    def test_layout_engine_restore_empty_history_returns_false(self):
        adapter = FakeWindowAdapter(Screen(1920, 1080, Rect(0, 0, 1920, 1080)))
        engine = LayoutEngine(adapter)
        assert engine.restore() is False

    def test_layout_engine_apply_layout_and_restore_fidelity(self):
        screen = Screen(1920, 1080, Rect(0, 0, 1920, 1080))
        initial_windows = [
            WindowState("win-1", "App 1", Rect(10, 10, 500, 400)),
            WindowState("win-2", "App 2", Rect(600, 10, 500, 400)),
        ]
        adapter = FakeWindowAdapter(screen, initial_windows=initial_windows)
        engine = LayoutEngine(adapter)

        # Apply layout moves windows and snapshots previous state
        ok = engine.apply_layout(["win-1", "win-2"], 12)
        assert ok is True
        assert len(engine.history) == 1
        assert len(adapter.moved_log) == 2

        # Restore returns windows to initial rects
        restored = engine.restore()
        assert restored is True
        assert len(engine.history) == 0

        current_windows = {w.window_id: w.rect for w in adapter.list_windows()}
        assert current_windows["win-1"] == Rect(10, 10, 500, 400)
        assert current_windows["win-2"] == Rect(600, 10, 500, 400)
