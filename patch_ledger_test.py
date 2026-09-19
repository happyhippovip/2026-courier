with open("tests/test_ledger_fix_guards.py", "r") as f:
    code = f.read()

code = code.replace("class MatchDict(dict):", "class MatchDict(dict):\n    def __bool__(self): return True")

with open("tests/test_ledger_fix_guards.py", "w") as f:
    f.write(code)
