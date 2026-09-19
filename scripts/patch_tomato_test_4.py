import re

with open("tests/test_tomato_two_torture.py", "r") as f:
    code = f.read()

# We need to change env["COURIER_API_KEY"] = "local-dev-key-123" to the real key
code = code.replace('env["COURIER_API_KEY"] = "local-dev-key-123"', 'env["COURIER_API_KEY"] = "321606503a874d39b50f6137e3321b7f"')

# Also remove the new_config["COURIER_API_KEY"] injection
code = code.replace('new_config["COURIER_API_KEY"] = "local-dev-key-123"\n', '')

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(code)
print("Patched 4.")
