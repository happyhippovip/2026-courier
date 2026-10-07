import subprocess
import json
from typing import List
from courier_overlay.layout_engine import WindowAdapter, Screen, WindowState, Rect

class MacWindowAdapter(WindowAdapter):
    def get_screen(self) -> Screen:
        # Simplistic stub for testing AppleScript integration.
        # In a real app we'd parse `system_profiler SPDisplaysDataType` or `osascript` bounds.
        script = 'tell application "Finder" to get bounds of window of desktop'
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            bounds = result.stdout.strip().split(", ")
            if len(bounds) == 4:
                # bounds is left, top, right, bottom
                w = int(bounds[2]) - int(bounds[0])
                h = int(bounds[3]) - int(bounds[1])
                return Screen(width=w, height=h, usable_rect=Rect(0, 25, w, h-25)) # assuming 25px menu bar
        except Exception as e:
            pass
        return Screen(1920, 1080, Rect(0, 0, 1920, 1080))

    def list_windows(self) -> List[WindowState]:
        script = """
        set winData to {}
        tell application "System Events"
            set visibleProcs to processes where background only is false
            repeat with proc in visibleProcs
                set procName to name of proc
                repeat with win in windows of proc
                    try
                        set winName to name of win
                        set {x, y} to position of win
                        set {w, h} to size of win
                        set end of winData to procName & "::" & winName & "::" & x & "::" & y & "::" & w & "::" & h
                    end try
                end repeat
            end repeat
        end tell
        set {tid, text item delimiters} to {text item delimiters, linefeed}
        set output to winData as text
        set text item delimiters to tid
        return output
        """
        windows = []
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split("::")
                if len(parts) == 6:
                    proc_name, win_name, x, y, w, h = parts
                    # We use "ProcName::WinName" as a pseudo window_id for Mac
                    win_id = f"{proc_name}::{win_name}"
                    rect = Rect(int(x), int(y), int(w), int(h))
                    windows.append(WindowState(window_id=win_id, title=win_name, rect=rect))
        except Exception:
            pass
        return windows

    def move_window(self, window_id: str, rect: Rect) -> bool:
        parts = window_id.split("::", 1)
        if len(parts) != 2:
            return False
        proc_name, win_name = parts
        script = f"""
        tell application "System Events"
            tell process "{proc_name}"
                set target_win to window "{win_name}"
                set position of target_win to {{{rect.x}, {rect.y}}}
                set size of target_win to {{{rect.width}, {rect.height}}}
            end tell
        end tell
        """
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return True
        except Exception:
            return False
