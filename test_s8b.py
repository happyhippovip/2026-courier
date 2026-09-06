import tempfile
import unittest
from tests.test_mission_repair import TestMissionRepair
import sys

class TestS8B(TestMissionRepair):
    def test_s8b_multiline_explicit_file_intent_survives_discovery(self):
        goal = {
            "goal_id": "g-multiline",
            "goal": "Create repository-root file:\nstructured_effect.txt\n\nwith exact content:\nDONE",
        }
        discovery = dict(self.completed_disc)
        planned = self.p.discover_and_plan(goal, [discovery])
        print("PLANNED:", planned)
        print("ERROR:", self.p.last_planning_error)

if __name__ == '__main__':
    unittest.main()
