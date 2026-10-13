"""Release gate for the static Courier preview."""

import subprocess
import sys
from pathlib import Path


def test_website_release_gate():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "website" / "check_site.py")],
        cwd=root,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
