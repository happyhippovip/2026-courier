import json
import hashlib
import base64
from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class ContinuationContext:
    project: str
    workkey: str
    sha: str
    session_id: str
    checkpoint_state: str

class ContinuationTokenError(Exception):
    pass

class ContinuationToken:
    def __init__(self, context: ContinuationContext):
        self.context = context
        
    def generate_hash(self) -> str:
        """Generate a deterministic hash bound to the context."""
        data = self.context.project + self.context.workkey + self.context.sha + self.context.session_id + self.context.checkpoint_state
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def serialize(self) -> str:
        """Serialize the context and its hash into a safe base64 token."""
        payload = asdict(self.context)
        payload["_hash"] = self.generate_hash()
        
        json_str = json.dumps(payload, sort_keys=True)
        return base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')

    @classmethod
    def deserialize(cls, token_str: str) -> "ContinuationToken":
        """Deserialize and verify a token."""
        try:
            json_str = base64.urlsafe_b64decode(token_str.encode('utf-8')).decode('utf-8')
            payload = json.loads(json_str)
        except Exception as e:
            raise ContinuationTokenError("Invalid token format") from e
            
        if "_hash" not in payload:
            raise ContinuationTokenError("Token is missing verification hash")
            
        expected_hash = payload.pop("_hash")
        
        try:
            context = ContinuationContext(**payload)
        except TypeError as e:
            raise ContinuationTokenError("Token payload is missing required context fields") from e
            
        token = cls(context)
        
        if token.generate_hash() != expected_hash:
            raise ContinuationTokenError("Token hash verification failed! The token has been tampered with or corrupted.")
            
        return token
