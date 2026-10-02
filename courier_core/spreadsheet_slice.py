from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
import copy

@dataclass(frozen=True)
class StructuredRequest:
    action: str  # "UPDATE_CELL" or "APPEND_ROW"
    sheet_name: str
    target_coord: str = None # e.g., "B2"
    value: Any = None        # e.g., "42" or ["Data1", "Data2"]

@dataclass(frozen=True)
class MutationPlan:
    sheet_name: str
    operations: List[Dict[str, Any]] # [{"row": int, "col": int, "value": Any}]

@dataclass(frozen=True)
class VerificationResult:
    success: bool
    verified_operations: int

@dataclass(frozen=True)
class SpreadsheetReceipt:
    transaction_id: str
    plan: MutationPlan
    verification: VerificationResult

def _parse_coord(coord: str) -> Tuple[int, int]:
    """Converts 'B2' -> (1, 1). Only supports A-Z for simplicity in this slice."""
    col_char = coord[0].upper()
    row_str = coord[1:]
    col_idx = ord(col_char) - ord('A')
    row_idx = int(row_str) - 1
    return row_idx, col_idx

class SpreadsheetPipeline:
    """
    Vertical slice for isolated, deterministic spreadsheet mutations.
    LOAD -> UNDERSTAND -> PLAN -> APPLY -> VERIFY -> RECEIPT
    """

    @staticmethod
    def load_workbook(fixture: Dict[str, List[List[str]]]) -> Dict[str, List[List[str]]]:
        """LOAD WORKBOOK: Deep copy to simulate loading into memory."""
        return copy.deepcopy(fixture)

    @staticmethod
    def understand_request(request: StructuredRequest, workbook: Dict[str, List[List[str]]]) -> MutationPlan:
        """UNDERSTAND STRUCTURED REQUEST & PLAN MUTATION"""
        ops = []
        if request.action == "UPDATE_CELL":
            row_idx, col_idx = _parse_coord(request.target_coord)
            ops.append({"row": row_idx, "col": col_idx, "value": request.value})
            
        elif request.action == "APPEND_ROW":
            sheet = workbook.get(request.sheet_name, [])
            row_idx = len(sheet) # Append at the end
            for col_idx, val in enumerate(request.value):
                ops.append({"row": row_idx, "col": col_idx, "value": val})
                
        else:
            raise ValueError(f"Unknown action: {request.action}")
            
        return MutationPlan(sheet_name=request.sheet_name, operations=ops)

    @staticmethod
    def apply_mutation(workbook: Dict[str, List[List[str]]], plan: MutationPlan) -> None:
        """APPLY MUTATION in-place to the workbook representation."""
        if plan.sheet_name not in workbook:
            workbook[plan.sheet_name] = []
            
        sheet = workbook[plan.sheet_name]
        
        for op in plan.operations:
            r, c, v = op["row"], op["col"], op["value"]
            
            # Pad rows
            while len(sheet) <= r:
                sheet.append([])
            # Pad cols
            while len(sheet[r]) <= c:
                sheet[r].append("")
                
            sheet[r][c] = str(v)

    @staticmethod
    def verify_result(workbook: Dict[str, List[List[str]]], plan: MutationPlan) -> VerificationResult:
        """VERIFY RESULT: Ensure operations were written correctly."""
        sheet = workbook.get(plan.sheet_name, [])
        success_count = 0
        
        for op in plan.operations:
            r, c, expected = op["row"], op["col"], str(op["value"])
            try:
                actual = sheet[r][c]
                if actual == expected:
                    success_count += 1
                else:
                    return VerificationResult(success=False, verified_operations=success_count)
            except IndexError:
                return VerificationResult(success=False, verified_operations=success_count)
                
        return VerificationResult(success=True, verified_operations=success_count)

    @staticmethod
    def generate_receipt(transaction_id: str, plan: MutationPlan, verification: VerificationResult) -> SpreadsheetReceipt:
        """GENERATE RECEIPT"""
        return SpreadsheetReceipt(
            transaction_id=transaction_id,
            plan=plan,
            verification=verification
        )
