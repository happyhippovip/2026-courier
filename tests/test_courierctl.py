#!/usr/bin/env python3
"""Tests for tools/courierctl/courierctl.py.

Verifies CLI exit codes on HTTP success and error conditions.
"""

from __future__ import annotations

import sys
import unittest
from unittest import mock

from tools.courierctl import courierctl


class TestCourierctlExitCodes(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict("os.environ", {
            "COURIER_API_KEY": "test-key-123",
            "COURIER_SERVER": "http://127.0.0.1:8080"
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @mock.patch("requests.get")
    def test_health_success_exit_code_zero(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_resp

        with mock.patch.object(sys, "argv", ["courierctl", "health"]):
            with self.assertRaises(SystemExit) as cm:
                courierctl.main()
            self.assertEqual(cm.exception.code, 0)

    @mock.patch("requests.get")
    def test_health_error_exit_code_non_zero(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Internal Server Crash"}
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_resp

        with mock.patch.object(sys, "argv", ["courierctl", "health"]):
            with self.assertRaises(SystemExit) as cm:
                courierctl.main()
            self.assertEqual(cm.exception.code, 1)

    @mock.patch("requests.post")
    def test_submit_success_exit_code_zero(self, mock_post):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"goal_id": "goal-999"}
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_resp

        with mock.patch.object(sys, "argv", ["courierctl", "submit", "test goal"]):
            with self.assertRaises(SystemExit) as cm:
                courierctl.main()
            self.assertEqual(cm.exception.code, 0)

    @mock.patch("requests.post")
    def test_submit_error_exit_code_one(self, mock_post):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Bad Request"}
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_resp

        with mock.patch.object(sys, "argv", ["courierctl", "submit", "test goal"]):
            with self.assertRaises(SystemExit) as cm:
                courierctl.main()
            self.assertEqual(cm.exception.code, 1)

    @mock.patch("requests.get")
    def test_workers_404_exit_code_one(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_get.return_value = mock_resp

        with mock.patch.object(sys, "argv", ["courierctl", "workers"]):
            with self.assertRaises(SystemExit) as cm:
                courierctl.main()
            self.assertEqual(cm.exception.code, 1)

    @mock.patch("requests.get")
    def test_wall_404_exit_code_one(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_get.return_value = mock_resp

        with mock.patch.object(sys, "argv", ["courierctl", "wall"]):
            with self.assertRaises(SystemExit) as cm:
                courierctl.main()
            self.assertEqual(cm.exception.code, 1)

    @mock.patch("requests.get")
    def test_status_error_exit_code_one(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 503
        mock_resp.json.return_value = {"error": "Unavailable"}
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_resp

        with mock.patch.object(sys, "argv", ["courierctl", "status"]):
            with self.assertRaises(SystemExit) as cm:
                courierctl.main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
