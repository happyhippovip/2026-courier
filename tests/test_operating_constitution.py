"""
test_operating_constitution.py - Acceptance Tests for Windows Courier Operating Constitution
Verifies:
- Durable persistence of Markdown and JSON constitution files
- Fresh session policy discovery and loading via ConstitutionLoader
- Queue reconciliation policy invariants
- Weiter coalescing & single-trigger autonomy policy invariants
- One writer & crash-loop policy invariants
- Value Governor & anti-busywork policy invariants
- Human gates & Mac scope isolation policy invariants
- Chief handover policy invariants
"""

import os
import sys
import json
import hashlib
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.constitution import ConstitutionLoader


class TestOperatingConstitution(unittest.TestCase):
    def setUp(self):
        self.courier_json = os.path.join(WORKSPACE_ROOT, "courier", "WINDOWS_COURIER_OPERATING_CONSTITUTION.json")
        self.courier_md = os.path.join(WORKSPACE_ROOT, "courier", "WINDOWS_COURIER_OPERATING_CONSTITUTION.md")

    def test_01_constitution_persisted_and_valid(self):
        self.assertTrue(os.path.exists(self.courier_json), "JSON constitution missing")
        self.assertTrue(os.path.exists(self.courier_md), "Markdown constitution missing")

        with open(self.courier_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("status"), "ACTIVE")
        self.assertIn(data.get("policy_version"), ("1.0.0", "1.1.0"))
        self.assertEqual(data.get("machine_role"), "WINDOWS")
        self.assertEqual(data.get("source"), "CHIEF_DIRECTIVE")

        with open(self.courier_md, "r", encoding="utf-8") as f:
            md_text = f.read()

        self.assertIn("ARTICLE 1 — ROLE & AUTHORITY", md_text)
        self.assertIn("ARTICLE 31 — FINAL OPERATING LOOP", md_text)
        self.assertIn("ARTICLE 33 — TWO-METHOD REAL EXHAUSTION COURT", md_text)
        self.assertIn("ARTICLE 34 — CONTINUATION CAMPAIGN AUTONOMY", md_text)

    def test_02_fresh_session_policy_load(self):
        loaded, data, path, h = ConstitutionLoader.discover_and_load()
        self.assertTrue(loaded, "Failed to load constitution via ConstitutionLoader")
        self.assertEqual(data.get("status"), "ACTIVE")
        self.assertIn(data.get("policy_version"), ("1.0.0", "1.1.0"))
        self.assertGreaterEqual(len(data.get("articles", {})), 32)

        summary = ConstitutionLoader.get_summary()
        self.assertEqual(summary["status"], "ACTIVE")
        self.assertIn(summary["policy_version"], ("1.0.0", "1.1.0"))
        self.assertIn("policy_hash", summary)

    def test_03_queue_reconciliation_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art3 = data["articles"]["article_03_queue_reconciliation"]
        self.assertFalse(art3["blind_execution"])
        self.assertTrue(art3["older_prompt_cannot_undo_newer_state"])
        self.assertTrue(art3["equivalent_prompts_map_to_one_intent"])
        self.assertIn("SUPERSEDED", art3["classification_categories"])
        self.assertIn("ALREADY_SATISFIED", art3["classification_categories"])

    def test_04_weiter_coalescing_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art4 = data["articles"]["article_04_weiter_semantics"]
        self.assertEqual(art4["semantic_meaning"], "CONTINUE_INTENT")
        self.assertTrue(art4["coalesce_duplicate_weiter"])
        self.assertEqual(art4["max_outstanding_continuation_intents"], 1)
        self.assertEqual(art4["running_loop_behavior"], "NOOP_SUPPRESSED")

    def test_05_single_trigger_autonomy_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art5 = data["articles"]["article_05_no_synthetic_human_clock"]
        self.assertFalse(art5["for_loop_weiter_autonomy_proof_allowed"])
        self.assertEqual(art5["max_external_start_signals"], 1)
        self.assertEqual(art5["internal_loop_order"][0], "RECONCILE")
        self.assertEqual(art5["internal_loop_order"][-1], "SELECT_SUCCESSOR")

    def test_06_one_writer_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art7 = data["articles"]["article_07_one_writer_law"]
        self.assertEqual(art7["max_concurrent_conflicting_writers"], 1)
        self.assertIn("lease", art7["pre_write_checks"])

        art10 = data["articles"]["article_10_recovery_law"]
        self.assertEqual(art10["max_safe_recovery_attempts"], 1)
        self.assertTrue(art10["prevent_duplicate_effects"])

    def test_07_value_governor_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art11 = data["articles"]["article_11_no_busywork"]
        self.assertIn("REPETITIVE_ROUND_BENCHMARKS", art11["disallowed_categories"])
        self.assertIn("TASK_COUNT_MILESTONE_ONLY", art11["disallowed_categories"])

        art12 = data["articles"]["article_12_value_governor"]
        self.assertFalse(art12["speculative_potential_sufficient"])
        self.assertIn("EXPECTED_REAL_DELTA", art12["required_task_fields"])

    def test_08_human_gate_and_mac_isolation_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art21 = data["articles"]["article_21_human_gates"]
        self.assertIn("LIVE_STRIPE", art21["parked_gate_keys"])
        self.assertIn("LIVE_PAYMENT", art21["parked_gate_keys"])
        self.assertFalse(art21["blocks_independent_safe_work"])

        art23 = data["articles"]["article_23_windows_mac_boundary"]
        self.assertFalse(art23["mac_conflicting_writes_allowed"])
        self.assertFalse(art23["windows_self_certify_mac_accepted_allowed"])

    def test_09_chief_handover_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art29 = data["articles"]["article_29_chief_handover"]
        self.assertEqual(art29["canonical_path"], "courier/CANONICAL_WINDOWS_CHIEF_HANDOVER.json")
        self.assertFalse(art29["secrets_allowed"])

    def test_10_two_method_exhaustion_court_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art32 = data["articles"]["article_32_two_method_exhaustion_court"]
        self.assertTrue(art32["exhaustion_claim_requires_two_methods"])
        self.assertEqual(art32["method_a"], "STATE_TESTS_DEFECTS_PROOF_DEBT_CONTROL_PLANE")
        self.assertEqual(art32["method_b"], "REPOSITORY_RUNTIME_FAILURE_PATHS_CUSTOMER_DELIVERY")
        self.assertEqual(art32["action_on_discrepancy"], "CONTINUE_CAMPAIGN_AUTOMATICALLY")

    def test_11_multi_signal_campaign_autonomy_policy(self):
        _, data, _, _ = ConstitutionLoader.discover_and_load()
        art33 = data["articles"]["article_33_multi_signal_campaign_autonomy"]
        self.assertFalse(art33["signals_multiply_work"])
        self.assertEqual(art33["max_active_campaigns"], 1)
        self.assertTrue(art33["campaign_owns_continuation"])
        self.assertEqual(art33["duplicate_signals_handling"], "COALESCED_NOOP")


if __name__ == "__main__":
    unittest.main()
