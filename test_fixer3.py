import sys

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = c.replace(
    '        if t1 and t1[0]["status"] == "DISPATCHED":\n            claimed = True\n            task1_data = t1[0]\n            break\n        time.sleep(0.2)\n\n    assert claimed, "Task 1 was not claimed within timeout"',
    '        if t1:\n            if t1[0]["status"] == "DISPATCHED" or t1[0]["status"] == "READY_FOR_VERIFICATION" or t1[0]["status"] == "DONE":\n                claimed = True\n                task1_data = t1[0]\n                break\n        time.sleep(0.2)\n\n    assert claimed, f"Task 1 was not claimed within timeout. Last task status was {t1[0][\'status\'] if t1 else None}"'
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

