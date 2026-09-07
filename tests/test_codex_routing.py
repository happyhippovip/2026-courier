from scripts.courier_safety_dispatcher import DynamicAgentRouter
from scripts.courier_founder_mode import FounderModePlanner

def test_codex_routing():
    # 1. Test Router explicitly selects CODEX
    router = DynamicAgentRouter()
    agent = router.select_agent("high-information-gain specialist", preferred_agent="GEMINI")
    assert agent == "CODEX", f"Expected CODEX, got {agent}"

    # 2. Test Planner handles CODEX_DISCOVERY result
    planner = FounderModePlanner("/tmp")
    goal = {"goal_id": "test-1", "goal": "Fix something"}
    
    # Simulate CODEX returning a finding
    mission = {
        "mission_id": "m-1",
        "result_data": {
            "task_type": "DISCOVERY",
            "finding": {
                "finding_id": "ARCH_ISSUE",
                "description": "Found arch issue",
                "evidence": "some trace",
                "affected_files": ["foo.py"],
                "recommended_action": "Fix it",
                "verification_strategy": "Run tests",
                "confidence": 0.95
            }
        }
    }
    
    # Check that discover_and_plan routes it to GEMINI for implementation
    next_missions = planner.discover_and_plan(goal, [mission])
    assert len(next_missions) == 1
    assert next_missions[0]["preferred_agent"] == "GEMINI"
    assert next_missions[0]["task"]["action"] == "implement_bounded_improvement"
    assert "ARCH_ISSUE" in next_missions[0]["normalized_task"]

if __name__ == "__main__":
    test_codex_routing()
    print("CODEX ROUTING AND RETURN TEST PASSED")
