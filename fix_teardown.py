import re
with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

# Remove the faulty teardown block from the end of start_server
c = re.sub(
    r"    if config_path\.exists\(\) and 'orig_config' in locals\(\):.*?(?=\n\n\ndef test_tomato_two)",
    "",
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

