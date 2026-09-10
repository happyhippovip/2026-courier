import os
import subprocess

class AntigravityTaskController:
    def is_available(self) -> bool:
        return False  # P0-1: REAL_ANTIGRAVITY_CONTROL_BACKEND_UNAVAILABLE

    def cancel(self, native_task_id: str):
        if not self.is_available():
            raise RuntimeError("Antigravity cancellation API is not available.")

    def get_state(self, native_task_id: str) -> str:
        if not self.is_available():
            raise RuntimeError("Antigravity cancellation API is not available.")
        return "UNKNOWN"

    def list_owned(self, attempt_id: str):
        if not self.is_available():
            raise RuntimeError("Antigravity cancellation API is not available.")
        return []
