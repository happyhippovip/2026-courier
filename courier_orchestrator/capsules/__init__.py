"""Work Capsules: community extension registry V1 (stdlib only, local only).

Upload -> validate -> quarantine -> independent review -> human gate -> distribute.
Recalled capsules are never distributed again.
"""
from .schema import Capsule, CapsuleStatus, LICENSE_ALLOWLIST
from .validate import ValidationResult, validate_capsule
from .registry import CapsuleRegistry, RegistryError

__all__ = ["Capsule", "CapsuleStatus", "LICENSE_ALLOWLIST", "ValidationResult",
           "validate_capsule", "CapsuleRegistry", "RegistryError"]
