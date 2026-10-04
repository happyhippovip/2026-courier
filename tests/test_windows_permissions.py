import pytest
from scripts.windows_permission_state import PermissionManager, PermissionRequest, PermissionState

def test_user_permission():
    pm = PermissionManager()
    req = PermissionRequest("delete_project", requires_user_consent=True)
    state = pm.request_permission("req1", req)
    
    assert state == PermissionState.WAITING_FOR_USER_PERMISSION
    
    pm.resolve_user_permission("req1", True)
    assert pm.pending_requests["req1"].state == PermissionState.GRANTED

def test_os_permission():
    pm = PermissionManager()
    req = PermissionRequest("install_service", requires_uac=True)
    state = pm.request_permission("req2", req)
    
    assert state == PermissionState.WAITING_FOR_OS_PERMISSION
    
    pm.resolve_os_permission("req2", False)
    assert pm.pending_requests["req2"].state == PermissionState.DENIED

def test_os_cannot_resolve_user():
    pm = PermissionManager()
    req = PermissionRequest("delete_project", requires_user_consent=True)
    pm.request_permission("req3", req)
    
    # OS resolution should not affect user permission
    pm.resolve_os_permission("req3", True)
    assert pm.pending_requests["req3"].state == PermissionState.WAITING_FOR_USER_PERMISSION
