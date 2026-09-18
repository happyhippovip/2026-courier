import ast
from pathlib import Path

def test_motor_exception_swallow_fixed():
    """
    PROVE: The motor loop no longer swallows exceptions silently.
    It must call update_ledger when a future raises an exception.
    """
    source = Path("scripts/courier_continue.py").read_text()
    tree = ast.parse(source)
    
    found_catch = False
    found_update_ledger = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            for child in ast.walk(node):
                if isinstance(child, ast.ExceptHandler):
                    # check if update_ledger is called inside this exception handler
                    for stmt in ast.walk(child):
                        if isinstance(stmt, ast.Call):
                            if isinstance(stmt.func, ast.Name) and stmt.func.id == "update_ledger":
                                found_update_ledger = True
                    found_catch = True
                    
    assert found_catch, "Motor must catch exceptions"
    assert found_update_ledger, "Motor must call update_ledger when an exception is caught to avoid infinite wedge"

