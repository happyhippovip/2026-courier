from dataclasses import dataclass
from typing import List

@dataclass
class LauncherCommand:
    executable: str
    args: List[str]

class LauncherContract:
    """WK-06: Verify launcher starts actual V1 Core + Hub contract."""
    REQUIRED_ARGS = ["--core-v1", "--enable-hub"]

    @classmethod
    def verify_launch_intent(cls, command: LauncherCommand) -> bool:
        if not command.executable.endswith("courier.exe") and not command.executable.endswith("courier"):
            return False
        
        for req in cls.REQUIRED_ARGS:
            if req not in command.args:
                return False
                
        return True
