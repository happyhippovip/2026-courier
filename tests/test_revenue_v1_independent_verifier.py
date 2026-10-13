import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import revenue_v1_independent_verifier as ind  # noqa: E402
import revenue_v1_safety_baseline as rvsb  # noqa: E402  (only to produce worker output in tests)

SHA_A = "a" * 40
WORKFLOWS = {
    "ci.yml": "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo ${{ github.event.issue.title }}\n",
    "sub/ci.yml": f"on: [push]\npermissions:\n  contents: read\nconcurrency: g\njobs:\n  t:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    steps:\n      - uses: actions/checkout@{SHA_A}\n",
    "broken.yaml": "jobs:\n  t:\n    runs-on: self-hosted\n   bad: [unclosed\n",
}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


class TestIndependentVerifier(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectory()
        root = Path(self.td.name)
        self.remote = root / "remote"
        self.remote.mkdir()
        git(self.remote, "init", "-q")
        git(self.remote, "config", "core.autocrlf", "false")
        git(self.remote, "config", "uploadpack.allowFilter", "true")
        git(self.remote, "config", "uploadpack.allowAnySHA1InWant", "true")
        for rel, text in WORKFLOWS.items():
            p = self.remote / ".github" / "workflows" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode("utf-8"))  # exact LF bytes on every OS
        (self.remote / "README.md").write_text("x", encoding="utf-8")
        git(self.remote, "add", "-A")
        git(self.remote, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
        self.sha = git(self.remote, "rev-parse", "HEAD")
        self.url = self.remote.as_uri()
        self.work = root / "work"
        self.task = {"target_owner": "o", "target_repo": "r", "target_sha": self.sha, "task_id": "t1",
                     "attempt_id": "a1", "idempotency_key": "k1", "customer_reference": "DEMO"}

    def tearDown(self):
        self.td.cleanup()

    def run_worker(self, tamper=None):
        def fake_clone(owner, repo, sha, dest):
            shutil.copytree(self.remote, dest, ignore=shutil.ignore_patterns(".git"))
            if tamper:
                tamper(dest)
        with patch.object(rvsb, "clone_and_extract", side_effect=fake_clone):
            return rvsb.worker(self.task, self.work)

    def test_pass_on_honest_worker_output(self):
        cand = self.run_worker()
        v = ind.verify(self.task, self.work, cand, self.url)
        self.assertEqual(v["verdict"], "PASS", v["reasons"])
        self.assertTrue(v["accepted"])
        self.assertEqual(v["expected_file_count"], 3)

    def test_reads_raw_blobs_via_git_show_not_worktree(self):
        git_dir = Path(self.td.name) / "g"
        ind.fetch_commit(self.url, self.sha, git_dir)
        self.assertFalse((git_dir / ".github").exists())  # no working tree checkout
        blobs = ind.workflow_blobs(git_dir, self.sha)
        self.assertEqual(set(blobs), set(WORKFLOWS))
        self.assertEqual(blobs["sub/ci.yml"], WORKFLOWS["sub/ci.yml"].encode())

    def test_rejects_manipulated_report_json(self):
        cand = self.run_worker()
        rp = self.work / "report.json"
        report = json.loads(rp.read_text())
        report["findings"] = [f for f in report["findings"] if f["rule"] != "script_injection"]
        rp.write_text(json.dumps(report, indent=2))
        cand["report_json_sha256"] = hashlib.sha256(rp.read_bytes()).hexdigest()  # even with a consistent hash
        v = ind.verify(self.task, self.work, cand, self.url)
        self.assertEqual(v["verdict"], "MISMATCH")
        self.assertFalse(v["accepted"])
        self.assertTrue(any("findings differ" in r for r in v["reasons"]))

    def test_rejects_report_json_hash_tampering(self):
        cand = self.run_worker()
        rp = self.work / "report.json"
        report = json.loads(rp.read_text())
        report["inspected_files"]["ci.yml"] = "0" * 64
        rp.write_text(json.dumps(report, indent=2))
        v = ind.verify(self.task, self.work, cand, self.url)
        self.assertEqual(v["verdict"], "MISMATCH")
        self.assertTrue(any("report_json_sha256" in r for r in v["reasons"]))
        self.assertTrue(any("inspected_files" in r for r in v["reasons"]))

    def test_rejects_manipulated_workflow_file(self):
        # worker analysed a file that differs from git at the SHA (e.g. cleaned up locally)
        def tamper(dest):
            (dest / ".github" / "workflows" / "ci.yml").write_text(
                f"on: push\npermissions: {{}}\nconcurrency: g\njobs:\n  t:\n    runs-on: ubuntu-latest\n    timeout-minutes: 1\n    steps:\n      - uses: actions/checkout@{SHA_A}\n",
                encoding="utf-8")
        cand = self.run_worker(tamper)
        v = ind.verify(self.task, self.work, cand, self.url)
        self.assertEqual(v["verdict"], "MISMATCH")
        self.assertFalse(v["accepted"])
        self.assertTrue(any("inspected_files" in r for r in v["reasons"]))

    def test_missing_report_file_is_fail(self):
        cand = self.run_worker()
        (self.work / "report_de.md").unlink()
        v = ind.verify(self.task, self.work, cand, self.url)
        self.assertEqual(v["verdict"], "FAIL")
        self.assertFalse(v["accepted"])

    def test_exception_is_fail(self):
        cand = self.run_worker()
        bad = dict(self.task, target_sha="f" * 40)  # commit does not exist
        v = ind.verify(bad, self.work, cand, self.url)
        self.assertEqual(v["verdict"], "FAIL")
        v = ind.verify(dict(self.task, target_sha="nope"), self.work, cand, self.url)
        self.assertEqual(v["verdict"], "FAIL")

    def test_wrong_worker_status_is_mismatch(self):
        cand = self.run_worker()
        cand["worker_status"] = "WARN"
        self.assertEqual(ind.verify(self.task, self.work, cand, self.url)["verdict"], "MISMATCH")

    def test_cli_exit_code_nonzero_unless_pass(self):
        cand = self.run_worker()
        cand["task_id"] = "other"
        tp, cp = Path(self.td.name) / "task.json", Path(self.td.name) / "cand.json"
        tp.write_text(json.dumps(self.task)); cp.write_text(json.dumps(cand))
        proc = subprocess.run([sys.executable, str(SCRIPTS / "revenue_v1_independent_verifier.py"), str(tp), str(self.work), str(cp), self.url],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["verdict"], "MISMATCH")

    def test_identity_name_version_sha256(self):
        ident = ind.verifier_identity()
        self.assertEqual(ident["name"], "revenue_v1_independent_verifier.verify")
        self.assertEqual(ident["version"], ind.VERIFIER_VERSION)
        self.assertEqual(ident["source_sha256"], hashlib.sha256((SCRIPTS / "revenue_v1_independent_verifier.py").read_bytes()).hexdigest())

    def _imported_modules(self, source: str) -> list:
        """All module names referenced by Import/ImportFrom (incl. relative), __import__() and importlib calls."""
        import ast
        mods = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative import: never allowed in this standalone module
                    mods.append("." * node.level + (node.module or ""))
                else:
                    mods.append(node.module or "")
                mods += [f"{node.module or ''}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
                if name in ("__import__", "import_module") or (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "importlib"):
                    arg = node.args[0] if node.args else None
                    mods.append(arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else "<dynamic>")
        return mods

    FORBIDDEN = ("revenue_v1_safety_baseline", "revenue_worker", "courier", "intake_dispatcher", "repo_reality_check", "scripts")

    def _assert_clean(self, mods):
        for m in mods:
            self.assertFalse(m.startswith("."), f"relative import {m}")
            self.assertNotEqual(m, "<dynamic>", "dynamic import not allowed")
            for bad in self.FORBIDDEN:
                self.assertNotIn(bad, m.lower(), f"forbidden import {m}")

    def test_module_imports_no_worker_code(self):
        src = (SCRIPTS / "revenue_v1_independent_verifier.py").read_text(encoding="utf-8")
        mods = self._imported_modules(src)
        self.assertIn("yaml", mods)
        self.assertIn("hashlib", mods)
        self._assert_clean(mods)

    def test_import_checker_catches_forbidden_forms(self):
        cases = [
            "import revenue_v1_safety_baseline",
            "from revenue_v1_safety_baseline import worker",
            "from . import revenue_v1_safety_baseline",
            "from .x import y",
            "import courier_core.verification as v",
            "m = __import__('revenue_v1_safety_baseline')",
            "import importlib\nm = importlib.import_module('courier_runtime')",
            "import importlib\nm = importlib.import_module(name)",
        ]
        for code in cases:
            with self.assertRaises(AssertionError, msg=code):
                self._assert_clean(self._imported_modules(code))

if __name__ == "__main__":
    unittest.main()
