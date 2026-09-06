import unittest
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_founder_mode import MultiChatGoalIntake

class TestCourierRecoverySemantics(unittest.TestCase):
    def test_01_no_publication_no_human_gate(self):
        mission = {"goal": "No publication", "normalized_task": ""}
        task = {}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_02_no_deployment_no_human_gate(self):
        mission = {"goal": "No deployment, publication, customer contact or purchases", "normalized_task": ""}
        task = {}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_03_publish_this_human_gate(self):
        mission = {"goal": "Publish this", "normalized_task": ""}
        task = {}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_04_login_to_google_human_gate(self):
        mission = {"goal": "Login to Google", "normalized_task": ""}
        task = {}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_05_purchase_this_human_gate(self):
        mission = {"goal": "Purchase this", "normalized_task": ""}
        task = {}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_06_mixed_intent_human_gate(self):
        mission = {"goal": "Do not publish the draft, but purchase the service", "normalized_task": ""}
        task = {}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

