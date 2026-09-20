import sys

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'bad_rec["UNPROVEN_EDGES"] = []\n        bad_rec["STATUS"] = "READY"',
    'bad_rec["NEXT_EXECUTABLE_ACTION"] = "NONE"\n        bad_rec["UNPROVEN_EDGES"] = []\n        bad_rec["STATUS"] = "READY"'
).replace(
    'bad_rec["STATUS"] = "DONE"\n        bad_rec["NEXT_EXECUTABLE_ACTION"] = "SOME_ACTION"',
    'bad_rec["UNPROVEN_EDGES"] = []\n        bad_rec["STATUS"] = "DONE"\n        bad_rec["NEXT_EXECUTABLE_ACTION"] = "SOME_ACTION"'
)
open("tests/test_tomato_two_torture.py", "w").write(content)
