import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from courier_overlay.layout_engine import LayoutEngine, WindowAdapter, Screen, Rect
from courier_overlay.state_machine import OverlayStateMachine
from courier_overlay.renderer_tk import TkinterRenderer
from courier_overlay.event_bus import emit

class DummyAdapter(WindowAdapter):
    def get_screen(self):
        return Screen(800, 600, Rect(0, 0, 800, 600))
    def list_windows(self):
        return []
    def move_window(self, wid, rect):
        return True

@patch("tkinter.Tk")
@patch("tkinter.Canvas")
def test_w14_overlay_integration(mock_canvas, mock_tk):
    mock_tk_instance = MagicMock()
    mock_tk.return_value = mock_tk_instance
    
    mock_canvas_instance = MagicMock()
    mock_canvas.return_value = mock_canvas_instance
    
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "bus.jsonl")
        
        # 1. Simulate events on the bus
        emit(bus, "agent1", "taskA", "WORKER_CLAIMED", "Claiming task")
        emit(bus, "agent1", "taskA", "WORKER_PROGRESS", "Doing work")
        emit(bus, "agent2", "taskB", "WORKER_CLAIMED", "Claiming B")
        
        # 2. State machine syncs events
        sm = OverlayStateMachine(bus)
        sm.sync()
        snapshot = sm.get_snapshot()
        
        assert len(snapshot) == 2
        
        # 3. Renderer draws them via LayoutEngine
        adapter = DummyAdapter()
        engine = LayoutEngine(adapter)
        renderer = TkinterRenderer(engine)
        
        renderer.render(snapshot)
        
        # Assert canvas delete was called
        mock_canvas_instance.delete.assert_called_with("all")
        
        # We should have created rectangles for the 2 agents
        assert mock_canvas_instance.create_rectangle.call_count == 2
        
        # One is WORKING (green) and one is ASSIGNED (yellow)
        calls = mock_canvas_instance.create_rectangle.call_args_list
        colors = [call.kwargs.get("outline") for call in calls]
        
        assert "green" in colors
        assert "yellow" in colors
