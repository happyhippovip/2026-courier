import os
import ast
import json
from pathlib import Path

class ResultCustoms:
    """
    Courier Result Customs: A standalone validation framework to catch agent hallucinations
    and verify artifacts before committing them to your task queue.
    """

    @staticmethod
    def verify_file_exists(filepath):
        if not Path(filepath).exists():
            return False, f"Artifact missing: {filepath}"
        return True, "File exists."

    @staticmethod
    def verify_valid_python_ast(filepath):
        try:
            content = Path(filepath).read_text()
            ast.parse(content)
            return True, "Valid Python AST."
        except SyntaxError as e:
            return False, f"Syntax Error in {filepath}: {e}"
        except FileNotFoundError:
            return False, f"Artifact missing: {filepath}"

    @staticmethod
    def verify_valid_json(filepath):
        try:
            content = Path(filepath).read_text()
            json.loads(content)
            return True, "Valid JSON."
        except json.JSONDecodeError as e:
            return False, f"JSON Error in {filepath}: {e}"
        except FileNotFoundError:
            return False, f"Artifact missing: {filepath}"

    @staticmethod
    def verify_content_regex(filepath, pattern):
        try:
            import re
            content = Path(filepath).read_text()
            if re.search(pattern, content):
                return True, f"Regex match found for {pattern}"
            return False, f"Regex match NOT found for {pattern}"
        except FileNotFoundError:
            return False, f"Artifact missing: {filepath}"

if __name__ == "__main__":
    # Self-test
    Path("test_valid.py").write_text("print('hello')")
    Path("test_invalid.py").write_text("print('hello'")

    success_val, msg1 = ResultCustoms.verify_valid_python_ast("test_valid.py")
    fail_val, msg2 = ResultCustoms.verify_valid_python_ast("test_invalid.py")

    Path("test_valid.py").unlink()
    Path("test_invalid.py").unlink()

    if success_val and not fail_val:
        print("CUSTOMS_FRAMEWORK_VERIFIED")
    else:
        print(f"FAILED: {msg1} | {msg2}")
        import sys
        sys.exit(1)
WORKSPACE = Path.cwd()
