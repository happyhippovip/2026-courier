import pytest
from courier_core.permission_broker import (
    PermissionBrokerStateMachine as Broker,
    PermissionState, PermissionRequest, PermissionGrant,
    InvalidTransitionError, AuthorityExpansionError
)

def create_request():
    return PermissionRequest(
        id="req-123",
        state=PermissionState.REQUESTED,
        requested_action="READ",
        requested_resource="/etc/secrets",
        requested_scope="system"
    )

def create_grant(action="READ", resource="/etc/secrets", scope="system", expiry=200.0, provenance="user"):
    return PermissionGrant(
        action=action,
        resource=resource,
        scope=scope,
        expiry=expiry,
        provenance=provenance
    )

def test_valid_user_consent_lifecycle():
    req = create_request()
    
    # Wait for user
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    assert req.state == PermissionState.WAITING_FOR_USER_PERMISSION
    
    # Grant
    grant = create_grant()
    req = Broker.apply(req, "GRANT", {"grant": grant})
    assert req.state == PermissionState.GRANTED
    assert req.grant == grant
    
    # Tick before expiry
    req = Broker.apply(req, "TICK", now=150.0)
    assert req.state == PermissionState.GRANTED
    
    # Tick after expiry
    req = Broker.apply(req, "TICK", now=250.0)
    assert req.state == PermissionState.EXPIRED

def test_valid_os_consent_denial():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_OS_CONSENT")
    assert req.state == PermissionState.WAITING_FOR_OS_PERMISSION
    
    req = Broker.apply(req, "DENY")
    assert req.state == PermissionState.DENIED

def test_revoke():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    req = Broker.apply(req, "GRANT", {"grant": create_grant()})
    
    req = Broker.apply(req, "REVOKE")
    assert req.state == PermissionState.REVOKED

# --- NEGATIVE TESTS (AUTHORITY EXPANSION) ---

def test_no_silent_authority_expansion_action():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    
    malicious_grant = create_grant(action="WRITE") # Expanding READ to WRITE
    with pytest.raises(AuthorityExpansionError, match="Cannot expand action"):
        Broker.apply(req, "GRANT", {"grant": malicious_grant})

def test_no_silent_authority_expansion_resource():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    
    malicious_grant = create_grant(resource="/") # Expanding to root directory
    with pytest.raises(AuthorityExpansionError, match="Cannot expand resource"):
        Broker.apply(req, "GRANT", {"grant": malicious_grant})

def test_no_silent_authority_expansion_scope():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    
    malicious_grant = create_grant(scope="global") # Expanding scope
    with pytest.raises(AuthorityExpansionError, match="Cannot expand scope"):
        Broker.apply(req, "GRANT", {"grant": malicious_grant})

# --- NEGATIVE TESTS (INVALID TRANSITIONS) ---

def test_invalid_grant_from_requested():
    req = create_request()
    with pytest.raises(InvalidTransitionError, match="Can only grant from a WAITING state"):
        Broker.apply(req, "GRANT", {"grant": create_grant()})

def test_invalid_revoke_from_waiting():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    with pytest.raises(InvalidTransitionError, match="Can only revoke a GRANTED"):
        Broker.apply(req, "REVOKE")

def test_invalid_deny_from_granted():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    req = Broker.apply(req, "GRANT", {"grant": create_grant()})
    with pytest.raises(InvalidTransitionError, match="Can only deny from a WAITING state"):
        Broker.apply(req, "DENY")
        
def test_missing_grant_payload():
    req = create_request()
    req = Broker.apply(req, "REQUIRE_USER_CONSENT")
    with pytest.raises(ValueError, match="requires a valid PermissionGrant"):
        Broker.apply(req, "GRANT", {})

