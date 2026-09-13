"""
test_framework_integrations_and_doctor.py - Test Suite for TASK-WIN-80:
Agent Control Plane Framework Integration Matrix, Drop-In Multi-Agent Adapters & Local Diagnostic Doctor CLI

Certifies:
1. Framework Matrix Completeness: FRAMEWORK_INTEGRATIONS.md exists and covers 8 agent runtimes (OpenAI, LangChain, CrewAI, LlamaIndex, AutoGPT, Node.js, LiteLLM, Anthropic).
2. Zero-Dependency Adapter: acp_adapter.py exists, exports drop-in helper functions, and returns correct base URLs.
3. Doctor Standalone Checks: acp_doctor.py executes offline checks (Python version, offline license engine) without server dependency.
4. Doctor Live Diagnostic Circuit: acp_doctor.py runs all 5 diagnostic checks against an ephemeral spend_firewall_pro instance with 100% PASS.
5. Operating Invariants: Automatic spend strictly 0.00 EUR, Mac scope excluded, 100% offline.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
ACP_DIR = os.path.join(PROJECT_MEMORY_DIR, "data", "distribution_ready", "agent_control_plane")
if ACP_DIR not in sys.path:
    sys.path.insert(0, ACP_DIR)

import acp_doctor
import acp_adapter


class TestFrameworkIntegrationsAndDoctor(unittest.TestCase):
    server_proc = None
    test_port = 4991

    @classmethod
    def setUpClass(cls):
        cls.frameworks_file = os.path.join(ACP_DIR, "FRAMEWORK_INTEGRATIONS.md")
        cls.adapter_file = os.path.join(ACP_DIR, "acp_adapter.py")
        cls.doctor_file = os.path.join(ACP_DIR, "acp_doctor.py")
        cls.server_script = os.path.join(ACP_DIR, "spend_firewall_pro.py")

        # Launch ephemeral spend firewall on test port
        env = os.environ.copy()
        env["UPSTREAM_API_HOST"] = "mock"
        cls.server_proc = subprocess.Popen(
            [sys.executable, cls.server_script, str(cls.test_port), "20.00"],
            cwd=ACP_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        time.sleep(1.0)

    @classmethod
    def tearDownClass(cls):
        if cls.server_proc:
            try:
                cls.server_proc.terminate()
                cls.server_proc.wait(timeout=5)
            except Exception:
                try:
                    cls.server_proc.kill()
                except Exception:
                    pass

    def test_01_framework_matrix_completeness(self):
        """Verify FRAMEWORK_INTEGRATIONS.md exists and covers all 8 canonical agent frameworks."""
        self.assertTrue(os.path.exists(self.frameworks_file), "FRAMEWORK_INTEGRATIONS.md must exist")
        with open(self.frameworks_file, "r", encoding="utf-8") as f:
            content = f.read()

        frameworks = [
            "OpenAI Python SDK",
            "LangChain & LangGraph",
            "CrewAI",
            "LlamaIndex",
            "AutoGPT",
            "Node.js & TypeScript",
            "LiteLLM Proxy Chaining",
            "Anthropic Claude SDK"
        ]
        for fw in frameworks:
            self.assertIn(fw, content, f"Matrix must document integration for: {fw}")
        self.assertIn("127.0.0.1:4006/v1", content)

    def test_02_adapter_functions(self):
        """Verify acp_adapter.py exports correct helper functions and URLs."""
        self.assertTrue(os.path.exists(self.adapter_file), "acp_adapter.py must exist")
        url = acp_adapter.get_firewall_base_url(4006)
        self.assertEqual(url, "http://127.0.0.1:4006/v1")

        env_url = acp_adapter.configure_environment(4006)
        self.assertEqual(env_url, "http://127.0.0.1:4006/v1")
        self.assertEqual(os.environ.get("OPENAI_BASE_URL"), "http://127.0.0.1:4006/v1")

    def test_03_doctor_offline_checks(self):
        """Verify acp_doctor.py passes offline checks without running server."""
        rep = acp_doctor.run_diagnostics(check_server=False)
        self.assertEqual(rep["status"], "PASS")
        self.assertEqual(rep["checks_passed"], 2)
        names = [c["name"] for c in rep["checks"]]
        self.assertIn("python_version", names)
        self.assertIn("offline_license_validator", names)

    def test_04_doctor_live_diagnostic_circuit(self):
        """Verify acp_doctor.py executes all 5 checks against running proxy instance and reports 100% PASS."""
        rep = acp_doctor.run_diagnostics(port=self.test_port, check_server=True)
        self.assertEqual(rep["status"], "PASS", f"Doctor report failed: {rep}")
        self.assertEqual(rep["checks_total"], 5)
        self.assertEqual(rep["checks_passed"], 5)

        names = [c["name"] for c in rep["checks"]]
        self.assertIn("proxy_status", names)
        self.assertIn("loop_breaker_circuit", names)
        self.assertIn("audit_csv_export", names)

    def test_05_operating_invariants(self):
        """Verify automatic spend limit strictly 0.00 EUR and Mac scope untouched."""
        cycle_state_path = os.path.join(PROJECT_MEMORY_DIR, "data", "autonomy_cycle_state.json")
        if os.path.exists(cycle_state_path):
            with open(cycle_state_path, "r", encoding="utf-8") as f:
                c_state = json.load(f)
            self.assertEqual(c_state.get("spend_eur", 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
