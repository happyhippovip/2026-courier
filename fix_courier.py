with open("scripts/courier_continue.py", "r") as f:
    code = f.read()

code = code.replace(
    '                except Exception as e:\n                    pass',
    '                except Exception as e:\n                    print(f"CAUGHT ERROR: {e}"); raise e'
)

with open("scripts/courier_continue.py", "w") as f:
    f.write(code)
