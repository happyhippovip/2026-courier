import re

with open("tests/test_write_reliability.py", "r") as f:
    content = f.read()

# I will just rewrite the bottom chunk. 
# find the index of "def test_e10_second_attempt_human_gate"
idx = content.find("    def test_e10_second_attempt_human_gate")
if idx != -1:
    content = content[:idx]

new_tests = """
    def test_e10_second_attempt_human_gate(self):
        def mock_dispatch(agent, env, adp):
            self.dispatch_count += 1
            if self.dispatch_count == 1:
                return {"result_path": "dummy.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}
            else:
                return {"result_path": "dummy.json", "route": agent, "result": {"status": "HUMAN_GATE", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp_2", "payload": {"verdict": "HUMAN_GATE"}, "error_type": "AUTHENTICATION_REQUIRED"}}
        self.dispatcher.adapter_boundary.dispatch = mock_dispatch
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 2)
        self.assertIn(res["status"], ["HUMAN_GATE", "FAILED"])
        self.assertNotEqual(res["status"], "VERIFIED")

    def test_e11_identity_mismatch_no_retry(self):
        def mock_dispatch(agent, env, adp):
            self.dispatch_count += 1
            return {"result_path": "dummy.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": "WRONG_HASH", "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}
        self.dispatcher.adapter_boundary.dispatch = mock_dispatch
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 1)
        self.assertEqual(res["status"], "FAILED")

    def test_e14_cli1_no_write_retry(self):
        # process m1 to get it out of the way
        self.dispatcher.mission_queue.claim_next("founder")
        self.dispatcher.mission_queue.transition("m1", "FAILED", "founder")
        
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m_cli1",
            "capability_required": "implementation",
            "preferred_agent": "CLI1",
            "task": {
                "action": "implement_bounded_improvement",
                "requires_write": True,
                "acceptance_criteria": {"file_exists": "effect.txt"}
            }
        })
        def mock_dispatch(agent, env, adp):
            if agent == "CLI1":
                raise RuntimeError("CLI1_READONLY_CONTRACT_VIOLATED")
            self.dispatch_count += 1
            return {"result_path": "dummy.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}
        self.dispatcher.adapter_boundary.dispatch = mock_dispatch
        try:
            res = self.dispatcher.process_next_mission("founder")
        except Exception:
            res = {"status": "FAILED"}
        self.assertLessEqual(self.dispatch_count, 0) # never dispatched successfully
        self.assertNotEqual(res["status"], "VERIFIED")

    def test_e15_courier_never_writes_effect(self):
        self.create_effect_on_attempt = 3
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 2)
        self.assertNotEqual(res["status"], "VERIFIED")
        self.assertFalse((self.workspace / "effect.txt").exists())

    def test_e16_stale_effect_rejected(self):
        (self.workspace / "effect.txt").write_text("DONE")
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 1)
        self.assertEqual(res["status"], "FAILED")

    def test_e17_freshness_required(self):
        (self.workspace / "effect.txt").write_text("DONE")
        self.create_effect_on_attempt = 1
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 1)
        self.assertEqual(res["status"], "FAILED")

    def test_e18_ledger_binds_final_execution(self):
        self.create_effect_on_attempt = 2
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(res["status"], "VERIFIED")
        
        ledger_data = self.dispatcher.ledger._load_ledger()
        reviews = ledger_data.get("reviews", {})
        self.assertTrue(len(reviews) > 0)
        last_review = list(reviews.values())[-1]
        
        # Check result fingerprint hash matches the mock result data hash
        from scripts.review_budget import canonical_json_dumps, compute_sha256
        result_data_1 = {"status": "COMPLETED", "task_hash": self.last_envelope.task_hash, "mission_id": "m1", "target_agent": "GEMINI", "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS", "summary": "Did it"}}
        result_data_2 = {"status": "COMPLETED", "task_hash": self.last_envelope.task_hash, "mission_id": "m1", "target_agent": "GEMINI", "result_fingerprint": "mock_fp_2", "payload": {"verdict": "PASS", "summary": "Did it on retry"}}
        fp1 = compute_sha256(canonical_json_dumps(result_data_1))
        fp2 = compute_sha256(canonical_json_dumps(result_data_2))
        
        self.assertEqual(last_review["file_hashes"]["result_fingerprint"], fp2)
        self.assertNotEqual(last_review["file_hashes"]["result_fingerprint"], fp1)
        self.assertEqual(last_review["file_hashes"]["effect_verified"], "True")
        self.assertEqual(last_review["file_hashes"]["freshness_verified"], "True")
        self.assertEqual(last_review["file_hashes"]["worker_id"], "GEMINI")
        self.assertEqual(last_review["file_hashes"]["mission_id"], "m1")

    def test_e21_no_canary_specific_production_logic(self):
        import pathlib
        prod_files = [
            Path("scripts/courier_safety_dispatcher.py"),
            Path("scripts/courier_real_worker_adapters.py"),
            Path("scripts/native_agy_runner.py")
        ]
        forbidden = [
            "courier_freeze_native_canary_",
            "CANARY_4", "CANARY_5", "CANARY_6", "CANARY_7", "CANARY_8",
            "COURIER_NATIVE_AUTONOMY_PROVEN_"
        ]
        for fpath in prod_files:
            if not fpath.exists(): continue
            text = fpath.read_text()
            for token in forbidden:
                self.assertNotIn(token, text, f"Forbidden token {token} found in {fpath}")

"""

content += new_tests

with open("tests/test_write_reliability.py", "w") as f:
    f.write(content)

