import dataclasses
from typing import List, Optional, Tuple, Dict

@dataclasses.dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

@dataclasses.dataclass(frozen=True)
class Screen:
    width: int
    height: int
    usable_rect: Rect

@dataclasses.dataclass(frozen=True)
class WindowState:
    window_id: str
    title: str
    rect: Rect

class WindowAdapter:
    """Interface for macOS / Windows window discovery and movement."""
    def get_screen(self) -> Screen:
        raise NotImplementedError

    def list_windows(self) -> List[WindowState]:
        raise NotImplementedError

    def move_window(self, window_id: str, rect: Rect) -> bool:
        raise NotImplementedError

class LayoutEngine:
    def __init__(self, adapter: WindowAdapter):
        self.adapter = adapter
        self.history: List[List[WindowState]] = []

    def snapshot(self) -> List[WindowState]:
        """Snapshot current window state."""
        state = self.adapter.list_windows()
        self.history.append(state)
        return state
        
    def restore(self) -> bool:
        """Restore previous window state."""
        if not self.history:
            return False
        last_state = self.history.pop()
        success = True
        for win in last_state:
            if not self.adapter.move_window(win.window_id, win.rect):
                success = False
        return success

    def calculate_grid(self, screen: Screen, profiles: int) -> List[Rect]:
        """Calculate layout geometry for 12, 14, or 16 profiles."""
        if profiles not in (12, 14, 16):
            raise ValueError(f"Unsupported profile count: {profiles}")
            
        rects = []
        cols = 4
        rows = profiles // cols + (1 if profiles % cols else 0)
        
        w = screen.usable_rect.width // cols
        h = screen.usable_rect.height // rows
        
        for i in range(profiles):
            r = i // cols
            c = i % cols
            rects.append(Rect(
                x=screen.usable_rect.x + c * w,
                y=screen.usable_rect.y + r * h,
                width=w,
                height=h
            ))
            
        return rects

    def apply_layout(self, window_ids: List[str], profiles: int) -> bool:
        """Apply layout geometry to a list of windows."""
        screen = self.adapter.get_screen()
        rects = self.calculate_grid(screen, profiles)
        
        self.snapshot()
        
        success = True
        for i, win_id in enumerate(window_ids):
            if i >= len(rects):
                break
            if not self.adapter.move_window(win_id, rects[i]):
                success = False
        return success
