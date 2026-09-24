import os
import sys
import tempfile

from scripts.first_run import main


def test_first_run_no_delay(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create .env.txt with credentials
        env_file = os.path.join(tmp_dir, ".env.txt")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("COURIER_API_KEY=test-first-run-key\n")

        orig_argv = sys.argv
        try:
            sys.argv = ["first_run.py", "--repo-dir", tmp_dir, "--no-delay"]
            main()
            captured = capsys.readouterr()
            assert "Courier First-Run Experience" in captured.out
            assert "Verifying Installation..." in captured.out
            assert "Credentials connected." in captured.out
            assert "Goal successfully achieved." in captured.out
        finally:
            sys.argv = orig_argv
