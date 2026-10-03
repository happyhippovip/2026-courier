import os
from courier_core.test_isolation import TestIsolationEnforcer

def test_isolation_enforcement():
    enforcer = TestIsolationEnforcer()
    pre_env = enforcer.snapshot_env()
    
    # Simulate test run leaking state
    os.environ["LEAKED_TEST_VAR"] = "1"
    post_env = enforcer.snapshot_env()
    
    # Check enforcement
    assert enforcer.enforce_isolation(pre_env, post_env) is False
    assert "LEAKED_TEST_VAR" in enforcer.detect_leakage(post_env)
    
    # Cleanup
    del os.environ["LEAKED_TEST_VAR"]
    clean_post_env = enforcer.snapshot_env()
    assert enforcer.enforce_isolation(pre_env, clean_post_env) is True
