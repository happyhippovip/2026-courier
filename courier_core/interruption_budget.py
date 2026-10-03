import time

class InterruptionBudget:
    """MAC-08: Define/test when Courier may interrupt a human."""
    def __init__(self, max_interruptions: int, window_sec: float):
        self.max_interruptions = max_interruptions
        self.window_sec = window_sec
        self.timestamps = []

    def can_interrupt(self) -> bool:
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t <= self.window_sec]
        return len(self.timestamps) < self.max_interruptions

    def consume(self) -> bool:
        if self.can_interrupt():
            self.timestamps.append(time.time())
            return True
        return False
