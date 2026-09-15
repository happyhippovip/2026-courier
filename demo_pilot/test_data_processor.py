import pytest
from data_processor import process_records

def test_process_records_handles_missing_keys():
    input_data = [{"name": "Item A"}] # Missing ID and status
    
    # The remediation should ensure 'id' is generated if missing
    # and original dictionary is not mutated.
    original_input = list(input_data)
    
    result = process_records(input_data)
    
    assert len(result) == 1
    assert result[0]["status"] == "pending"
    assert "id" in result[0]
    
    # Ensure immutability (original input should NOT have 'status' or 'id')
    assert "status" not in original_input[0]
