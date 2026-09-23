import pytest
from app.cannon.processes import launch_gated

def test_launch_gated_prevents_yolo():
    with pytest.raises(ValueError, match="Sicherheitsrichtlinie verletzt: Flag --yolo ist strengstens verboten."):
        launch_gated(["muse", "exec", "--yolo"], cwd=".", env={})

def test_launch_gated_prevents_disable_sandbox():
    with pytest.raises(ValueError, match="Sicherheitsrichtlinie verletzt: Flag --disable-sandbox ist strengstens verboten."):
        launch_gated(["muse", "exec", "--disable-sandbox"], cwd=".", env={})
        
def test_launch_gated_prevents_dangerously_disable():
    with pytest.raises(ValueError, match="Sicherheitsrichtlinie verletzt: Flag --dangerously-disable-permissions ist strengstens verboten."):
        launch_gated(["muse", "exec", "--dangerously-disable-permissions"], cwd=".", env={})
