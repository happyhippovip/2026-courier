from dataclasses import dataclass
from typing import Any, List
from enum import Enum, IntEnum

class PrivacyCategory(IntEnum):
    PUBLIC_PROJECT = 10
    PRIVATE_PROJECT = 20
    LOCAL_ONLY = 30
    SECRET = 40
    PERSONAL_SENSITIVE = 50

class MemoryBoundaryException(Exception):
    pass

@dataclass
class CategorizedMemoryRecord:
    record_id: str
    category: PrivacyCategory
    payload: Any

class MemoryBoundaryAuditor:
    def __init__(self):
        self._records = []
        
    def add_record(self, record: CategorizedMemoryRecord):
        self._records.append(record)
        
    def export_for_destination(self, destination: str, max_allowed_category: PrivacyCategory) -> List[CategorizedMemoryRecord]:
        """
        Exports records suitable for a given destination (e.g. 'github_issue', 'ci_log').
        Ensures NO record with a higher privacy category leaks into the export.
        """
        safe_export = []
        
        for record in self._records:
            if record.category > max_allowed_category:
                raise MemoryBoundaryException(
                    f"BOUNDARY VIOLATION: Attempted to export record '{record.record_id}' "
                    f"with category {record.category.name} to destination '{destination}' "
                    f"which only allows up to {max_allowed_category.name}."
                )
            safe_export.append(record)
            
        return safe_export

    def filter_for_destination(self, destination: str, max_allowed_category: PrivacyCategory) -> List[CategorizedMemoryRecord]:
        """
        Like export, but silently drops violating records instead of throwing an exception.
        Used for building safe subsets (e.g. stripping local paths before telemetry).
        """
        return [r for r in self._records if r.category <= max_allowed_category]
