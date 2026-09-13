"""
test_queue_collapse.py - Test suite for WINDOWS COURIER P0 QUEUE COLLAPSE & STALE weiter SUPPRESSION
Certifies:
- Queue Storm Test: 100 equivalent continuations -> exactly 1 logical continuation intent (TASKS_DUPLICATED = 0)
- In-Flight Test: Task RUNNING + 50 continuations -> all 50 coalesced, 0 duplicate tasks
- Post-Verification Stale Test: Verified task + old continuation -> no replay, advances generation
- Genuine New Human Goal Preservation: Non-bare instructions are preserved and not dropped
- Monotonic State Generation: Generation increments upon verification, dropping stale references
- Full Queue Observability Metrics
"""

import os
import sys
import shutil
import tempfile
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.queue_coalescer import QueueCoalescer

class TestQueueCollapse(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_queue_collapse_")
        self.db_path = os.path.join(self.test_dir, "test_control_plane.db")
        self.state_file = os.path.join(self.test_dir, "coalescer_state.json")
        self.coalescer = QueueCoalescer(db_path=self.db_path, state_file=self.state_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_queue_storm_100_continuations_produce_one_intent(self):
        """Queue Storm Test: 100 duplicate continuations produce at most 1 logical intent."""
        messages = ["weiter"] * 100
        burst_res = self.coalescer.process_queue_burst(messages, active_task_status="IDLE")

        self.assertEqual(burst_res["total_messages_processed"], 100)
        self.assertEqual(burst_res["logical_continuation_intents_created"], 1)
        self.assertEqual(burst_res["continuations_coalesced"], 99)
        self.assertEqual(burst_res["duplicate_tasks_created"], 0)
        self.assertEqual(burst_res["verified_tasks_replayed"], 0)

        metrics = self.coalescer.get_metrics()
        self.assertEqual(metrics["raw_continuation_events_received"], 100)
        self.assertEqual(metrics["continuations_coalesced"], 99)
        self.assertEqual(metrics["logical_continuation_intents"], 1)
        self.assertEqual(metrics["duplicate_tasks_prevented"], 99)

    def test_02_in_flight_task_coalesces_all_incoming(self):
        """In-Flight Test: Task RUNNING + 50 'weiter' -> 100% coalesced, 0 new intents."""
        messages = ["weiter\n", "WEITER", "  weiter  "] * 17  # 51 messages
        burst_res = self.coalescer.process_queue_burst(
            messages,
            active_task_status="RUNNING",
            active_task_id="TASK-WIN-64"
        )

        self.assertEqual(burst_res["logical_continuation_intents_created"], 0)
        self.assertEqual(burst_res["continuations_coalesced"], 51)
        self.assertEqual(burst_res["duplicate_tasks_created"], 0)

    def test_03_post_verification_stale_dropped_and_generation_advanced(self):
        """Post-Verification: Task verified -> generation advances, old generation dropped."""
        # 1. Start generation 1 and complete task
        gen1 = self.coalescer.get_metrics()["current_state_generation"]
        self.assertEqual(gen1, 1)

        # Advance to generation 2
        gen2 = self.coalescer.advance_state_generation("TASK-WIN-63")
        self.assertEqual(gen2, 2)

        # Stale continuation from generation 1 arrives
        is_stale = self.coalescer.handle_stale_continuation_check(incoming_generation=1)
        self.assertTrue(is_stale)

        metrics = self.coalescer.get_metrics()
        self.assertEqual(metrics["stale_continuations_dropped"], 1)
        self.assertEqual(metrics["duplicate_tasks_prevented"], 1)

    def test_04_genuine_new_human_goal_preserved(self):
        """Non-bare human goal instructions are preserved and not coalesced as bare noise."""
        raw_msg = "weiter und prüfe danach Windows packaging"
        res = self.coalescer.process_raw_input(raw_msg, active_task_status="RUNNING")

        self.assertEqual(res["decision"], "PRESERVE_NEW_GOAL")
        self.assertTrue(res["is_new_goal"])
        self.assertEqual(res["extracted_goal"], raw_msg)
        self.assertEqual(res["duplicate_tasks_created"], 0)

    def test_05_observability_report_schema(self):
        """Observability report contains all required metrics."""
        self.coalescer.process_raw_input("weiter", active_task_status="IDLE")
        rep = self.coalescer.get_observability_report(current_task="TASK-WIN-64", current_goal="GOAL-05")

        self.assertIn("RAW_CONTINUATION_EVENTS_RECEIVED", rep)
        self.assertIn("CONTINUATIONS_COALESCED", rep)
        self.assertIn("STALE_CONTINUATIONS_DROPPED", rep)
        self.assertIn("LOGICAL_CONTINUATION_INTENTS", rep)
        self.assertIn("DUPLICATE_TASKS_PREVENTED", rep)
        self.assertIn("VERIFIED_TASKS_REPLAYED", rep)
        self.assertIn("CURRENT_STATE_GENERATION", rep)
        self.assertIn("CURRENT_TASK", rep)
        self.assertIn("CURRENT_GOAL", rep)
        self.assertEqual(rep["VERIFIED_TASKS_REPLAYED"], 0)

if __name__ == "__main__":
    unittest.main()
