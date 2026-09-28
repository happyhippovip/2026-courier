import pytest
import subprocess

def test_routing_proof(monkeypatch):
    import scripts.routing_proof as script
    
    # Mock subprocess.Popen to prevent server start
    class MockPopen:
        def __init__(self, *args, **kwargs):
            pass
        def terminate(self):
            pass
            
    monkeypatch.setattr(subprocess, "Popen", MockPopen)
    
    posts = []
    def mock_http_post(endpoint, data):
        posts.append((endpoint, data))
        if endpoint == "/tasks/claim":
            worker = data.get("worker_id")
            if worker == "win1":
                return {"task": {"target_agent": "windows"}}, 200
            elif worker == "lin1":
                return {"task": {"target_agent": "linux"}}, 200
        return {}, 200
        
    monkeypatch.setattr(script, "http_post", mock_http_post)
    
    script.main()
    
    assert len(posts) == 6
    assert posts[-1][0] == "/tasks/claim"

