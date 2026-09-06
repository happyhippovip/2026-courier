import unittest
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher

class TestActionAwareHumanGate(unittest.TestCase):
    def test_safe_cases(self):
        safe_cases = [
            "inspect tests/test_login.py",
            "modify local deploy parser",
            "analyze docs/publication.md",
            "test OAuth classification locally",
            "no external deployment requested",
            "local simulated billing test",
            "do not manually select a worker"
        ]
        
        for text in safe_cases:
            mission = {"goal": text}
            task = {}
            self.assertFalse(
                CourierSafetyDispatcher._requires_human_gate(mission, task),
                f"False positive on safe phrase: {text}"
            )

    def test_gate_cases(self):
        gate_cases = [
            "deploy production now",
            "without spend, deploy production now",
            "login to external service now",
            "no OAuth required, login external service now",
            "publish this externally",
            "purchase/upgrade paid capacity",
            "perform wallet signing",
            "execute real-money trade",
            "enable billing"
        ]
        
        for text in gate_cases:
            mission = {"goal": text}
            task = {}
            self.assertTrue(
                CourierSafetyDispatcher._requires_human_gate(mission, task),
                f"False negative on gated phrase: {text}"
            )

if __name__ == '__main__':
    unittest.main()
