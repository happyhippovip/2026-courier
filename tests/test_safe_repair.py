import json
import os
import sys
import tempfile

from scripts.safe_repair import safe_repair, main


def test_safe_repair_flow():
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = safe_repair(repo_dir=tmp_dir)
        assert "service_repaired" in res
        assert "health_check_ok" in res
        assert "restart_ok" in res
        assert res["restart_ok"] is True


def test_safe_repair_cli(capsys):
    with tempfile.TemporaryDirectory() as tmp_dir:
        orig_argv = sys.argv
        try:
            sys.argv = ["safe_repair.py", "--repo-dir", tmp_dir, "--json"]
            main()
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert data["restart_ok"] is True
        finally:
            sys.argv = orig_argv
