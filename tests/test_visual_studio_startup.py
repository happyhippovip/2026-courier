from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

import scripts.run_visual_studio_server as rvss


REPO_ROOT = Path(__file__).resolve().parents[1]


class VisualStudioStartupTests(unittest.TestCase):
    def test_cockpit_imports_without_optional_enrichment_modules(self):
        result = subprocess.run(
            [sys.executable, "-c", "import scripts.run_visual_studio_server"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_read_courier_ledger_truth(self):
        truth = rvss.read_courier_ledger_truth()
        self.assertIn("revision", truth)
        self.assertIn("status", truth)
        self.assertIn("clean_idle", truth)
        self.assertIn("unproven_count", truth)
        self.assertIn("next_action", truth)

    def test_save_and_load_json_safe(self, tmp_path: Path | None = None):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "subdir" / "state.json"
            data = {"key": "value", "count": 42}
            rvss.save_json_safe(target, data)
            self.assertTrue(target.exists())

            loaded = rvss.load_json_safe(target)
            self.assertEqual(loaded, data)

            nonexistent = Path(td) / "nonexistent.json"
            self.assertEqual(rvss.load_json_safe(nonexistent), {})

    def test_find_active_human_gate_provenance(self):
        # 1. Complete provenance
        agents_complete = {
            "agent-1": {
                "id": "agent-1",
                "state": "BLOCKED_HUMAN_GATE",
                "workflow": "wf-123",
                "correlation_id": "corr-456",
                "task": "task-789",
            }
        }
        gate1 = rvss.find_active_human_gate(agents_complete)
        self.assertIsNotNone(gate1)
        self.assertEqual(gate1["workflow_id"], "wf-123")
        self.assertEqual(gate1["correlation_id"], "corr-456")
        self.assertTrue(gate1["provenance_complete"])

        # 2. Incomplete provenance (missing correlation_id)
        agents_incomplete = {
            "agent-2": {
                "id": "agent-2",
                "state": "BLOCKED_HUMAN_GATE",
                "workflow": "wf-123",
            }
        }
        gate2 = rvss.find_active_human_gate(agents_incomplete)
        self.assertIsNotNone(gate2)
        self.assertFalse(gate2["provenance_complete"])

        # 3. No active gate
        agents_idle = {
            "agent-3": {
                "id": "agent-3",
                "state": "IDLE",
            }
        }
        self.assertIsNone(rvss.find_active_human_gate(agents_idle))

    def test_resolve_active_gate_decision(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            dec_dir = Path(td) / "decisions"
            app_dir = Path(td) / "approvals"
            dec_dir.mkdir(parents=True)
            app_dir.mkdir(parents=True)

            gate = {
                "workflow_id": "wf-1",
                "correlation_id": "corr-1",
                "provenance_complete": True,
            }

            # No decision yet
            res1 = rvss.resolve_active_gate_decision(gate, dec_dir, app_dir)
            self.assertEqual(res1["status"], "NO_DECISION")

            # Add approval file
            app_file = app_dir / "approval-1.json"
            app_file.write_text(
                json.dumps({
                    "workflow_id": "wf-1",
                    "correlation_id": "corr-1",
                    "action": "APPROVED",
                }),
                encoding="utf-8",
            )

            res2 = rvss.resolve_active_gate_decision(gate, dec_dir, app_dir)
            self.assertEqual(res2["status"], "APPROVED")
            self.assertEqual(res2["source"], "HUMAN_APPROVAL")

    def test_main_cli_check_config(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = rvss.main(["--check-config", "--port", "8099", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["status"], "CONFIG_VALID")
        self.assertEqual(data["port"], 8099)


if __name__ == "__main__":
    unittest.main()
