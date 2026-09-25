import re
with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = re.sub(
    r"        if orig_keychain_srv:.*?except Exception:.*?pass",
    "",
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)
