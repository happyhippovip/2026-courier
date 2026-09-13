import unittest
import os
import shutil
from scripts.idea_inbox import IdeaInbox

class TestIdeaInbox(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_courier_state"
        self.db_path = f"{self.test_dir}/idea_inbox.json"
        self.inbox = IdeaInbox(self.db_path)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_add_and_update_idea(self):
        idea = self.inbox.add_idea("Build a feature")
        self.assertIsNotNone(idea["idea_id"])
        self.assertEqual(idea["raw_text"], "Build a feature")
        self.assertEqual(idea["status"], "NEW")

        pending = self.inbox.get_pending_ideas()
        self.assertEqual(len(pending), 1)

        updated = self.inbox.update_idea(idea["idea_id"], {"status": "NORMALIZED", "normalized_intent": "build_feature"})
        self.assertEqual(updated["status"], "NORMALIZED")
        self.assertEqual(updated["normalized_intent"], "build_feature")

        pending_after = self.inbox.get_pending_ideas()
        self.assertEqual(len(pending_after), 0)

if __name__ == '__main__':
    unittest.main()
