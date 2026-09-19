import json
with open("tests/test_courier_continue.py", "r") as f:
    code = f.read()

print("VALIDITY IN TEST:", code.find('"validity":"VALID","producer_id":"test"'))
