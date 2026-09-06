import tempfile
import unittest
from tests.test_mission_repair import TestMissionRepair
import sys

class PrintR6(TestMissionRepair):
    def test_print_r6(self):
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

        unexecuted_new_impl = self.impl_mission.copy()
        unexecuted_new_impl["mission_id"] = "impl_2"
        unexecuted_new_impl["status"] = "VERIFIED"
        unexecuted_new_impl["task_hash"] = updated_impl["task_hash"]
        unexecuted_new_impl["verification_reference"] = updated_impl["verification_reference"]
        unexecuted_new_impl["result_reference"] = updated_impl["result_reference"]

        print("\n--- UNEXECUTED NEW IMPL IN R6 ---")
        for k, v in unexecuted_new_impl.items():
            print(f"{k}: {v}")

if __name__ == '__main__':
    unittest.main()
