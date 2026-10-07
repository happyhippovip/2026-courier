import pytest
from unittest.mock import patch, MagicMock
from courier_overlay.layout_engine import Rect, Screen
from courier_overlay.mac_window_adapter import MacWindowAdapter

@patch("subprocess.run")
def test_get_screen_success(mock_run):
    mock_run.return_value = MagicMock(stdout="0, 0, 1440, 900\n")
    adapter = MacWindowAdapter()
    screen = adapter.get_screen()
    assert screen.width == 1440
    assert screen.height == 900
    assert screen.usable_rect.height == 875

@patch("subprocess.run")
def test_get_screen_fallback(mock_run):
    mock_run.side_effect = Exception("error")
    adapter = MacWindowAdapter()
    screen = adapter.get_screen()
    assert screen.width == 1920
    assert screen.height == 1080

@patch("subprocess.run")
def test_list_windows(mock_run):
    mock_run.return_value = MagicMock(stdout="Terminal::bash::10::20::400::300\n")
    adapter = MacWindowAdapter()
    windows = adapter.list_windows()
    assert len(windows) == 1
    assert windows[0].window_id == "Terminal::bash"
    assert windows[0].title == "bash"
    assert windows[0].rect == Rect(10, 20, 400, 300)

@patch("subprocess.run")
def test_move_window(mock_run):
    mock_run.return_value = MagicMock()
    adapter = MacWindowAdapter()
    success = adapter.move_window("Terminal::bash", Rect(100, 100, 500, 500))
    assert success is True
    mock_run.assert_called_once()
