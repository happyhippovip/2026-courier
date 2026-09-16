"""
Deterministic Unit Tests for Courier Cross-Device Task Intake & Team Coordination Engine
Tests Cases 1 to 8 AND Team Model Tests A through H.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cross_device_intake import (
    CrossDeviceIntakeEngine, MessageClass, TaskStatus, ActionDomain,
    Host, Agent, detect_host_and_agent, CrossMachineResourceManager
)

class TestCrossDeviceIntakeAndTeamModel(unittest.TestCase):
    def setUp(self):
        self.engine = CrossDeviceIntakeEngine()
        self.resource_manager = CrossMachineResourceManager()

    # --- ORIGINAL CASES 1 TO 8 ---

    def test_case_1_windows_github_login_required(self):
        """CASE 1: 'Windows sagt GitHub login nötig.' -> HUMAN_GATE, ERLEDIGT: NEIN"""
        res = self.engine.classify_and_route("Windows sagt GitHub login nötig.")
        self.assertEqual(res.message_class, MessageClass.HUMAN_GATE)
        self.assertEqual(res.status, TaskStatus.BLOCKED)
        self.assertFalse(res.erledigt)
        self.assertEqual(res.action_domain, ActionDomain.HUMAN_ONLY)
        self.assertIn("ERLEDIGT: NEIN", res.to_terminal_format())

    def test_case_2_delegation_to_chief(self):
        """CASE 2: 'Windows sagt: ChatGPT soll das über den verbundenen GitHub machen.' -> DELEGATION_TO_CHIEF"""
        res = self.engine.classify_and_route(
            "Windows sagt: ChatGPT soll das über den verbundenen GitHub machen.",
            context={"has_connected_tool": True}
        )
        self.assertEqual(res.message_class, MessageClass.DELEGATION_TO_CHIEF)
        self.assertEqual(res.action_domain, ActionDomain.CONNECTED_REMOTE)
        self.assertTrue(res.requires_worker_launch)
        self.assertFalse(res.erledigt)

    def test_case_3_verified_completion(self):
        """CASE 3: 'Tests 25/25 PASS, Datei remote verifiziert.' -> COMPLETED_RESULT, ERLEDIGT: JA"""
        res = self.engine.classify_and_route("Tests 25/25 PASS, Datei remote verifiziert.")
        self.assertEqual(res.message_class, MessageClass.COMPLETED_RESULT)
        self.assertEqual(res.status, TaskStatus.DONE)
        self.assertTrue(res.erledigt)
        self.assertEqual(res.blocker, "NONE")
        self.assertIn("ERLEDIGT: JA", res.to_terminal_format())

    def test_case_4_worker_claim_without_evidence(self):
        """CASE 4: 'Worker says success' but no effect evidence -> ERLEDIGT: NEIN"""
        res = self.engine.classify_and_route("Worker says success with no proof.")
        self.assertFalse(res.erledigt)
        self.assertNotEqual(res.status, TaskStatus.DONE)
        self.assertIn("ERLEDIGT: NEIN", res.to_terminal_format())

    def test_case_5_task_still_running(self):
        """CASE 5: 'Task still running.' -> STATUS = RUNNING, ERLEDIGT: NEIN, no duplicate worker"""
        res = self.engine.classify_and_route("Task still running.")
        self.assertEqual(res.status, TaskStatus.RUNNING)
        self.assertFalse(res.erledigt)
        self.assertFalse(res.requires_worker_launch)
        self.assertIn("ERLEDIGT: NEIN", res.to_terminal_format())

    def test_case_6_blocked_by_oauth(self):
        """CASE 6: 'Blocked by OAuth.' -> HUMAN_GATE, ERLEDIGT: NEIN"""
        res = self.engine.classify_and_route("Blocked by OAuth.")
        self.assertEqual(res.message_class, MessageClass.HUMAN_GATE)
        self.assertEqual(res.status, TaskStatus.BLOCKED)
        self.assertFalse(res.erledigt)
        self.assertIn("ERLEDIGT: NEIN", res.to_terminal_format())

    def test_case_7_continuation_directive_weiter(self):
        """CASE 7: 'weiter' -> exactly ONE next safe local task, not standing authorization"""
        res = self.engine.classify_and_route("weiter")
        self.assertEqual(res.message_class, MessageClass.TASK_REQUEST)
        self.assertTrue(res.requires_worker_launch)
        self.assertEqual(res.action_domain, ActionDomain.LOCAL_MACHINE)
        self.assertIn("ONE next safe local action", res.next_step)
        self.assertFalse(res.erledigt)

    def test_case_8_partial_success(self):
        """CASE 8: External agent reports PARTIAL success -> STATUS: PARTIAL, ERLEDIGT: NEIN"""
        res = self.engine.classify_and_route("Partial success: 3 of 5 steps completed.")
        self.assertEqual(res.status, TaskStatus.PARTIAL)
        self.assertFalse(res.erledigt)
        self.assertIn("ERLEDIGT: NEIN", res.to_terminal_format())

    # --- TEAM MODEL TESTS A THROUGH H ---

    def test_a_gemini_on_windows_path(self):
        r"""TEST A: Gemini message containing C:\Users\lol\... -> AGENT GEMINI, HOST WINDOWS"""
        msg = r"Gemini processed files in C:\Users\lol\2026-workspace\project-memory."
        host, agent = detect_host_and_agent(msg)
        self.assertEqual(agent, Agent.GEMINI)
        self.assertEqual(host, Host.WINDOWS)

    def test_b_gemini_on_mac_path(self):
        """TEST B: Gemini message containing /Users/user/... -> AGENT GEMINI, HOST MAC"""
        msg = "Gemini inspected /Users/user/2026-workspace/courier."
        host, agent = detect_host_and_agent(msg)
        self.assertEqual(agent, Agent.GEMINI)
        self.assertEqual(host, Host.MAC)

    def test_c_gemini_without_host_evidence(self):
        """TEST C: Gemini message without host evidence -> HOST UNKNOWN, no guessing"""
        msg = "Gemini finished schema validation."
        host, agent = detect_host_and_agent(msg)
        self.assertEqual(agent, Agent.GEMINI)
        self.assertEqual(host, Host.UNKNOWN)

    def test_d_local_step_done_vs_gesamtaufgabe_blocked(self):
        """TEST D: Windows local step succeeds but remote synchronization remains blocked -> LOCAL_STEP_ERLEDIGT JA, GESAMTAUFGABE_ERLEDIGT NEIN"""
        res = self.engine.classify_and_route(
            "Windows local hardening committed, but GitHub login nötig for remote sync.",
            context={"local_step_done": True, "authenticated": False}
        )
        self.assertTrue(res.local_step_erledigt)
        self.assertFalse(res.gesamtaufgabe_erledigt)
        self.assertFalse(res.erledigt)
        self.assertEqual(res.status, TaskStatus.BLOCKED)
        self.assertIn("LOCAL_STEP_ERLEDIGT: JA", res.to_terminal_format())
        self.assertIn("GESAMTAUFGABE_ERLEDIGT: NEIN", res.to_terminal_format())

    def test_e_cross_machine_single_writer_serialization(self):
        """TEST E: Mac and Windows both request write access to same repository/resource -> serialize, SINGLE_WRITER preserved"""
        repo_resource = "repo:happyhippovip/2026-project-memory:branch:main"
        
        # 1. Windows acquires write lock
        granted_win, msg_win = self.resource_manager.request_access(repo_resource, Host.WINDOWS, is_write=True)
        self.assertTrue(granted_win)
        self.assertEqual(msg_win, "WRITE_LOCK_ACQUIRED")

        # 2. Mac simultaneously requests write lock on SAME resource -> Denied / Serialized
        granted_mac, msg_mac = self.resource_manager.request_access(repo_resource, Host.MAC, is_write=True)
        self.assertFalse(granted_mac)
        self.assertIn("SINGLE_WRITER_CONFLICT", msg_mac)

        # 3. Read-only operation on Mac to same resource -> Permitted
        granted_mac_read, msg_mac_read = self.resource_manager.request_access(repo_resource, Host.MAC, is_write=False)
        self.assertTrue(granted_mac_read)
        self.assertEqual(msg_mac_read, "READ_ONLY_ALLOWED")

        # 4. Windows releases lock, Mac can now acquire write lock
        self.resource_manager.release_access(repo_resource)
        granted_mac_after, msg_mac_after = self.resource_manager.request_access(repo_resource, Host.MAC, is_write=True)
        self.assertTrue(granted_mac_after)
        self.assertEqual(msg_mac_after, "WRITE_LOCK_ACQUIRED")

    def test_f_machine_gate_isolation(self):
        """TEST F: Windows has HUMAN_GATE on GitHub auth while unrelated Mac read-only task exists -> Windows task blocked, unrelated Mac task not globally blocked"""
        win_task = self.engine.classify_and_route("Windows: GitHub auth login nötig.")
        self.assertEqual(win_task.status, TaskStatus.BLOCKED)
        self.assertEqual(win_task.action_domain, ActionDomain.HUMAN_ONLY)

        # Independent Mac read-only task remains completely unblocked
        mac_read_task = self.engine.classify_and_route(
            "Mac read-only inspection: Tests 25/25 PASS, Datei remote verifiziert.",
            context={"authenticated": True}
        )
        self.assertEqual(mac_read_task.status, TaskStatus.DONE)
        self.assertTrue(mac_read_task.erledigt)

    def test_g_connected_capability_routed_to_chief(self):
        """TEST G: Chief has connected GitHub read capability -> remote inspection routed to Chief rather than Windows"""
        res = self.engine.classify_and_route(
            "Windows sagt: ChatGPT soll das über den verbundenen GitHub machen.",
            context={"has_connected_tool": True}
        )
        self.assertEqual(res.message_class, MessageClass.DELEGATION_TO_CHIEF)
        self.assertEqual(res.action_domain, ActionDomain.CONNECTED_REMOTE)
        self.assertIn("Chief executes task via connected tool", res.next_step)

    def test_h_unpushed_local_bytes_never_claimed_by_chief(self):
        """TEST H: Unpushed files exist only on Windows -> Chief must not claim access to those local bytes, route to Windows"""
        res = self.engine.classify_and_route(
            "Chief soll unpushed local commit auf Windows pushen.",
            context={"requires_local_bytes": True}
        )
        self.assertEqual(res.action_domain, ActionDomain.LOCAL_MACHINE)
        self.assertIn("Unpushed bytes exist exclusively on local machine", res.evidence)
        self.assertIn("Route local operation to machine-local agent", res.next_step)

if __name__ == '__main__':
    unittest.main(verbosity=2)
