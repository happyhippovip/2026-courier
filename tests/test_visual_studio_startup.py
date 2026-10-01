import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class VisualStudioStartupTests(unittest.TestCase):
    def test_cockpit_imports_without_optional_enrichment_modules(self):
        result = subprocess.run(
            [sys.executable, "-c", "import scripts.run_visual_studio_server"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
