import sys

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'bad_rec["UNPROVEN_EDGES"] = ["POST-PILOT HARDENING"]\n        validate_record(bad_rec, allow_unknown_sha=False)',
    'bad_rec["NEXT_EXECUTABLE_ACTION"] = "NONE"\n        bad_rec["UNPROVEN_EDGES"] = ["POST-PILOT HARDENING"]\n        validate_record(bad_rec, allow_unknown_sha=False)'
)

# wait, there's another check right below it: Invariant 2
content = content.replace(
    'bad_rec2["UNPROVEN_EDGES"] = []\n        bad_rec2["NEXT_EXECUTABLE_ACTION"] = "SOME_ACTION"\n        validate_record(bad_rec2, allow_unknown_sha=False)',
    'bad_rec2["UNPROVEN_EDGES"] = []\n        bad_rec2["NEXT_EXECUTABLE_ACTION"] = "SOME_ACTION"\n        validate_record(bad_rec2, allow_unknown_sha=False)'
)
open("tests/test_tomato_two_torture.py", "w").write(content)
