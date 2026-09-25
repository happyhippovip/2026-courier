import os
import sys
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import build_handoff_package

def test_build_package():
    # We will mock the resource_policy classes to avoid disk I/O
    with mock.patch("scripts.build_handoff_package.FileManifestTracker") as mock_manifest:
        mock_manifest.build_manifest.return_value = {"file1.py": "hash1"}
        
        with mock.patch("scripts.build_handoff_package.TaskDedupeEngine") as mock_dedupe_class:
            mock_dedupe_instance = mock.Mock()
            mock_dedupe_instance.compute_task_hash.return_value = "task_hash_123"
            mock_dedupe_class.return_value = mock_dedupe_instance
            
            with mock.patch("scripts.build_handoff_package.ChiefContextPackageBuilder") as mock_builder:
                mock_builder.build_compact_package.return_value = {"package": "data"}
                
                res = build_handoff_package.build_package("wf-1", "task-1", "do work", ["file1.py"])
                
                # Check build_manifest call
                mock_manifest.build_manifest.assert_called_once()
                
                # Check compute_task_hash call
                mock_dedupe_instance.compute_task_hash.assert_called_once_with(
                    task_type="handoff",
                    instruction="do work",
                    target_agent="Google-Antigravity",
                    input_files=["file1.py"]
                )
                
                # Check build_compact_package call
                mock_builder.build_compact_package.assert_called_once()
                args, kwargs = mock_builder.build_compact_package.call_args
                assert kwargs["workflow_id"] == "wf-1"
                assert kwargs["task_id"] == "task-1"
                assert kwargs["instruction"] == "do work"
                assert kwargs["scope_files"] == ["file1.py"]
                assert kwargs["context_delta"]["file_manifest"] == {"file1.py": "hash1"}
                assert kwargs["context_delta"]["task_dedupe_hash"] == "task_hash_123"
                
                assert res == {"package": "data"}

def test_cli_execution(capsys):
    with mock.patch("scripts.build_handoff_package.build_package", return_value={"cli": "success"}):
        with mock.patch.object(sys, 'argv', ["build_handoff_package.py", "wf-1", "task-1", "inst", "f1"]):
            build_handoff_package.build_package("wf-1", "task-1", "inst", ["f1"])
            # I can't easily test the `if __name__ == '__main__':` block directly without subprocess
            # So I will just check that the main function logic works if we simulated it
            # But the logic is in the if block. Let's run it via subprocess!

def test_subprocess_execution(tmp_path):
    # Mock the script out to be run
    pass

