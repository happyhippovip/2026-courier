import ast
from pathlib import Path

def test_server_infinite_retry_fixed():
    """
    PROVE: server/app.py task_result() transitions to FAILED_TERMINAL 
    on MAX_RETRIES instead of resetting retry_state to 0.
    """
    source = Path("server/app.py").read_text()
    tree = ast.parse(source)
    
    found_failed_terminal = False
    found_zero_reset = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "task_result":
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Subscript):
                            if isinstance(target.value, ast.Name) and target.value.id == "retry_state":
                                if isinstance(target.slice, ast.Constant) and target.slice.value == "execution":
                                    if isinstance(child.value, ast.Constant) and child.value.value == 0:
                                        found_zero_reset = True
                
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name) and child.func.id == "set_task_status":
                        if len(child.args) == 2 and isinstance(child.args[1], ast.Constant) and child.args[1].value == "FAILED_TERMINAL":
                            found_failed_terminal = True

    assert not found_zero_reset, "Server must not reset execution retry_state to 0 on max retries!"
    assert found_failed_terminal, "Server must transition to FAILED_TERMINAL on max retries!"

