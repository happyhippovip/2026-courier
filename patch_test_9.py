with open("tests/test_courier_continue.py", "r") as f:
    code = f.read()

# Replace the specific valid evidence string in test_valid_physical_proof_allows_acceptance BACK to missing producer_id
old_str = '"validity":"VALID","producer_id":"test","verifier_id":"test","result_sha256":"0000000000000000000000000000000000000000","reason":"test"'
new_str = '"validity":"VALID","reason":"test"'

code = code.replace(old_str, new_str)

with open("tests/test_courier_continue.py", "w") as f:
    f.write(code)
