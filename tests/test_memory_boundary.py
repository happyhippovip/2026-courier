import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_boundary import MemoryBoundaryAuditor, CategorizedMemoryRecord, PrivacyCategory, MemoryBoundaryException

def setup_auditor():
    auditor = MemoryBoundaryAuditor()
    auditor.add_record(CategorizedMemoryRecord("mem-1", PrivacyCategory.PUBLIC_PROJECT, "Project Name: Courier"))
    auditor.add_record(CategorizedMemoryRecord("mem-2", PrivacyCategory.PRIVATE_PROJECT, "Internal roadmap discussion"))
    auditor.add_record(CategorizedMemoryRecord("mem-3", PrivacyCategory.LOCAL_ONLY, "C:/Users/lol/local_cache"))
    auditor.add_record(CategorizedMemoryRecord("mem-4", PrivacyCategory.SECRET, "github_token=ghp_1234"))
    auditor.add_record(CategorizedMemoryRecord("mem-5", PrivacyCategory.PERSONAL_SENSITIVE, "Home Address: 123 Main St"))
    return auditor

def test_export_to_public_github_issue_fails_on_leak():
    auditor = setup_auditor()
    
    # Attempting to export all records to a GitHub issue which requires PUBLIC_PROJECT
    with pytest.raises(MemoryBoundaryException, match="BOUNDARY VIOLATION"):
        auditor.export_for_destination("github_issue", PrivacyCategory.PUBLIC_PROJECT)

def test_export_to_ci_log_fails_on_leak():
    auditor = setup_auditor()
    
    # CI Logs might be allowed to see PRIVATE_PROJECT but definitely NOT SECRET or PERSONAL
    with pytest.raises(MemoryBoundaryException, match="BOUNDARY VIOLATION"):
        auditor.export_for_destination("ci_log", PrivacyCategory.PRIVATE_PROJECT)

def test_filter_for_customer_telemetry():
    auditor = setup_auditor()
    
    # Customer telemetry can only see PUBLIC_PROJECT. Filter should drop the rest safely.
    safe_telemetry = auditor.filter_for_destination("customer_telemetry", PrivacyCategory.PUBLIC_PROJECT)
    
    assert len(safe_telemetry) == 1
    assert safe_telemetry[0].record_id == "mem-1"

def test_export_local_debug_fails_on_secrets():
    auditor = setup_auditor()
    
    # Local debugging is allowed to see LOCAL_ONLY and below, but NOT SECRET or PERSONAL_SENSITIVE
    with pytest.raises(MemoryBoundaryException, match="BOUNDARY VIOLATION"):
        auditor.export_for_destination("local_debug_dump", PrivacyCategory.LOCAL_ONLY)
