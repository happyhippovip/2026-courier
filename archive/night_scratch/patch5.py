import sys

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'cwd=str(REPO_ROOT))',
    'cwd=str(Path.home() / ".courier_runtime"))'
)

# wait, I need to make sure the server path is absolute if it's changing cwd!
# scripts/courier_verifier.py relative to ~/.courier_runtime would be WRONG!
# The verifier script is at REPO_ROOT/scripts/courier_verifier.py.
content = content.replace(
    '[python_exe, "scripts/courier_verifier.py"]',
    '[python_exe, str(REPO_ROOT / "scripts/courier_verifier.py")]'
)

open("tests/test_tomato_two_torture.py", "w").write(content)
