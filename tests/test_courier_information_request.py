import json
import os
from pathlib import Path
from scripts.courier_founder_mode import FounderModeMVP, FounderModePlanner

def test_information_request_planning():
    planner = FounderModePlanner("/tmp")
    goal = {"goal_id": "test-1", "goal": "Fix something"}
    
    # Simulate worker returning WORKER_INFORMATION_REQUEST
    mission = {
        "mission_id": "m-1",
        "result_data": {
            "task_type": "INFORMATION_REQUEST",
            "request": "Show me the logs",
            "preferred_capability": "repo verification"
        }
    }
    
    # Check that discover_and_plan routes to CLI1 gather_information_read_only
    next_missions = planner.discover_and_plan(goal, [mission])
    assert len(next_missions) == 1
    assert next_missions[0]["preferred_agent"] == "CLI1"
    assert next_missions[0]["task"]["action"] == "gather_information_read_only"
    assert next_missions[0]["task"]["requested_information"] == "Show me the logs"

def test_information_result_planning():
    planner = FounderModePlanner("/tmp")
    goal = {"goal_id": "test-1", "goal": "Fix something"}
    
    # Simulate CLI1 returning INFORMATION_RESULT
    mission = {
        "mission_id": "m-2",
        "result_data": {
            "task_type": "INFORMATION_RESULT",
            "evidence": "Here are the logs: error on line 42",
            "request": "Show me the logs"
        }
    }
    
    # Check that discover_and_plan routes back to GEMINI implementation
    next_missions = planner.discover_and_plan(goal, [mission])
    assert len(next_missions) == 1
    assert next_missions[0]["preferred_agent"] == "GEMINI"
    assert next_missions[0]["task"]["action"] == "implement_bounded_improvement"
    assert "error on line 42" in next_missions[0]["task"]["goal_context"]
    
if __name__ == "__main__":
    test_information_request_planning()
    test_information_result_planning()
    print("ALL TESTS PASSED")
