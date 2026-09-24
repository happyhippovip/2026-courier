import json
import os
import sys
import tempfile

from scripts.rc_builder import build_release_candidate, main


def test_rc_builder_all_components_ready():
    with tempfile.TemporaryDirectory() as tmp_dir:
        scripts_dir = os.path.join(tmp_dir, "scripts")
        os.makedirs(scripts_dir)

        # Create dummy component files
        for fname in ["first_run.py", "revenue_customer_intake.py", "human_gate_ux.py"]:
            with open(os.path.join(scripts_dir, fname), "w", encoding="utf-8") as f:
                f.write("# dummy\n")

        with open(os.path.join(tmp_dir, "version.txt"), "w", encoding="utf-8") as f:
            f.write("2.1.0\n")

        report = build_release_candidate(repo_dir=tmp_dir, output_dir=tmp_dir)

        assert report["RELEASE_CANDIDATE"] == "PASS"
        assert report["VERSION"] == "2.1.0"
        assert report["CUSTOMER_READY"] == "YES"
        assert report["BLOCKER"] == "NONE"
        assert report["WINDOWS_READY"] is True
        assert report["REVENUE_V1_READY"] is True

        # Check report file was generated
        report_file = os.path.join(tmp_dir, "rc_report.json")
        assert os.path.exists(report_file)
        with open(report_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["RELEASE_CANDIDATE"] == "PASS"


def test_rc_builder_missing_components():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Empty repo
        report = build_release_candidate(repo_dir=tmp_dir, output_dir=tmp_dir)

        assert report["RELEASE_CANDIDATE"] == "BLOCKED"
        assert report["CUSTOMER_READY"] == "NO"
        assert report["BLOCKER"] == "MISSING_COMPONENTS"
        assert report["WINDOWS_READY"] is False
