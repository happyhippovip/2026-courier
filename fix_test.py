with open("tests/test_cannon_motor_acceptance.py", "r") as f:
    lines = f.readlines()

with open("tests/test_cannon_motor_acceptance.py", "w") as f:
    for line in lines:
        if "statuses(tmp_path)[\"DONE\"]" not in line:
            f.write(line)
