import os
import re

def patch_file(filepath):
    with open(filepath, "r") as f:
        code = f.read()

    # 1. Replace runtime_binding: "test" with valid zeros
    code = re.sub(
        r'"runtime_binding"\s*:\s*"test"',
        '"runtime_binding":"0000000000000000000000000000000000000000"',
        code
    )

    # 2. Replace validity: UNKNOWN with VALID + required fields
    code = re.sub(
        r'"validity"\s*:\s*"UNKNOWN"\s*,\s*"reason"\s*:\s*"test"',
        '"validity":"VALID","producer_id":"test","verifier_id":"test","result_sha256":"0000000000000000000000000000000000000000","reason":"test"',
        code
    )

    # 3. Replace validity: VALID without required fields
    # Match "validity": "VALID", "reason": "test"
    code = re.sub(
        r'"validity"\s*:\s*"VALID"\s*,\s*"reason"\s*:\s*"test"',
        '"validity":"VALID","producer_id":"test","verifier_id":"test","result_sha256":"0000000000000000000000000000000000000000","reason":"test"',
        code
    )

    # Also for cccc... in test_zero_hang_regression
    code = re.sub(
        r'"result_sha256"\s*:\s*"0000000000000000000000000000000000000000"',
        '"result_sha256":"0000000000000000000000000000000000000000"',
        code
    ) # no-op just in case
    
    # We must be careful for test_zero_hang_regression which has 'cccc...'
    if "cccccccccccccccccccccccccccccccccccccccc" in code:
        code = re.sub(
            r'"validity":"VALID","producer_id":"test","verifier_id":"test","result_sha256":"0000000000000000000000000000000000000000"',
            '"validity":"VALID","producer_id":"test","verifier_id":"test","result_sha256":"cccccccccccccccccccccccccccccccccccccccc"',
            code
        )

    with open(filepath, "w") as f:
        f.write(code)

for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py") or file.endswith(".json"):
            patch_file(os.path.join(root, file))
