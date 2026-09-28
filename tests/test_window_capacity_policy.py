import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scripts.window_capacity_policy as p

class WindowCapacityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.state=Path(self.tmp.name)/"state.json"
        self.defaults=Path(self.tmp.name)/"defaults.json"
        self.defaults.write_text(json.dumps({"target_window_slots":16}),encoding="utf-8")
        self.patch1=patch.object(p,"STATE_FILE",self.state)
        self.patch2=patch.object(p,"DEFAULTS_FILE",self.defaults)
        self.patch1.start(); self.patch2.start()
    def tearDown(self):
        self.patch2.stop(); self.patch1.stop(); self.tmp.cleanup()
    def test_persists_profile_and_visibility(self):
        got=p.update_policy(slots=32,controls_hidden=True)
        self.assertEqual(got["target_window_slots"],32)
        self.assertTrue(got["controls_hidden"])
        self.assertEqual(p.load_policy()["target_window_slots"],32)
    def test_invalid_slots_fail_closed(self):
        with self.assertRaises(ValueError): p.update_policy(slots=64)
    def test_scale_down_drains_without_kill_semantics(self):
        pol=p.update_policy(slots=8)
        a=p.admission(pol,12)
        self.assertEqual(a["mode"],"DRAINING")
        self.assertFalse(a["allow_new_window"])
        self.assertEqual(a["remaining_slots"],0)
    def test_pause_blocks_new_admission(self):
        pol=p.update_policy(paused=True)
        self.assertFalse(p.admission(pol,0)["allow_new_window"])
    def test_writer_and_heavy_caps_never_scale_with_windows(self):
        pol=p.update_policy(slots=32)
        self.assertEqual(pol["max_mutable_writers"],1)
        self.assertEqual(pol["max_heavy_jobs_per_host"],1)
if __name__=="__main__": unittest.main()
