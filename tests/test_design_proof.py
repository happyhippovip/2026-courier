import unittest
from scripts.control_center import get_os_telemetry, evaluate_health

class TestDesignProof(unittest.TestCase):
    def test_01_health_classifier_unknown_handling(self):
        # UNKNOWN telemetry remains UNKNOWN, does not become GREEN silently
        telemetry = {
            "uptime": "UNKNOWN", "load": "UNKNOWN", "crash_loop": "UNKNOWN", "recording_active": "UNKNOWN"
        }
        res = evaluate_health(telemetry)
        self.assertEqual(res["color"], "UNKNOWN")

    def test_02_recording_detection_changes_workload(self):
        # High load + no recording = ORANGE
        telemetry = {"uptime": "1:00", "load": " 100.0", "crash_loop": False, "recording_active": False}
        res = evaluate_health(telemetry)
        self.assertEqual(res["color"], "ORANGE")

        # High load + recording = GREEN (KNOWN_HEAVY_WORKLOAD)
        telemetry["recording_active"] = True
        res = evaluate_health(telemetry)
        self.assertEqual(res["color"], "GREEN")

    def test_03_crash_loop_is_red(self):
        telemetry = {"uptime": "1:00", "load": " 1.0", "crash_loop": True, "recording_active": False}
        res = evaluate_health(telemetry)
        self.assertEqual(res["color"], "RED")
        self.assertEqual(res["restart"], "NOW")

if __name__ == '__main__':
    unittest.main()
