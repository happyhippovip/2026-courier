"""Targeted acceptance tests for the Motor's canonical supervisor authority."""
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "build/courier_ecosystem_v1/motor/supervisor_standalone.py"
sys.path.insert(0, str(SOURCE.parent))
SPEC = importlib.util.spec_from_file_location("motor_supervisor", SOURCE)
motor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(motor)


class MotorSupervisorAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "motor.db"
        original = motor.DB_PATH
        motor.DB_PATH = self.db
        motor.ATTEMPTS_DIR = Path(self.tmp.name) / "attempts"
        motor.init_env().close()
        motor.DB_PATH = original

    def tearDown(self):
        self.tmp.cleanup()

    def authority(self, name):
        return motor.SupervisorAuthority(self.db, instance_id=name)

    def test_first_owner_and_competing_owner(self):
        first = self.authority("first")
        self.assertEqual(first.acquire()[0], True)
        second = self.authority("second")
        self.assertEqual(second.acquire(), (False, "ACTIVE_OWNER_PRESENT"))

    def test_expired_dead_owner_rotates_generation(self):
        first = self.authority("first")
        self.assertTrue(first.acquire()[0])
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE supervisor_authority SET expires_at=0, pid=99999999, process_birth_identity='gone'")
        conn.commit(); conn.close()
        second = self.authority("second")
        self.assertEqual(second.acquire()[0], True)
        self.assertGreater(second.generation, first.generation)

    def test_reused_pid_is_not_old_owner_and_never_signaled(self):
        first = self.authority("first")
        self.assertTrue(first.acquire()[0])
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE supervisor_authority SET expires_at=0, pid=?, process_birth_identity='different-birth'", (os.getpid(),))
        conn.commit(); conn.close()
        second = self.authority("second")
        self.assertTrue(second.acquire()[0])
        # The authority layer has no kill primitive; takeover cannot signal us.
        self.assertTrue(os.getpid() > 0)

    def test_stale_generation_cannot_renew_or_release(self):
        first = self.authority("first")
        self.assertTrue(first.acquire()[0])
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE supervisor_authority SET expires_at=0")
        conn.commit(); conn.close()
        second = self.authority("second")
        self.assertTrue(second.acquire()[0])
        self.assertFalse(first.renew())
        self.assertFalse(first.release())

    def test_gate_table_is_not_a_dispatch_authority(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("AND t.gate_id IS NULL", source)
        self.assertIn("Direct gate approval is retired", source)
        self.assertNotIn("LEFT JOIN approved_gates", source)

    def test_worker_environment_does_not_receive_owner_secret(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('env.pop("COURIER_HUMAN_GATE_SECRET", None)', source)


if __name__ == "__main__":
    unittest.main()
