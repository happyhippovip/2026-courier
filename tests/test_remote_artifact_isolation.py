import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from remote_artifact_isolation import AtomicArtifactStore, ArtifactLifecycleError, RemoteLifecycleError, RemoteLifecycleLedger


class RemoteArtifactIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "heavy_jobs.sqlite3"
        self.remote = RemoteLifecycleLedger(self.ledger)
        self.artifacts = AtomicArtifactStore(self.ledger)

    def tearDown(self):
        self.tmp.cleanup()

    def test_remote_normal_completion_binds_result(self):
        self.remote.start("task", 1, "g1", "remote-1", "approved-target", "allowed", "effect")
        self.remote.reconcile("task", 1, "g1", "COMPLETED", "effect")
        self.remote.accept_result("task", 1, "g1", "result")

    def test_client_loss_is_unknown_and_cannot_retry(self):
        self.remote.start("task", 1, "g1", "remote-1", "approved-target", "allowed", "effect")
        self.remote.connection_lost("task", 1, "g1")
        self.assertFalse(self.remote.retry_allowed("task", 1, "g1"))

    def test_late_generation_and_ambiguous_remote_id_are_quarantined(self):
        with self.assertRaisesRegex(RemoteLifecycleError, "AMBIGUOUS"):
            self.remote.start("task", 1, "g1", "", "target", "cmd", "effect")
        with self.assertRaisesRegex(RemoteLifecycleError, "LATE"):
            self.remote.accept_result("task", 2, "old-generation", "late")

    def test_partial_artifact_never_becomes_final_and_stale_temp_preserves(self):
        final = Path(self.tmp.name) / "result.bin"
        temp = self.artifacts.write(final, "task", 1, b"partial")
        self.assertTrue(temp.exists())
        self.assertFalse(final.exists())
        self.assertEqual(self.artifacts.reconcile_temp(final, "task", 1), "STALE_TEMP_PRESERVED_QUARANTINED")

    def test_artifact_promotion_is_atomic_fenced_and_idempotent(self):
        final = Path(self.tmp.name) / "result.bin"
        self.artifacts.write(final, "task", 1, b"complete")
        self.artifacts.promote(final, "task", 1, "g1", "effect")
        self.assertEqual(final.read_bytes(), b"complete")
        self.artifacts.promote(final, "task", 1, "g1", "effect")
        self.artifacts.write(final, "task", 2, b"stale")
        with self.assertRaisesRegex(ArtifactLifecycleError, "FENCE"):
            self.artifacts.promote(final, "task", 2, "g2", "other")
