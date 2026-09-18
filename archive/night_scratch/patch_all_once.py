import sys
content = open("tests/test_courier_continue.py").read()

content = content.replace(
'''res = subprocess.run([sys.executable, str(runner)], env=env, capture_output=True, text=True)''',
'''res = subprocess.run([sys.executable, str(runner), "--once"], env=env, capture_output=True, text=True)''')

content = content.replace(
'''res = subprocess.run([sys.executable, str(runner), "--run"], env=env, capture_output=True, text=True)''',
'''res = subprocess.run([sys.executable, str(runner), "--run", "--once"], env=env, capture_output=True, text=True)''')

content = content.replace(
'''res = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "scripts" / "courier_continue.py"), "--run"],''',
'''res = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "scripts" / "courier_continue.py"), "--run", "--once"],''')

open("tests/test_courier_continue.py", "w").write(content)
