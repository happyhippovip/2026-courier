from courier_core.human_handoff import HumanHandoffContract, HandoffContext
from courier_core.project_primitive import ProjectBasePrimitive
import os

def test_human_handoff_contract():
    ctx = HandoffContext(
        workkey="MAC-09",
        reason="Requires 2FA code",
        required_action="Provide SMS code",
        context_data={"timeout_sec": 300}
    )
    payload = HumanHandoffContract.generate_handoff(ctx)
    assert payload["status"] == "NEEDS_YOU"
    assert payload["action_required"] == "Provide SMS code"
    assert payload["context"]["timeout_sec"] == 300

def test_project_base_primitive(tmp_path):
    proj_dir = str(tmp_path / "my_project")
    primitive = ProjectBasePrimitive(proj_dir)
    
    # Initialize
    primitive.init_safe_haven()
    assert os.path.exists(primitive.state_file)
    
    # Read
    state = primitive.read_state()
    assert state["version"] == 1
    assert state["active"] is True
    
    # Update
    state["protected_paths"].append("src/")
    primitive.update_state(state)
    
    updated = primitive.read_state()
    assert updated["protected_paths"] == ["src/"]
