import re
with open("tests/test_courier_continue.py", "r") as f:
    code = f.read()

old_str = '"validity":"VALID","producer_id":"test","verifier_id":"test","result_sha256":"0000000000000000000000000000000000000000","reason":"test"'
new_str = '"validity":"VALID","producer_id":"producer_1","verifier_id":"verifier_1","result_sha256":"0000000000000000000000000000000000000000","reason":"test"'

code = code.replace(old_str, new_str)

with open("tests/test_courier_continue.py", "w") as f:
    f.write(code)
