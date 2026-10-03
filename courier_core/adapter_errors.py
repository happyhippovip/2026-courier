from enum import Enum

class ErrorSeverity(Enum):
    TRANSIENT = "TRANSIENT"
    FATAL = "FATAL"
    REQUIRES_USER = "REQUIRES_USER"

class AdapterError(Exception):
    def __init__(self, message: str, severity: ErrorSeverity):
        super().__init__(message)
        self.severity = severity

class MissingElementError(AdapterError):
    def __init__(self, element_id: str):
        super().__init__(f"Element {element_id} not found", ErrorSeverity.TRANSIENT)

class ProviderTimeoutError(AdapterError):
    def __init__(self, endpoint: str):
        super().__init__(f"Timeout reaching {endpoint}", ErrorSeverity.TRANSIENT)

class ProviderAuthError(AdapterError):
    def __init__(self):
        super().__init__("Authentication failed", ErrorSeverity.REQUIRES_USER)

class SurfaceCorruptedError(AdapterError):
    def __init__(self):
        super().__init__("Screen/surface is corrupted", ErrorSeverity.FATAL)

class ProcessStormError(AdapterError):
    def __init__(self, process_name: str):
        super().__init__(f"Process storm detected: {process_name}", ErrorSeverity.FATAL)
