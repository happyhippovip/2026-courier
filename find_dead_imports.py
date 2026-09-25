import ast
import os
import collections

def check_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.append((name.asname or name.name.split('.')[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for name in node.names:
                imports.append((name.asname or name.name, node.lineno))

    if not imports:
        return

    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # rudimentary: if it's not a Name, we skip, this is just a heuristic
            pass

    for imp_name, lineno in imports:
        if imp_name not in used_names and imp_name != "*":
            # Check if it's used in strings (like pytest parametrize)
            if imp_name not in source:
                print(f"{filepath}:{lineno} - Unused import: {imp_name}")

for root, dirs, files in os.walk("scripts"):
    for file in files:
        if file.endswith(".py"):
            check_file(os.path.join(root, file))
for root, dirs, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            check_file(os.path.join(root, file))
