"""
test_wakeable_quiescence.py - Acceptance Tests for Wakeable Quiescence (Article 35)
Verifies:
TEST A: 100 duplicate queued replay signals -> exactly 1 logical re-evaluation maximum.
TEST B: After quiescence, send one NEW human 'weiter' -> new bounded re-evaluation occurs.
TEST C: During re-evaluation inject known synthetic safe autonomy gap -> quiescence exits,
        gap selected, work executed, verified, closed, autonomous successor resumes.
TEST D: Remove gap, send another NEW human 'weiter' -> fresh bounded review, 0 real gaps, clean return to quiescence.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.quiescent_absorber import QuiescentQueueAbsorber
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone


class TestWakeableQuiescence(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="wakeable_quiescence_test_")
        self.db_path = os.path.join(self.temp_dir, "control_plane.db")
        self.watermark_file = os.path.join(self.temp_dir, "quiescent_watermark.json")
        self.pm_dir = os.path.join(self.temp_dir, "project-memory", "data")
        os.makedirs(self.pm_dir, exist_ok=True)
        self.backlog_file = os.path.join(self.pm_dir, "safe_backlog.json")

        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump({
                "version": "1.0.0",
                "machine_role": "WINDOWS_PARALLEL_COMMERCIAL",
                "spend_limit_eur": 0.0,
                "verified_real_revenue_eur": 0.0,
                "tasks": []
            }, f, indent=2)

        self.cp = ControlPlane(db_path=self.db_path)
        self.absorber = QuiescentQueueAbsorber(
            watermark_file=self.watermark_file,
            db_path=self.db_path,
            workspace_root=self.temp_dir,
            cp=self.cp
        )
        self.absorber.set_quiescent_watermark(
            state_generation=88,
            status="ACTIVE",
            last_result="NO_REAL_GAP"
        )

    def tearDown(self):
        try:
            self.cp.close()
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # TEST A: 100 duplicate queued replay signals -> 1 logical re-evaluation maximum
    def test_01_test_a_100_duplicate_queued_replay_signals(self):
        """TEST A: 100 queued replay signals collapse into exactly 1 logical review."""
        reviews_before = self.absorber.logical_reviews_count

        # Send 100 duplicate signals in a queue replay
        responses = []
        for i in range(100):
            res = self.absorber.process_signal(signal="weiter", current_state_gen=88)
            responses.append(res)

        reviews_triggered = self.absorber.logical_reviews_count - reviews_before
        self.assertEqual(reviews_triggered, 1, "100 duplicate queued replay signals must produce exactly 1 logical review")
        
        first = responses[0]
        self.assertEqual(first["logical_reviews_triggered"], 1)
        self.assertTrue(first["absorbed"])
        self.assertEqual(first["response_text"], "QUIESCENT_NOOP")

        # The remaining 99 are absorbed as duplicate replays
        replays = responses[1:]
        self.assertEqual(len(replays), 99)
        for r in replays:
            self.assertTrue(r["absorbed"])
            self.assertEqual(r["logical_reviews_triggered"], 0)
            self.assertEqual(r["classification"], "DUPLICATE_CONTINUATION_ALREADY_SATISFIED")
            self.assertEqual(r["response_text"], "QUIESCENT_NOOP")

    # TEST B: After quiescence, send one NEW human 'weiter' -> new bounded review occurs
    def test_02_test_b_new_human_weiter_triggers_review(self):
        """TEST B: Genuinely new human weiter triggers a fresh bounded re-evaluation."""
        # Initial drain of duplicates
        self.absorber.process_signal(signal="weiter", current_state_gen=88)
        initial_reviews = self.absorber.logical_reviews_count

        # A later, genuinely new human weiter arrives
        new_res = self.absorber.process_signal(
            signal="weiter",
            current_state_gen=88,
            external_gen=self.absorber.last_evaluated_signal_generation + 1
        )
        self.assertEqual(new_res["logical_reviews_triggered"], 1)
        self.assertEqual(self.absorber.logical_reviews_count, initial_reviews + 1)
        self.assertEqual(new_res["classification"], "QUIESCENT_NO_REAL_GAP")
        self.assertTrue(new_res["absorbed"])

    # TEST C: During re-evaluation inject known synthetic safe autonomy gap -> exit quiescence & work
    def test_03_test_c_real_gap_wakes_engine(self):
        """TEST C: Injected real safe autonomy gap causes quiescence exit and autonomous task succession."""
        # Inject known synthetic safe gap into backlog
        synthetic_gap = {
            "task_id": "TASK-SYNTHETIC-WAKE-01",
            "title": "Synthetic Safe Autonomy Gap For Wake Verification",
            "goal_id": "GOAL-04",
            "priority": 10.0,
            "status": "PENDING",
            "conflict_scope": "SYNTHETIC_WAKE_SCOPE",
            "expected_real_delta": "AUTONOMY_GAIN",
            "source_evidence": "courier/chief/control_plane.py",
            "script_path": None
        }
        synthetic_successor = {
            "task_id": "TASK-SYNTHETIC-WAKE-02",
            "title": "Synthetic Successor Task",
            "goal_id": "GOAL-04",
            "priority": 9.5,
            "status": "PENDING",
            "conflict_scope": "SYNTHETIC_SUCCESSOR_SCOPE",
            "expected_real_delta": "AUTONOMY_GAIN",
            "source_evidence": "courier/chief/control_plane.py",
            "script_path": None
        }
        with open(self.backlog_file, "r", encoding="utf-8") as f:
            b_data = json.load(f)
        b_data["tasks"] = [synthetic_gap, synthetic_successor]
        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump(b_data, f, indent=2)

        # Send new human weiter
        res = self.absorber.process_signal(
            signal="weiter",
            current_state_gen=88,
            external_gen=self.absorber.last_evaluated_signal_generation + 1
        )
        self.assertFalse(res["absorbed"])
        self.assertEqual(res["classification"], "REAL_GAP_FOUND_QUIESCENCE_EXITED")
        self.assertEqual(res["action"], "EXIT_QUIESCENCE_START_WORK")
        self.assertGreaterEqual(res["gaps_found"], 1)
        self.assertIn("TASK-SYNTHETIC-WAKE-01", res["executed_tasks"])
        self.assertIn("TASK-SYNTHETIC-WAKE-02", res["executed_tasks"])

        # Quiescence is marked WOKEN
        wm = self.absorber.get_watermark()
        self.assertEqual(wm["quiescent_continuation_absorber"], "WOKEN")

    # TEST D: Remove gap, send another NEW human 'weiter' -> clean return to quiescence
    def test_04_test_d_clean_return_to_quiescence(self):
        """TEST D: After gaps resolved, new human weiter runs fresh review and cleanly returns to quiescence."""
        # Empty backlog of pending work
        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump({"tasks": []}, f, indent=2)

        # Send new human weiter
        res = self.absorber.process_signal(
            signal="weiter",
            current_state_gen=88,
            external_gen=self.absorber.last_evaluated_signal_generation + 1
        )
        self.assertTrue(res["absorbed"])
        self.assertEqual(res["classification"], "QUIESCENT_NO_REAL_GAP")
        self.assertEqual(res["action"], "QUIESCENT_NOOP")
        self.assertEqual(res["last_reevaluation_result"], "NO_REAL_GAP")

        # Watermark is back to ACTIVE
        wm = self.absorber.get_watermark()
        self.assertEqual(wm["quiescent_continuation_absorber"], "ACTIVE")
        self.assertEqual(wm["last_reevaluation_result"], "NO_REAL_GAP")


if __name__ == "__main__":
    unittest.main()
