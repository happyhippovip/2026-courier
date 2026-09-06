import tempfile
import unittest
from tests.test_mission_repair import TestMissionRepair
import sys

class DebugR5(TestMissionRepair):
    def test_debug(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        from pathlib import Path
        from tests.test_mission_repair import MockBoundary
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        dispatcher.process_next_mission("GEMINI")
        
        missions = dispatcher.mission_queue.read_all()
        updated_impl = [m for m in missions if m["mission_id"] == "impl_1"][0]
        
        # Manually evaluate to see what goes wrong
        last_mission = updated_impl
        
        v_ref = last_mission.get("verification_reference")
        t_hash = last_mission.get("task_hash")
        
        print("v_ref:", v_ref)
        print("t_hash:", t_hash)
        
        result_data = last_mission.get("result_data", {})
        if not result_data:
            import json
            ref = last_mission.get("result_reference")
            print("ref:", ref)
            if ref and isinstance(ref, str) and Path(ref).exists():
                try:
                    with open(ref, "r") as f:
                        data = json.load(f)
                    result_data = data.get("result", data)
                except Exception as e:
                    print("Error loading:", e)
        print("result_data:", result_data)
        print("mission_id in result_data:", result_data.get("mission_id"))
        print("mission_id in mission:", last_mission.get("mission_id"))
        
if __name__ == '__main__':
    unittest.main()
