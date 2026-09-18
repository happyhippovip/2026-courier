import sys
content = open("tests/test_antigravity_continuous.py").read()

content = content.replace(
'''res = subprocess.run([sys.executable, str(runner), "--run"], env=env, capture_output=True, text=True)''',
'''res = subprocess.run([sys.executable, str(runner), "--run", "--once"], env=env, capture_output=True, text=True)''')

open("tests/test_antigravity_continuous.py", "w").write(content)
