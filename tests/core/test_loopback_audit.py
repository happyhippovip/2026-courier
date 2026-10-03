import ast
import os
from pathlib import Path

def test_no_wildcard_bindings():
    """WK-10: Search every runtime server/bind call reachable from V1. Verify 127.0.0.1/loopback-only semantics."""
    
    root_dir = Path(__file__).parent.parent.parent
    
    python_files = []
    for d in ["courier_core", "courier_hub", "courier_worker"]:
        python_files.extend((root_dir / d).rglob("*.py"))
        
    for py_file in python_files:
        content = py_file.read_text()
        
        # Simple string-level checks for wildcard IP
        assert "0.0.0.0" not in content, f"Wildcard binding '0.0.0.0' found in {py_file}!"
        
        # AST-level checks for bind() or server initialization calls
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for bind(('...', port)) or super().__init__(('...', port))
                args = None
                
                if isinstance(node.func, ast.Attribute) and node.func.attr == "bind":
                    args = node.args
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "__init__":
                    args = node.args
                elif isinstance(node.func, ast.Name) and node.func.id == "HTTPServer":
                    args = node.args
                    
                if args:
                    for arg in args:
                        # Find a tuple arg which might be (host, port)
                        if isinstance(arg, ast.Tuple) and len(arg.elts) == 2:
                            host_expr = arg.elts[0]
                            if isinstance(host_expr, ast.Constant) and isinstance(host_expr.value, str):
                                host = host_expr.value
                                assert host in ("127.0.0.1", "localhost", "::1"), \
                                    f"Unsafe binding address '{host}' used in {py_file}! Must be loopback-only."
                                
