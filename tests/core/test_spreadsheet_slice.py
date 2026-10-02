import pytest
from courier_core.spreadsheet_slice import (
    SpreadsheetPipeline, StructuredRequest, MutationPlan,
    VerificationResult, SpreadsheetReceipt
)

def get_fixture():
    return {
        "Sheet1": [
            ["ID", "Name", "Score"],
            ["1", "Alice", "95"],
            ["2", "Bob", "=B2+5"] # Formula
        ]
    }

def test_update_one_cell_and_verify_formula_retained():
    # 1. LOAD WORKBOOK
    fixture = get_fixture()
    wb = SpreadsheetPipeline.load_workbook(fixture)
    
    # Pre-condition: Check Bob's formula
    assert wb["Sheet1"][2][2] == "=B2+5"
    
    # 2. UNDERSTAND STRUCTURED REQUEST
    # Update Alice's score to 99 in C2 (row 1, col 2)
    req = StructuredRequest(action="UPDATE_CELL", sheet_name="Sheet1", target_coord="C2", value="99")
    plan = SpreadsheetPipeline.understand_request(req, wb)
    
    # 3. PLAN MUTATION
    assert len(plan.operations) == 1
    assert plan.operations[0] == {"row": 1, "col": 2, "value": "99"}
    
    # 4. APPLY MUTATION
    SpreadsheetPipeline.apply_mutation(wb, plan)
    
    # 5. VERIFY RESULT
    verification = SpreadsheetPipeline.verify_result(wb, plan)
    assert verification.success is True
    assert verification.verified_operations == 1
    
    # Extra check: Formula retained, unrelated cells untouched
    assert wb["Sheet1"][2][2] == "=B2+5"
    assert wb["Sheet1"][1][1] == "Alice"
    assert wb["Sheet1"][1][2] == "99" # The changed cell
    
    # 6. GENERATE RECEIPT
    receipt = SpreadsheetPipeline.generate_receipt("tx-123", plan, verification)
    assert receipt.transaction_id == "tx-123"

def test_append_one_row():
    # 1. LOAD WORKBOOK
    fixture = get_fixture()
    wb = SpreadsheetPipeline.load_workbook(fixture)
    
    # 2. UNDERSTAND STRUCTURED REQUEST
    # Append Charlie's data
    req = StructuredRequest(action="APPEND_ROW", sheet_name="Sheet1", value=["3", "Charlie", "88"])
    plan = SpreadsheetPipeline.understand_request(req, wb)
    
    # 3. PLAN MUTATION
    assert len(plan.operations) == 3 # 3 columns to append at row 3 (0-indexed)
    assert plan.operations[0]["row"] == 3
    assert plan.operations[1]["row"] == 3
    assert plan.operations[2]["row"] == 3
    
    # 4. APPLY MUTATION
    SpreadsheetPipeline.apply_mutation(wb, plan)
    assert len(wb["Sheet1"]) == 4 # 3 original rows + 1 appended
    assert wb["Sheet1"][3] == ["3", "Charlie", "88"]
    
    # 5. VERIFY RESULT
    verification = SpreadsheetPipeline.verify_result(wb, plan)
    assert verification.success is True
    
    # 6. GENERATE RECEIPT
    receipt = SpreadsheetPipeline.generate_receipt("tx-124", plan, verification)
    assert receipt.plan.sheet_name == "Sheet1"
