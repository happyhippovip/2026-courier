import pytest

def test_q14_proof(monkeypatch):
    import scripts.q14_proof as script
    import threading
    
    # prevent server start
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)
    
    posts = []
    def mock_http_post(endpoint, data):
        posts.append((endpoint, data))
        if endpoint == "/tasks/claim":
            # first time return linux task
            if len(posts) == 4:
                return {"task": {"target_agent": "linux"}}, 200
            # second time return None
            return {}, 200
        return {}, 200
        
    monkeypatch.setattr(script, "http_post", mock_http_post)
    
    script.main()
    
    assert len(posts) == 5
    assert posts[-1][0] == "/tasks/claim"

