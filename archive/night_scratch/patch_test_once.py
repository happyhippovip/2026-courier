import sys
content = open("tests/test_courier_continue.py").read()

content = content.replace(
'''    cmd = [sys.executable, str(script)]
    if run:
        cmd.append("--run")''',
'''    cmd = [sys.executable, str(script)]
    cmd.append("--once")
    if run:
        cmd.append("--run")''')

open("tests/test_courier_continue.py", "w").write(content)
