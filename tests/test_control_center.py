import unittest
from pathlib import Path
import json
import tempfile
import os
import shutil

from scripts.control_center import generate_board

class TestControlCenter(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.events_dir = self.test_dir / "events"

        self.goals_dir = self.events_dir / "founder-mode"
        self.goals_dir.mkdir(parents=True)

        self.queue_dir = self.events_dir / "mission-queue"
        self.queue_dir.mkdir(parents=True)

        self.worker_dir = self.events_dir / "worker-availability"
        self.worker_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def write_json(self, path: Path, data: dict):
        with open(path, "w") as f:
            json.dump(data, f)

    def test_board_generation_standby(self):
        self.write_json(self.goals_dir / "goals.json", [{"goal_id": "g1", "status": "SATISFIED", "goal": "Test Goal"}])
        self.write_json(self.queue_dir / "queue.json", {"missions": [{"mission_id": "m1", "status": "VERIFIED", "normalized_task": "task"}]})
        self.write_json(self.worker_dir / "fingerprints.json", {"GEMINI": "hash123"})

        board = generate_board(self.events_dir)

        self.assertEqual(board["goals"][0]["status"], "SATISFIED")
        self.assertEqual(board["next_safe_action"], "STANDBY")
        self.assertEqual(len(board["blockers"]), 0)
        self.assertEqual(board["workers"]["fingerprints"]["GEMINI"], "hash123")

    def test_board_generation_blocked(self):
        self.write_json(self.goals_dir / "goals.json", [{"goal_id": "g1", "status": "BLOCKED", "goal": "Test Goal"}])
        self.write_json(self.queue_dir / "queue.json", {"missions": [{"mission_id": "m1", "status": "BLOCKED", "normalized_task": "task"}]})

        board = generate_board(self.events_dir)
        self.assertEqual(board["next_safe_action"], "WAIT_ON_HUMAN_GATE_OR_WORKER_CHANGE")
        self.assertEqual(len(board["blockers"]), 1)
        self.assertEqual(board["blockers"][0]["mission_id"], "m1")

if __name__ == "__main__":
    unittest.main()
