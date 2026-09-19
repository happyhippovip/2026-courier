import re

with open("tests/test_agent_handoff_ledger.py", "r") as f:
    code = f.read()

# Locate the function and replace it ENTIRELY
match = re.search(r'    def test_acceptance_cannot_consume_same_update_evidence\(self\):.*?    def test_reject_copied_proof_with_different_sha', code, flags=re.DOTALL)
if match:
    new_func = """    def test_acceptance_cannot_consume_same_update_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger.json"
            initialize(ledger)
            bundle = ledger_module.load_bundle(ledger)
            landed = ledger_module.copy.deepcopy(
                bundle["acceptance_guard"]
            )
            proof = {
                "source_url": "https://github.com/example/project/actions/runs/2",
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-09-17T18:00:00Z",
                "evidence_sha": "b" * 40,
                "runtime_binding": "b" * 40,
                "validity": "VALID",
                "reason": "foreign attestation",
                "producer_id": "foreign-producer",
                "verifier_id": "foreign-verifier",
                "result_sha256": "0000000000000000000000000000000000000000"
            }
            
            ledger_module._attestation_resolver = lambda url: {
                "verdict": "PASS",
                "producer_principal": "foreign-producer",
                "verifier_principal": "foreign-verifier",
                "result_sha256": "0000000000000000000000000000000000000000",
                "goal_id": "test",
                "binding": {
                    "sha": "b" * 40,
                    "runtime": "b" * 40
                }
            }

            landed["evidence"].append(proof)
            landed["transition_state"] = "CANONICAL_ACCEPTED"
            landed["acceptance_predicate"]["results"]["ISSUE_STATE"][
                "status"
            ] = "PASS"
            landed["acceptance_predicate"]["results"]["ISSUE_STATE"][
                "evidence_urls"
            ] = [proof["source_url"]]
            landed["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"][
                "status"
            ] = "PASS"
            landed["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"][
                "observed_value"
            ] = "PASS"
            landed["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"][
                "evidence_urls"
            ] = [proof["source_url"]]

            with self.assertRaisesRegex(ledger_module.SelfCertificationError, "predicate PASS requires prior evidence"):
                ledger_module.update(
                    ledger,
                    bundle["revision"],
                    {"UNPROVEN_EDGES": [], "PROVEN_EDGES": ["issue state", "runtime artifact"]},
                    "foreign-worker",
                    1.0,
                    landed,
                )

            # Now do it correctly: First add the evidence without claiming PASS
            valid_land = ledger_module.copy.deepcopy(bundle["acceptance_guard"])
            valid_land["evidence"].append(proof)
            after_landing = ledger_module.update(
                ledger,
                bundle["revision"],
                {"UNPROVEN_EDGES": [], "PROVEN_EDGES": ["issue state", "runtime artifact"]},
                "foreign-worker",
                1.0,
                valid_land,
            )
            
            self.assertEqual(
                after_landing["acceptance_guard"]["transition_state"],
                "PROVISIONAL",
            )
            self.assertNotEqual(after_landing["record"]["CLEAN_IDLE"], "YES")
            
            # Now consume the prior evidence to reach CANONICAL_ACCEPTED
            followed_guard = ledger_module.copy.deepcopy(after_landing["acceptance_guard"])
            followed_guard["transition_state"] = "CANONICAL_ACCEPTED"
            followed_guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "PASS"
            followed_guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = [proof["source_url"]]
            followed_guard["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "PASS"
            followed_guard["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["observed_value"] = "PASS"
            followed_guard["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["evidence_urls"] = [proof["source_url"]]
            
            followed = ledger_module.update(
                ledger,
                after_landing["revision"],
                {"TASKS_COMPLETED": 3},
                "another-worker",
                1.0,
                followed_guard
            )
            self.assertEqual(
                followed["acceptance_guard"]["transition_state"],
                "CANONICAL_ACCEPTED",
            )
            
            # Clean up resolver
            ledger_module._attestation_resolver = None

    def test_reject_copied_proof_with_different_sha"""
    code = code[:match.start()] + new_func + code[match.end():]
    
    with open("tests/test_agent_handoff_ledger.py", "w") as f:
        f.write(code)

