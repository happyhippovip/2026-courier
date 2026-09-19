import re
with open("tests/test_zero_hang_regression.py") as f:
    text = f.read()

text = text.replace("""    res = subprocess.run(
        [sys.executable, str(repo_dir / "scripts" / "courier_continue.py"), "--run"],
        env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="main", MOCK_SHA="cccccccccccccccccccccccccccccccccccccccc"),
        capture_output=True, text=True, cwd=str(repo_dir), timeout=25
    )""", """    try:
        res = subprocess.run(
            [sys.executable, str(repo_dir / "scripts" / "courier_continue.py"), "--run"],
            env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="main", MOCK_SHA="cccccccccccccccccccccccccccccccccccccccc"),
            capture_output=True, text=True, cwd=str(repo_dir), timeout=25
        )
    except subprocess.TimeoutExpired as e:
        with open("/tmp/real_stdout.txt", "w") as f:
            f.write(e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
        raise e""")
with open("tests/test_zero_hang_regression.py", "w") as f:
    f.write(text)
