import unittest
import os
import shutil
from scripts.idea_inbox import IdeaInbox
from scripts.courier_founder_mode import MultiChatGoalIntake
from scripts.idea_to_goal import IdeaToGoalBridge

class TestIdeaToGoalBridge(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_courier_state_bridge"
        os.makedirs(self.test_dir, exist_ok=True)
        self.inbox = IdeaInbox(f"{self.test_dir}/idea_inbox.json")
        self.intake = MultiChatGoalIntake(workspace_dir=self.test_dir, )
        self.bridge = IdeaToGoalBridge(self.inbox, self.intake)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_process_pending_ideas(self):
        self.inbox.add_idea("Implement auto-retry")
        self.inbox.add_idea("Build feature X")
        
        processed = self.bridge.process_pending_ideas()
        self.assertEqual(len(processed), 2)
        
        # Check goals were created
        goals = self.intake._read_no_lock()
        self.assertEqual(len(goals), 2)
        self.assertEqual(goals[0]["goal"], "Implement auto-retry")
        self.assertEqual(goals[1]["goal"], "Build feature X")
        
        # Check ideas were updated
        ideas = self.inbox._read_all()
        self.assertEqual(ideas[0]["status"], "GOAL_CREATED")
        self.assertEqual(ideas[0]["goal_id"], goals[0]["goal_id"])

if __name__ == '__main__':
    unittest.main()
