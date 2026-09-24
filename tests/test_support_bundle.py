import json
import os
import sys
import tempfile
import zipfile

from scripts.support_bundle import get_system_health, create_support_bundle, main


def test_get_system_health():
    health = get_system_health()
    assert "os" in health
    assert "platform" in health
    assert "python_version" in health
    assert "disk_free_gb" in health
    assert health["disk_free_gb"] != "N/A"
    assert isinstance(health["disk_free_gb"], (int, float))


def test_create_support_bundle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = os.path.join(tmp_dir, "repo")
        output_dir = os.path.join(tmp_dir, "output")
        os.makedirs(repo_dir)

        # Create dummy central_state.json
        state_file = os.path.join(repo_dir, "central_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"goals": {"G1": "done"}, "tasks": {"T1": "done"}, "status": "IDLE"}, f)

        # Create dummy version.txt
        version_file = os.path.join(repo_dir, "version.txt")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write("1.2.3-test\n")

        bundle_path = create_support_bundle(repo_dir=repo_dir, output_dir=output_dir)
        assert os.path.exists(bundle_path)
        assert bundle_path.endswith(".zip")

        # Inspect zip contents
        with zipfile.ZipFile(bundle_path, "r") as zf:
            names = zf.namelist()
            assert "health.json" in names
            assert "queue_summary.json" in names
            assert "version.txt" in names

            health_data = json.loads(zf.read("health.json").decode("utf-8"))
            assert "disk_free_gb" in health_data

            queue_data = json.loads(zf.read("queue_summary.json").decode("utf-8"))
            assert queue_data["queue_summary"]["total_goals"] == 1
            assert queue_data["queue_summary"]["total_tasks"] == 1

            version_data = zf.read("version.txt").decode("utf-8")
            assert "1.2.3-test" in version_data


def test_support_bundle_cli(capsys):
    with tempfile.TemporaryDirectory() as tmp_dir:
        orig_argv = sys.argv
        try:
            sys.argv = ["support_bundle.py", "--repo-dir", tmp_dir, "--output-dir", tmp_dir]
            main()
            captured = capsys.readouterr()
            assert "Support bundle created:" in captured.out
        finally:
            sys.argv = orig_argv
