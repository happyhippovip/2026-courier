from dataclasses import dataclass
from typing import Optional

class AuthorityException(Exception):
    pass

@dataclass
class AuthorityGrant:
    grant_id: str
    scope: str
    allowed_action: str
    resource: str
    source_of_authority: str
    
    start_time: int
    expiry_time: int
    
    budget: Optional[float] = None
    is_revoked: bool = False
    
    def is_valid(self, current_time: int) -> bool:
        """
        Validates whether the authority is currently active.
        """
        if self.is_revoked:
            return False
            
        if current_time < self.start_time:
            return False
            
        if current_time >= self.expiry_time:
            return False
            
        return True
        
    def consume_budget(self, amount: float):
        if self.budget is None:
            return # Unlimited budget
            
        if self.budget < amount:
            raise AuthorityException(f"Insufficient budget. Have {self.budget}, need {amount}")
            
        self.budget -= amount

class AuthorityStore:
    """
    Separated from ordinary project memory to ensure strict lifecycle enforcement.
    """
    def __init__(self):
        self._grants = {} # type: dict[str, AuthorityGrant]
        
    def add_grant(self, grant: AuthorityGrant):
        self._grants[grant.grant_id] = grant
        
    def revoke_grant(self, grant_id: str):
        if grant_id in self._grants:
            self._grants[grant_id].is_revoked = True
            
    def assert_authority(self, current_time: int, scope: str, action: str, resource: str):
        """
        Throws an AuthorityException if no valid grant exists for this specific combination.
        """
        for grant in self._grants.values():
            if grant.scope == scope and grant.allowed_action == action and grant.resource == resource:
                if grant.is_valid(current_time):
                    return grant
                    
        raise AuthorityException(
            f"No valid authority found for scope='{scope}', action='{action}', resource='{resource}'. "
            "Memory of a past permission is not permanent permission."
        )
