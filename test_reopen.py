import json
import uuid
from scripts.courier_founder_mode import MultiChatGoalIntake

def run():
    intake = MultiChatGoalIntake('.')
    goal_id = intake.submit_goal("CLI", "Test goal")
    # Force set to HUMAN_GATE
    def _force(data):
        for r in data:
            if r["goal_id"] == goal_id:
                r["status"] = "HUMAN_GATE"
                return True
    intake._mutate(_force)
    
    # Check it's HUMAN_GATE
    with open("events/founder-mode/goals.json") as f:
        data = json.load(f)
        assert any(r["goal_id"] == goal_id and r["status"] == "HUMAN_GATE" for r in data), "Not HUMAN_GATE"
        
    # Reopen
    res = intake.reopen_invalidated_blocker(goal_id)
    assert res, "Reopen failed"
    
    # Check persistence
    with open("events/founder-mode/goals.json") as f:
        data = json.load(f)
        assert any(r["goal_id"] == goal_id and r["status"] == "PENDING" for r in data), "Not PENDING"
        
    print("TARGETED_RECOVERY_TEST: PASS")

run()
