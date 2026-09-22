"""web.status() live-Anreicherung: Fehler bleiben beobachtbar, Form bleibt stabil."""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from app.cannon import web


def _minimal_mac_status():
    return {
        "state": "IDLE",
        "overnight": {"laufart": "BEGRENZT", "verbleibend": 5, "erledigt": 0},
        "task_counts": {},
        "invariants": {},
        "current_task": None,
    }


class WebLivePayloadTests(unittest.TestCase):
    def setUp(self):
        self._saved_profile = os.environ.get("COURIER_CANNON_PROFILE")
        os.environ["COURIER_CANNON_PROFILE"] = "yolo"
        self._saved_path = list(sys.path)
        self.addCleanup(self._restore_env)
        patches = [
            patch.object(web, "get_mac_status", return_value=_minimal_mac_status()),
            patch.object(web, "CHILD", None),
            patch.object(web, "JOB", None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _restore_env(self):
        if self._saved_profile is None:
            os.environ.pop("COURIER_CANNON_PROFILE", None)
        else:
            os.environ["COURIER_CANNON_PROFILE"] = self._saved_profile
        sys.path[:] = self._saved_path

    def test_live_failure_is_logged_and_shape_preserved(self):
        failing = types.ModuleType("cannon_yolo")

        def _boom():
            raise RuntimeError("boom-live-payload")

        failing.live_payload = _boom
        with patch.dict(sys.modules, {"cannon_yolo": failing}):
            with self.assertLogs(web.__name__, level="WARNING") as logs:
                result = web.status()
        self.assertNotIn("live", result)
        self.assertIsNone(result.get("error"))
        self.assertTrue(
            any("cannon live payload unavailable" in line for line in logs.output),
            f"expected warning, got: {logs.output}",
        )

    def test_live_success_propagates(self):
        payload = {"text": "hello-live"}
        working = types.ModuleType("cannon_yolo")
        working.live_payload = lambda: payload
        with patch.dict(sys.modules, {"cannon_yolo": working}):
            result = web.status()
        self.assertEqual(result.get("live"), payload)


if __name__ == "__main__":
    unittest.main()
