from dataclasses import dataclass
from typing import List, Dict, Optional
import json

class SensitiveDataException(Exception):
    pass

@dataclass
class DeviceStateMemory:
    """
    Long-term durable memory representation of a target device/runtime environment.
    Designed to store structural truths, NOT transient noise (like CPU temp) or secrets.
    """
    device_id: str
    os_name: str
    os_version: str
    
    # Meaningful runtime capabilities
    runtime_capabilities: List[str]
    
    # Courier-specific installation metadata
    installed_courier_version: str
    
    # Durable environment realities
    verified_dependencies: Dict[str, str] # e.g. {"python": "3.12.10", "git": "2.44.0"}
    
    # Timestamp of last clean shutdown (used to detect unexpected crashes since last boot)
    last_clean_shutdown_ts: Optional[int]
    
    # Known recovery maneuvers supported by this specific runtime
    supported_recovery_capabilities: List[str]

    def to_json(self) -> str:
        # Pre-serialization validation to prevent secret leakage
        self._validate_no_secrets()
        return json.dumps(self.__dict__, indent=2)
        
    @classmethod
    def from_json(cls, json_str: str) -> "DeviceStateMemory":
        obj = cls(**json.loads(json_str))
        obj._validate_no_secrets()
        return obj
        
    def _validate_no_secrets(self):
        """
        Hard enforcement against accidentally writing secrets (tokens, keys, passwords)
        into ordinary memory records.
        """
        # Convert dictionary to string for naive secret scanning
        dump_str = str(self.__dict__).lower()
        
        forbidden_substrings = [
            "password", "secret", "token", "api_key", "credentials", 
            "private_key", "bearer", "oauth"
        ]
        
        for forbidden in forbidden_substrings:
            if forbidden in dump_str:
                raise SensitiveDataException(
                    f"Refusing to process device state memory: found forbidden string indicating a secret ('{forbidden}'). "
                    "Secrets must not be stored in ordinary memory records."
                )
