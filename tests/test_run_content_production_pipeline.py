import pytest
from pathlib import Path
import json

def test_run_content_production_pipeline_dedupe(tmp_path, monkeypatch):
    import scripts.run_content_production_pipeline as script
    
    monkeypatch.setattr(script, "execute_idea_stage", lambda *args: tmp_path / "runtime" / "c-1" / "mission-123" / "idea.txt")
    
    manifest_file = tmp_path / "runtime" / "c-1" / "mission-123" / "pipeline_manifest.json"
    manifest_file.parent.mkdir(parents=True)
    manifest_file.write_text(json.dumps({
        "schema_version": "2.0",
        "stages": {
            "IDEA": {"status": "COMPLETED", "artifact_path": "idea.txt"}
        }
    }))
    
    chan_config = tmp_path / "chan.json"
    chan_config.write_text(json.dumps({
        "channels": [{"channel_id": "c-1", "platform": "YOUTUBE", "content_project": "FruitKI", "workflow_id": "wf-1"}]
    }))
    
    wf_config = tmp_path / "wf.json"
    wf_config.write_text(json.dumps({
        "workflows": [{"workflow_id": "wf-1", "production_steps": ["IDEA"]}]
    }))
    
    res = script.run_pipeline(
        channel_id="c-1",
        topic="test",
        mission_id="mission-123",
        runtime_dir=tmp_path / "runtime",
        channels_path=chan_config,
        workflows_path=wf_config,
        local_tools_path=tmp_path / "tools.json",
        force_rerun=False
    )
    
    assert res["overall_status"] == "COMPLETED"
    assert res["stages"]["IDEA"]["status"] == "COMPLETED"
    
def test_run_content_production_pipeline_force(tmp_path, monkeypatch):
    import scripts.run_content_production_pipeline as script
    
    called = []
    def mock_execute_idea_stage(step_dir, topic, proj, plat):
        called.append(True)
        f = step_dir / "idea.txt"
        f.write_text("ok")
        return f
        
    monkeypatch.setattr(script, "execute_idea_stage", mock_execute_idea_stage)
    
    manifest_file = tmp_path / "runtime" / "c-1" / "mission-123" / "pipeline_manifest.json"
    manifest_file.parent.mkdir(parents=True)
    manifest_file.write_text(json.dumps({
        "schema_version": "2.0",
        "stages": {
            "IDEA": {"status": "COMPLETED", "artifact_path": "idea.txt"}
        }
    }))
    
    chan_config = tmp_path / "chan.json"
    chan_config.write_text(json.dumps({
        "channels": [{"channel_id": "c-1", "platform": "YOUTUBE", "content_project": "FruitKI", "workflow_id": "wf-1"}]
    }))
    
    wf_config = tmp_path / "wf.json"
    wf_config.write_text(json.dumps({
        "workflows": [{"workflow_id": "wf-1", "production_steps": ["IDEA"]}]
    }))
    
    res = script.run_pipeline(
        channel_id="c-1",
        topic="test",
        mission_id="mission-123",
        runtime_dir=tmp_path / "runtime",
        channels_path=chan_config,
        workflows_path=wf_config,
        local_tools_path=tmp_path / "tools.json",
        force_rerun=True
    )
    
    assert len(called) == 1
    assert res["overall_status"] == "COMPLETED"

