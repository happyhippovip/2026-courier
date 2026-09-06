import unittest
import threading
import time
import io
import sys
from http.server import HTTPServer
from social_platform.core.database import SocialDatabase
import social_platform.api.server as api_server
from social_platform.client.cli import SocialCLI


class TestSocialCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SocialDatabase(":memory:")
        api_server.db = cls.db

        cls.server = HTTPServer(("127.0.0.1", 0), api_server.SocialAPIHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.cli = SocialCLI(base_url=self.base_url)

    def _run_cli(self, args):
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
        try:
            full_args = ["--base-url", self.base_url] + args
            code = self.cli.run(full_args)
            out = sys.stdout.getvalue()
            err = sys.stderr.getvalue()
            return code, out, err
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

    def test_cli_user_and_post_flow(self):
        # 1. Create user
        code, out, err = self._run_cli([
            "user", "create",
            "--username", "cli_user1",
            "--id", "u_cli1",
            "--bio", "Command line enthusiast",
            "--json"
        ])
        self.assertEqual(code, 0)
        self.assertIn("cli_user1", out)

        # 2. Get user
        code, out, err = self._run_cli(["user", "get", "u_cli1", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("Command line enthusiast", out)

        # 3. Create post
        code, out, err = self._run_cli([
            "post", "create",
            "--author-id", "u_cli1",
            "--content", "Posted through social-cli #terminal",
            "--tags", "terminal", "cli",
            "--json"
        ])
        self.assertEqual(code, 0)
        self.assertIn("Posted through social-cli", out)

        # 4. View feed
        code, out, err = self._run_cli(["feed", "u_cli1", "--mode", "chronological", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("Posted through social-cli", out)

    def test_cli_community_and_social(self):
        # Create users
        self._run_cli(["user", "create", "--username", "comm_admin", "--id", "u_comm_admin"])
        self._run_cli(["user", "create", "--username", "comm_user", "--id", "u_comm_user"])

        # Follow
        code, out, err = self._run_cli(["social", "follow", "--follower", "u_comm_user", "--followed", "u_comm_admin"])
        self.assertEqual(code, 0)

        # Create community
        code, out, err = self._run_cli([
            "community", "create",
            "--name", "CLI Developers",
            "--creator", "u_comm_admin",
            "--desc", "All things CLI",
            "--json"
        ])
        self.assertEqual(code, 0)
        self.assertIn("CLI Developers", out)

        # List communities
        code, out, err = self._run_cli(["community", "list", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("CLI Developers", out)

    def test_cli_search(self):
        code, out, err = self._run_cli(["search", "CLI", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("query", out)


if __name__ == "__main__":
    unittest.main()
