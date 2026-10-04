from enum import Enum, auto

class PermissionState(Enum):
    GRANTED = auto()
    DENIED = auto()
    WAITING_FOR_OS_PERMISSION = auto() # OS-level prompt (UAC, etc.)
    WAITING_FOR_USER_PERMISSION = auto() # Courier-level prompt (Ask user in chat)

class PermissionRequest:
    def __init__(self, action: str, requires_uac: bool = False, requires_user_consent: bool = False):
        self.action = action
        self.requires_uac = requires_uac
        self.requires_user_consent = requires_user_consent
        self.state = PermissionState.GRANTED
        
        if self.requires_user_consent:
            self.state = PermissionState.WAITING_FOR_USER_PERMISSION
        elif self.requires_uac:
            self.state = PermissionState.WAITING_FOR_OS_PERMISSION

class PermissionManager:
    def __init__(self):
        self.pending_requests = {}
        
    def request_permission(self, req_id: str, request: PermissionRequest) -> PermissionState:
        self.pending_requests[req_id] = request
        return request.state

    def resolve_os_permission(self, req_id: str, granted: bool):
        if req_id in self.pending_requests:
            req = self.pending_requests[req_id]
            if req.state == PermissionState.WAITING_FOR_OS_PERMISSION:
                req.state = PermissionState.GRANTED if granted else PermissionState.DENIED
                
    def resolve_user_permission(self, req_id: str, granted: bool):
        if req_id in self.pending_requests:
            req = self.pending_requests[req_id]
            if req.state == PermissionState.WAITING_FOR_USER_PERMISSION:
                req.state = PermissionState.GRANTED if granted else PermissionState.DENIED
