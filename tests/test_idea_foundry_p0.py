import unittest
import json
import shutil
from pathlib import Path
from scripts.idea_foundry import IdeaFoundry, CANDIDATES_DIR, EXPERIMENTS_DIR, RESULT_LINKS_DIR, EVENTS_DIR
from scripts.run_thought_memory_mesh import canonical_hash

class TestIdeaFoundryP0(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("scratch/foundry_workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.foundry = IdeaFoundry(self.workspace)
        
        # clean up global dirs for test isolation
        for d in [CANDIDATES_DIR, EXPERIMENTS_DIR, RESULT_LINKS_DIR, EVENTS_DIR]:
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
            
    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_no_source_refs_fails(self):
        with self.assertRaises(ValueError):
            self.foundry.synthesize_candidate([])
            
    def test_missing_provenance_fails(self):
        with self.assertRaises(ValueError):
            self.foundry.synthesize_candidate([{"source_message_id": "m1", "content_hash": "h1"}]) # missing original_envelope

    def test_two_source_thoughts_produce_one_candidate(self):
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "crypto problem"}}}
        t2 = {"source_message_id": "m2", "content_hash": "h2", "original_envelope": {"content": {"summary": "is bad"}}}
        cand = self.foundry.synthesize_candidate([t1, t2])
        self.assertEqual(len(cand["source_thought_refs"]), 2)
        self.assertEqual(cand["source_thought_refs"], ["m1", "m2"])
        
    def test_idempotent_replay(self):
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "crypto problem"}}}
        cand1 = self.foundry.synthesize_candidate([t1])
        cand2 = self.foundry.synthesize_candidate([t1])
        self.assertEqual(cand1["candidate_id"], cand2["candidate_id"])
        self.assertEqual(cand1["version"], cand2["version"]) # no update
        
    def test_similar_keywords_different_sources_do_not_merge(self):
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "crypto problem"}}}
        t2 = {"source_message_id": "m2", "content_hash": "h2", "original_envelope": {"content": {"summary": "crypto problem"}}}
        cand1 = self.foundry.synthesize_candidate([t1])
        cand2 = self.foundry.synthesize_candidate([t2])
        self.assertNotEqual(cand1["candidate_id"], cand2["candidate_id"])
        
    def test_weak_candidate_parked_or_killed(self):
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "crypto problem"}}}
        cand = self.foundry.synthesize_candidate([t1])
        cand = self.foundry.challenge_candidate(cand)
        self.assertEqual(cand["status"], "KILLED") # because it contains 'crypto' -> policy conflict
        
    def test_strong_candidate_ready(self):
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "We need to verify user retention"}}}
        cand = self.foundry.synthesize_candidate([t1])
        cand["problem_statement"] = "Retention is low"
        cand["target_user_or_founder"] = "Internal team"
        cand = self.foundry.challenge_candidate(cand)
        self.assertEqual(cand["status"], "EXPERIMENT_READY")
        
    def test_experiment_needs_candidate(self):
        # A killed candidate won't propose
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "crypto problem"}}}
        cand = self.foundry.synthesize_candidate([t1])
        cand = self.foundry.challenge_candidate(cand)
        exp = self.foundry.propose_experiment(cand)
        self.assertIsNone(exp)
        
    def test_goal_proposal(self):
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "retention problem"}}}
        cand = self.foundry.synthesize_candidate([t1])
        cand["problem_statement"] = "Retention is low"
        cand["target_user_or_founder"] = "Internal team"
        cand = self.foundry.challenge_candidate(cand)
        exp = self.foundry.propose_experiment(cand)
        
        goal_id = self.foundry.handoff_to_courier(cand, exp)
        self.assertIsNotNone(goal_id)
        
        # Duplicate handoff is idempotent
        goal_id2 = self.foundry.handoff_to_courier(cand, exp)
        self.assertEqual(goal_id, goal_id2)
        
    def test_result_linkage(self):
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "retention problem"}}}
        cand = self.foundry.synthesize_candidate([t1])
        cand["problem_statement"] = "Retention is low"
        cand["target_user_or_founder"] = "Internal team"
        cand = self.foundry.challenge_candidate(cand)
        exp = self.foundry.propose_experiment(cand)
        goal_id = self.foundry.handoff_to_courier(cand, exp)
        
        # Link valid
        res = self.foundry.link_courier_result(
            candidate_id=cand["candidate_id"],
            experiment_id=exp["experiment_id"],
            courier_goal_id=goal_id,
            mission_id="m123",
            correlation_id="corr1",
            result_fingerprint="fing1",
            verification_reference="vr1",
            result_reference="rr1"
        )
        self.assertEqual(res["status"], "LINKED")
        
        # Link duplicate is skipped
        res2 = self.foundry.link_courier_result(
            candidate_id=cand["candidate_id"],
            experiment_id=exp["experiment_id"],
            courier_goal_id=goal_id,
            mission_id="m123",
            correlation_id="corr1",
            result_fingerprint="fing1",
            verification_reference="vr1",
            result_reference="rr1"
        )
        self.assertEqual(res2["status"], "SKIPPED")
        
        # Next best action asks for human review
        cand_updated = json.loads((CANDIDATES_DIR / f"{cand['candidate_id']}.json").read_text())
        nba = self.foundry.next_best_action(cand_updated)
        self.assertEqual(nba["next_job"], "REQUEST_FOUNDER_REVIEW")
        
    def test_invalid_result_linkage(self):
        res = self.foundry.link_courier_result(
            candidate_id="cand-fake",
            experiment_id="exp1",
            courier_goal_id="g1",
            mission_id="m1",
            correlation_id="c1",
            result_fingerprint="f1",
            verification_reference="v1",
            result_reference="r1"
        )
        self.assertEqual(res["status"], "FAILED")

if __name__ == '__main__':
    unittest.main()
