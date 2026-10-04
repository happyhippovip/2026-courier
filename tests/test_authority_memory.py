import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from authority_memory import AuthorityGrant, AuthorityStore, AuthorityException

def test_valid_authority_is_granted():
    store = AuthorityStore()
    grant = AuthorityGrant(
        grant_id="g1",
        scope="infrastructure",
        allowed_action="restart",
        resource="app_server",
        source_of_authority="user_explicit_prompt",
        start_time=1000,
        expiry_time=2000
    )
    store.add_grant(grant)
    
    # Asserting authority within valid time window succeeds
    assert store.assert_authority(current_time=1500, scope="infrastructure", action="restart", resource="app_server") == grant

def test_expired_authority_is_rejected():
    store = AuthorityStore()
    grant = AuthorityGrant(
        grant_id="g1",
        scope="infrastructure",
        allowed_action="restart",
        resource="app_server",
        source_of_authority="user_explicit_prompt",
        start_time=1000,
        expiry_time=2000
    )
    store.add_grant(grant)
    
    # Asserting authority after expiry fails
    with pytest.raises(AuthorityException, match="No valid authority found"):
        store.assert_authority(current_time=2001, scope="infrastructure", action="restart", resource="app_server")

def test_revoked_authority_is_rejected():
    store = AuthorityStore()
    grant = AuthorityGrant(
        grant_id="g1",
        scope="infrastructure",
        allowed_action="restart",
        resource="app_server",
        source_of_authority="user_explicit_prompt",
        start_time=1000,
        expiry_time=2000
    )
    store.add_grant(grant)
    
    # Revoke it
    store.revoke_grant("g1")
    
    # Even if time is valid, it should fail
    with pytest.raises(AuthorityException, match="No valid authority found"):
        store.assert_authority(current_time=1500, scope="infrastructure", action="restart", resource="app_server")

def test_authority_budget_consumption():
    grant = AuthorityGrant(
        grant_id="g1",
        scope="cloud",
        allowed_action="provision",
        resource="vm",
        source_of_authority="user_explicit_prompt",
        start_time=1000,
        expiry_time=2000,
        budget=10.0
    )
    
    # Valid consumption
    grant.consume_budget(4.0)
    assert grant.budget == 6.0
    
    # Over consumption
    with pytest.raises(AuthorityException, match="Insufficient budget"):
        grant.consume_budget(7.0)
