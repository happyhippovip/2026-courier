from enum import Enum
from dataclasses import dataclass, replace
from typing import Optional

class PermissionState(Enum):
    REQUESTED = "REQUESTED"
    WAITING_FOR_USER_PERMISSION = "WAITING_FOR_USER_PERMISSION"
    WAITING_FOR_OS_PERMISSION = "WAITING_FOR_OS_PERMISSION"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class InvalidTransitionError(Exception): pass
class AuthorityExpansionError(Exception): pass

@dataclass(frozen=True)
class PermissionGrant:
    action: str
    resource: str
    scope: str
    expiry: float
    provenance: str

    def is_expired(self, now: float) -> bool:
        return now >= self.expiry

@dataclass(frozen=True)
class PermissionRequest:
    id: str
    state: PermissionState
    requested_action: str
    requested_resource: str
    requested_scope: str
    grant: Optional[PermissionGrant] = None

class PermissionBrokerStateMachine:
    """
    Pure core logic for Permission Broker state transitions.
    Enforces the NO SILENT AUTHORITY EXPANSION invariant.
    """
    
    @staticmethod
    def apply(request: PermissionRequest, event_type: str, payload: dict = None, now: float = None) -> PermissionRequest:
        payload = payload or {}
        
        # Expiration logic takes precedence if we check 'now'
        if request.state == PermissionState.GRANTED and now is not None:
            if request.grant and request.grant.is_expired(now):
                if event_type != "EXPIRE_TICK":
                    # If an event comes in while expired, we transition it immediately
                    # However, usually we might just want a TICK to do this.
                    # We'll transition first.
                    pass
        
        if event_type == "TICK":
            if request.state == PermissionState.GRANTED and now is not None and request.grant:
                if request.grant.is_expired(now):
                    return replace(request, state=PermissionState.EXPIRED)
            return request

        if event_type == "REQUIRE_USER_CONSENT":
            if request.state != PermissionState.REQUESTED:
                raise InvalidTransitionError("Can only request user consent from REQUESTED state")
            return replace(request, state=PermissionState.WAITING_FOR_USER_PERMISSION)

        if event_type == "REQUIRE_OS_CONSENT":
            if request.state != PermissionState.REQUESTED:
                raise InvalidTransitionError("Can only request OS consent from REQUESTED state")
            return replace(request, state=PermissionState.WAITING_FOR_OS_PERMISSION)

        if event_type == "DENY":
            if request.state not in (PermissionState.WAITING_FOR_USER_PERMISSION, PermissionState.WAITING_FOR_OS_PERMISSION):
                raise InvalidTransitionError("Can only deny from a WAITING state")
            return replace(request, state=PermissionState.DENIED)

        if event_type == "GRANT":
            if request.state not in (PermissionState.WAITING_FOR_USER_PERMISSION, PermissionState.WAITING_FOR_OS_PERMISSION):
                raise InvalidTransitionError("Can only grant from a WAITING state")
            
            grant = payload.get("grant")
            if not grant or not isinstance(grant, PermissionGrant):
                raise ValueError("GRANT event requires a valid PermissionGrant object in payload")
            
            # INVARIANT: NO SILENT AUTHORITY EXPANSION
            # The granted permissions must perfectly match or be a subset.
            # In this strict broker, we require exact match to prevent implicit scope bloat.
            if grant.action != request.requested_action:
                raise AuthorityExpansionError(f"Cannot expand action from {request.requested_action} to {grant.action}")
            if grant.resource != request.requested_resource:
                raise AuthorityExpansionError(f"Cannot expand resource from {request.requested_resource} to {grant.resource}")
            if grant.scope != request.requested_scope:
                raise AuthorityExpansionError(f"Cannot expand scope from {request.requested_scope} to {grant.scope}")

            return replace(request, state=PermissionState.GRANTED, grant=grant)

        if event_type == "REVOKE":
            if request.state != PermissionState.GRANTED:
                raise InvalidTransitionError("Can only revoke a GRANTED permission")
            return replace(request, state=PermissionState.REVOKED)
            
        raise InvalidTransitionError(f"Unknown event '{event_type}' or invalid for state {request.state.name}")
