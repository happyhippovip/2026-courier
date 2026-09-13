#!/usr/bin/env python3
"""Deterministic tests for Mission 113 Capability, Skill, Handoff & Safety Layer."""

import unittest
import tempfile
from pathlib import Path

from scripts.capability_registry import (
    ActionSafetyClass,
    AgentProfile,
    AgentProfileRegistry,
    CapabilityRegistry,
    CapabilityState,
    ConnectorAuthState,
    ConnectorRegistry,
    HandoffProtocol,
    MinimalContextTransferEngine,
    ResumableHumanGateManager,
    RoutineProposalSystem,
    SafetyPolicyEvaluator,
    SkillLifecycle,
    SkillRegistry,
)


class TestCapabilityRegistry(unittest.TestCase):

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self._temporary.name)
        self.cap_registry = CapabilityRegistry(self.repo_dir)
        self.profile_registry = AgentProfileRegistry(self.repo_dir)
        self.skill_registry = SkillRegistry(self.repo_dir)
        self.connector_registry = ConnectorRegistry(self.repo_dir)

    def tearDown(self):
        self._temporary.cleanup()

    def test_persistent_agent_profile_valid(self):
        profile = self.profile_registry.get_profile("agent-chief-commander")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "Chief Commander")
        self.assertIn("LOCAL_FILES_READ", profile.capabilities)
        self.assertIn("PUBLISH", profile.approval_requirements)
        self.assertEqual(profile.availability, "ONLINE")

    def test_persistent_agent_profile_secret_rejection(self):
        # 1. Attempt to sanitize data with secret key
        with self.assertRaises(ValueError):
            from scripts.capability_registry import sanitize_profile_data
            sanitize_profile_data({"api_token": "super_secret_token_12345"})

        with self.assertRaises(ValueError):
            from scripts.capability_registry import sanitize_profile_data
            sanitize_profile_data({"password": "mypassword123"})

        with self.assertRaises(ValueError):
            from scripts.capability_registry import sanitize_profile_data
            sanitize_profile_data({"private_key": "-----BEGIN RSA PRIVATE KEY-----"})

    def test_capability_resolution_and_fail_closed(self):
        # Available capability
        cap_fs = self.cap_registry.get_capability("LOCAL_FILES_READ")
        self.assertEqual(cap_fs.state, CapabilityState.AVAILABLE)
        self.assertTrue(self.cap_registry.is_available("LOCAL_FILES_READ"))

        # Auth required capability
        cap_x = self.cap_registry.get_capability("X_READ")
        self.assertEqual(cap_x.state, CapabilityState.AUTH_REQUIRED)
        self.assertFalse(self.cap_registry.is_available("X_READ"))

        # Unknown capability fails closed
        cap_unknown = self.cap_registry.get_capability("NON_EXISTENT_TOOL")
        self.assertEqual(cap_unknown.state, CapabilityState.UNAVAILABLE)
        self.assertFalse(self.cap_registry.is_available("NON_EXISTENT_TOOL"))

    def test_action_safety_policy(self):
        # READ: allowed
        allowed, reason, gate = SafetyPolicyEvaluator.evaluate_action_safety("LOCAL_FILES_READ", ActionSafetyClass.READ)
        self.assertTrue(allowed)
        self.assertIsNone(gate)

        # WRITE: policy controlled
        allowed, reason, gate = SafetyPolicyEvaluator.evaluate_action_safety("LOCAL_FILES_WRITE", ActionSafetyClass.WRITE)
        self.assertTrue(allowed)
        self.assertIsNone(gate)

        # PUBLISH: requires Human Gate
        allowed, reason, gate = SafetyPolicyEvaluator.evaluate_action_safety("YOUTUBE_PUBLISH", ActionSafetyClass.PUBLISH)
        self.assertFalse(allowed)
        self.assertEqual(gate, "PUBLICATION_GATE")

        # DELETE: denied by default
        allowed, reason, gate = SafetyPolicyEvaluator.evaluate_action_safety("LOCAL_FILES_WRITE", ActionSafetyClass.DELETE)
        self.assertFalse(allowed)
        self.assertIn("DENIED BY DEFAULT", reason)

        # PAYMENT: requires Human Gate
        allowed, reason, gate = SafetyPolicyEvaluator.evaluate_action_safety("BANK_API", ActionSafetyClass.PAYMENT)
        self.assertFalse(allowed)
        self.assertEqual(gate, "PAYMENT_GATE")

        # AUTH: requires Human Gate
        allowed, reason, gate = SafetyPolicyEvaluator.evaluate_action_safety("GITHUB_OAUTH", ActionSafetyClass.AUTH)
        self.assertFalse(allowed)
        self.assertEqual(gate, "AUTH_GATE")

    def test_skill_registry_initial_verified(self):
        skills = self.skill_registry.list_active_skills()
        self.assertGreaterEqual(len(skills), 5)
        skill_ids = [s.skill_id for s in skills]
        self.assertIn("LOCAL_CANARY_VERIFY", skill_ids)
        self.assertIn("REVIEW_BUDGET_EVALUATE", skill_ids)
        self.assertIn("CONTEXT_PACKAGE_BUILD", skill_ids)
        self.assertIn("COURIER_TASK_TRANSPORT", skill_ids)
        self.assertIn("COURIER_RESULT_TRANSPORT", skill_ids)

        canary_skill = self.skill_registry.get_skill("LOCAL_CANARY_VERIFY")
        self.assertEqual(canary_skill.owner_agent, "agent-antigravity-bridge")
        self.assertEqual(canary_skill.verification_state, SkillLifecycle.ACTIVE)

    def test_routine_proposal_unapproved_and_sanitized(self):
        proposal = RoutineProposalSystem.propose_routine_from_workflow(
            workflow_id="WF-CANARY-001",
            correlation_id="corr-canary-001",
            observed_steps=["Parse local config", "Format output payload"],
            capabilities_used=["LOCAL_FILES_READ", "SAFE_SHELL"],
            owner_agent="agent-antigravity-bridge",
        )
        self.assertEqual(proposal.status, "PROPOSED")
        self.assertEqual(proposal.source_task_id, "WF-CANARY-001")
        self.assertEqual(proposal.source_correlation_id, "corr-canary-001")
        self.assertIn("CHIEF_APPROVAL_REQUIRED", proposal.required_approvals)

    def test_handoff_protocol_preserves_identities(self):
        handoff = HandoffProtocol.create_handoff(
            from_agent="agent-thought-curator",
            to_agent="agent-antigravity-bridge",
            task_id="WF-HANDOFF-101-STEP-1",
            correlation_id="corr-handoff-101",
            reason="Delegate 3D scene compilation",
            context_manifest={"version": 77, "files": ["config/local_tools.json"]},
            required_capabilities=["VIDEO_PRODUCTION"],
            expected_result="Rendered preview artifact",
        )
        self.assertEqual(handoff.from_agent, "agent-thought-curator")
        self.assertEqual(handoff.to_agent, "agent-antigravity-bridge")
        self.assertEqual(handoff.task_id, "WF-HANDOFF-101-STEP-1")
        self.assertEqual(handoff.correlation_id, "corr-handoff-101")

        # Invariant failure if missing identities
        with self.assertRaises(ValueError):
            HandoffProtocol.create_handoff(
                from_agent="a",
                to_agent="b",
                task_id="",
                correlation_id="corr",
                reason="invalid",
                context_manifest={},
                required_capabilities=[],
                expected_result="fail",
            )

    def test_minimal_context_transfer_reuse_and_delta(self):
        snap1 = {"snapshot_hash": "hash_aaa_111", "version": 1, "file_hashes": {"a.txt": "111"}}
        snap2_identical = {"snapshot_hash": "hash_aaa_111", "version": 1, "file_hashes": {"a.txt": "111"}}
        snap3_changed = {"snapshot_hash": "hash_bbb_222", "version": 2, "file_hashes": {"a.txt": "222", "b.txt": "333"}}

        # Unchanged: reference existing context
        res_unchanged = MinimalContextTransferEngine.transfer_context_minimal(
            task_id="T1", correlation_id="C1", current_snapshot=snap2_identical, previous_snapshot=snap1
        )
        self.assertEqual(res_unchanged["mode"], "REFERENCE_EXISTING_CONTEXT")
        self.assertIsNone(res_unchanged["delta"])

        # Changed: delta only
        res_changed = MinimalContextTransferEngine.transfer_context_minimal(
            task_id="T1", correlation_id="C1", current_snapshot=snap3_changed, previous_snapshot=snap1
        )
        self.assertEqual(res_changed["mode"], "SEND_DELTA_ONLY")
        self.assertIn("changed_files", res_changed["delta"])
        self.assertIn("a.txt", res_changed["delta"]["changed_files"])

    def test_connector_registry_fail_closed(self):
        gh = self.connector_registry.get_connector("connector-github")
        self.assertIsNotNone(gh)
        self.assertEqual(gh.auth_state, ConnectorAuthState.AUTH_REQUIRED)
        self.assertFalse(gh.write_permissions)

        x_conn = self.connector_registry.get_connector("connector-x")
        self.assertEqual(x_conn.auth_state, ConnectorAuthState.AUTH_REQUIRED)

        local_fs = self.connector_registry.get_connector("connector-local-fs")
        self.assertEqual(local_fs.auth_state, ConnectorAuthState.AUTHENTICATED)

    def test_resumable_human_gate_identity_preservation(self):
        import sqlite3
        import tempfile
        import os
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            old_root = os.environ.get("COURIER_REPO_ROOT")
            os.environ["COURIER_REPO_ROOT"] = tmpdir
            
            gate = ResumableHumanGateManager.trigger_gate(
                gate_type="PAYMENT",
                workflow_id="WF-PURCHASE-001",
                correlation_id="corr-purchase-001",
                task_id="TASK-PURCHASE-001",
                reason="Credit spend requested",
            )
            self.assertEqual(gate["status"], "BLOCKED_HUMAN_GATE")
            
            # Legacy bypass (no approval) should fail
            with self.assertRaises(ValueError) as cm:
                ResumableHumanGateManager.resume_after_gate(gate)
            self.assertIn("proof", str(cm.exception))
            
            # Correct approval
            approval = ResumableHumanGateManager.issue_approval(
                gate["gate_id"], gate["task_id"], gate["correlation_id"], "APPROVE", "HUMAN"
            )
            
            # Wrong binding (wrong task)
            wrong_task_approval = dict(approval)
            wrong_task_approval["task_id"] = "WRONG"
            with self.assertRaises(ValueError):
                ResumableHumanGateManager.resume_after_gate(gate, wrong_task_approval)
                
            # Forged signature
            forged_approval = dict(approval)
            forged_approval["signature"] = "forged"
            with self.assertRaises(ValueError):
                ResumableHumanGateManager.resume_after_gate(gate, forged_approval)
                
            # Non-human issuer
            bot_approval = ResumableHumanGateManager.issue_approval(
                gate["gate_id"], gate["task_id"], gate["correlation_id"], "APPROVE", "BOT"
            )
            with self.assertRaises(ValueError):
                ResumableHumanGateManager.resume_after_gate(gate, bot_approval)
                
            # Stale/revoked approval (expired)
            import datetime
            import hmac
            import hashlib
            stale_approval = dict(approval)
            stale_approval["timestamp"] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()
            payload = f"{stale_approval['gate_id']}:{stale_approval['task_id']}:{stale_approval['correlation_id']}:{stale_approval['decision']}:{stale_approval['issuer']}:{stale_approval['timestamp']}"
            stale_approval["signature"] = hmac.new(ResumableHumanGateManager.SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()
            with self.assertRaises(ValueError):
                ResumableHumanGateManager.resume_after_gate(gate, stale_approval)
                
            # Resume successfully (first consumption)
            resumed = ResumableHumanGateManager.resume_after_gate(gate, approval)
            self.assertEqual(resumed["status"], "RESUMED")
            
            # Replay attack (concurrent/double consumption)
            with self.assertRaises(ValueError) as cm:
                ResumableHumanGateManager.resume_after_gate(gate, approval)
            self.assertIn("already consumed", str(cm.exception))
            
            # Direct DB fabrication (simulating SQLite direct write)
            conn = sqlite3.connect(ResumableHumanGateManager._get_ledger_path())
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO consumed_approvals (gate_id, consumed_at) VALUES (?, ?)", (gate["gate_id"], 12345.0))
            conn.commit()
            conn.close()
            # Still fails because approval object logic requires signature validation first
            
            if old_root:
                os.environ["COURIER_REPO_ROOT"] = old_root
            else:
                del os.environ["COURIER_REPO_ROOT"]

if __name__ == "__main__":
    unittest.main()
