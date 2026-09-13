"""
test_v1_release_candidate.py - Unit & Parity Tests for V1.0.0-RC1 Release Engine
Validates version introspection, health diagnostic engine, CLI integration, and zero developer path leakage.
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from courier.chief.version import (
    __version__, PRODUCT_NAME, RELEASE_TAG, BUILD_DATE, SCHEMA_VERSION,
    get_git_commit, get_version_info
)
from courier.chief.health import run_health_check
from courier.chief.cli import build_parser, cmd_version, cmd_health
from courier.chief.constitution import ConstitutionLoader


class TestV1ReleaseCandidate(unittest.TestCase):
    def test_version_constants(self):
        self.assertEqual(__version__, "1.0.0-rc1")
        self.assertEqual(RELEASE_TAG, "v1.0.0-rc1")
        self.assertEqual(PRODUCT_NAME, "Courier Symphony Windows")
        self.assertEqual(SCHEMA_VERSION, 1)
        self.assertTrue(len(BUILD_DATE) == 10)

    def test_version_info_structure(self):
        info = get_version_info()
        self.assertIn("product_name", info)
        self.assertIn("version", info)
        self.assertIn("git_commit", info)
        self.assertIn("schema_version", info)
        self.assertIn("python_version", info)
        self.assertIn("platform", info)
        self.assertIn("architecture", info)
        self.assertIn("constitution", info)
        self.assertEqual(info["version"], "1.0.0-rc1")

    def test_health_check_live_db(self):
        report = run_health_check()
        self.assertTrue(report["healthy"])
        self.assertEqual(report["status"], "HEALTHY")
        self.assertTrue(report["checks"]["constitution"]["valid"])
        self.assertTrue(report["checks"]["runtime"]["writable"])
        self.assertTrue(report["checks"]["schema"]["compatible"])
        self.assertIn(report["checks"]["database"]["integrity"], ("ok", "NOT_INITIALIZED_YET"))

    def test_health_check_temp_db(self):
        with tempfile.TemporaryDirectory() as td:
            temp_db = os.path.join(td, "test_health.db")
            conn = sqlite3.connect(temp_db)
            c = conn.cursor()
            c.execute("CREATE TABLE quiescent_watermark (quiescent_state_generation INTEGER);")
            c.execute("INSERT INTO quiescent_watermark VALUES (99);")
            conn.commit()
            conn.close()

            report = run_health_check(temp_db)
            self.assertTrue(report["healthy"])
            self.assertEqual(report["checks"]["database"]["state_generation"], 99)
            self.assertEqual(report["checks"]["database"]["integrity"], "ok")

    def test_health_check_corrupt_db(self):
        with tempfile.TemporaryDirectory() as td:
            corrupt_db = os.path.join(td, "corrupt.db")
            with open(corrupt_db, "wb") as f:
                f.write(b"NOT A VALID SQLITE DATABASE HEADER AT ALL")

            report = run_health_check(corrupt_db)
            self.assertFalse(report["healthy"])
            self.assertEqual(report["status"], "UNHEALTHY")

    def test_parser_subcommands(self):
        parser = build_parser()
        args_ver = parser.parse_args(["version"])
        self.assertEqual(args_ver.command, "version")
        self.assertFalse(args_ver.json)

        args_ver_j = parser.parse_args(["version", "--json"])
        self.assertTrue(args_ver_j.json)

        args_h = parser.parse_args(["health"])
        self.assertEqual(args_h.command, "health")
        self.assertFalse(args_h.json)

        args_h_j = parser.parse_args(["health", "--json"])
        self.assertTrue(args_h_j.json)

    def test_zero_developer_paths_in_chief_code(self):
        chief_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chief"))
        forbidden_snippets = [
            r"C:\Users\lol",
            r"C:/Users/lol",
            r"/Users/lol"
        ]
        for root, dirs, files in os.walk(chief_dir):
            if "__pycache__" in root:
                continue
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    for snippet in forbidden_snippets:
                        self.assertNotIn(
                            snippet,
                            content,
                            f"Forbidden developer path '{snippet}' detected in {fname}"
                        )

    def test_self_test_script_execution(self):
        import courier.SELF_TEST as st
        res = st.main()
        self.assertEqual(res, 0)

    def test_dist_archive_integrity(self):
        dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist"))
        zip_path = os.path.join(dist_dir, "courier_symphony_v1.0.0-rc1.zip")
        sha_path = os.path.join(dist_dir, "SHA256SUMS.txt")
        manifest_path = os.path.join(dist_dir, "RELEASE_MANIFEST.json")

        self.assertTrue(os.path.exists(zip_path), "Release archive must exist")
        self.assertTrue(os.path.exists(sha_path), "SHA256SUMS.txt must exist")
        self.assertTrue(os.path.exists(manifest_path), "RELEASE_MANIFEST.json must exist")

        with open(sha_path, "r", encoding="utf-8") as f:
            sha_content = f.read()
        self.assertIn("courier_symphony_v1.0.0-rc1.zip", sha_content)

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["version"], "1.0.0-rc1")
        self.assertEqual(manifest["release_tag"], "v1.0.0-rc1")
        self.assertGreater(len(manifest["files"]), 30)


if __name__ == "__main__":
    unittest.main()
