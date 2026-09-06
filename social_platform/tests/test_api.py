import unittest
import json
import io
from datetime import datetime
from urllib.parse import urlencode

from social_platform.core.models import (
    User, Discussion, Community, Channel, ModerationReport,
    CommunityMember, DirectMessage, Course, StudyGroup
)
from social_platform.core.database import SocialDatabase
import social_platform.api.server as api_server


class MockRequest:
    def __init__(self, method="GET", path="/", body=None):
        self.method = method
        self.path = path
        self.body_bytes = json.dumps(body).encode("utf-8") if isinstance(body, dict) else (body or b"")

    def make_file(self):
        return io.BytesIO(self.body_bytes)


class TestSocialAPI(unittest.TestCase):
    def setUp(self):
        self.db = SocialDatabase(":memory:")
        api_server.db = self.db

    def _call_api(self, method, path, body=None):
        req = MockRequest(method=method, path=path, body=body)
        handler = api_server.SocialAPIHandler.__new__(api_server.SocialAPIHandler)
        handler.path = path
        handler.command = method
        handler.headers = {"Content-Length": str(len(req.body_bytes))} if body else {}
        handler.rfile = io.BytesIO(req.body_bytes)
        handler.wfile = io.BytesIO()

        handler._captured_status = None
        handler._captured_headers = {}

        def mock_send_response(status):
            handler._captured_status = status

        def mock_send_header(k, v):
            handler._captured_headers[k] = v

        def mock_end_headers():
            pass

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers

        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()
        elif method == "PUT":
            handler.do_PUT()
        elif method == "DELETE":
            handler.do_DELETE()

        raw_output = handler.wfile.getvalue().decode("utf-8")
        json_resp = json.loads(raw_output) if raw_output else None
        return handler._captured_status, json_resp

    def test_user_creation_and_profile_api(self):
        status, resp = self._call_api("POST", "/users", {
            "id": "u100",
            "username": "ada_lovelace",
            "bio": "First programmer",
            "is_publicly_discoverable": True
        })
        self.assertIn(status, (200, 201))
        self.assertEqual(resp.get("username"), "ada_lovelace")

        status, resp = self._call_api("GET", "/users/u100")
        self.assertEqual(status, 200)
        self.assertEqual(resp.get("bio"), "First programmer")

        status, resp = self._call_api("GET", "/users?q=lovelace&public_only=false")
        self.assertEqual(status, 200)
        self.assertTrue(any(u.get("username") == "ada_lovelace" for u in resp))

    def test_discussion_and_endorsement_api(self):
        self._call_api("POST", "/users", {"id": "u1", "username": "alice"})

        status, resp = self._call_api("POST", "/discussions", {
            "id": "d1",
            "author_id": "u1",
            "content": "Exploring algorithmic fairness and privacy #ethics"
        })
        self.assertIn(status, (200, 201))
        self.assertEqual(resp.get("id"), "d1")

        status, resp = self._call_api("POST", "/discussions/d1/endorse", {"user_id": "u2"})
        self.assertIn(status, (200, 201))
        self.assertGreaterEqual(resp.get("value_endorsements", 0), 1)

        status, resp = self._call_api("GET", "/discussions/d1")
        self.assertEqual(status, 200)
        self.assertEqual(resp.get("value_endorsements"), 1)

    def test_direct_messaging_workflow(self):
        self._call_api("POST", "/users", {"id": "u1", "username": "alice"})
        self._call_api("POST", "/users", {"id": "u2", "username": "bob"})

        status, resp = self._call_api("POST", "/dms", {
            "id": "m1",
            "sender_id": "u1",
            "recipient_id": "u2",
            "content": "Hi Bob, check out the study guide!"
        })
        self.assertIn(status, (200, 201))

        status, msgs = self._call_api("GET", "/users/u2/conversations/u1")
        self.assertEqual(status, 200)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["content"], "Hi Bob, check out the study guide!")

    def test_community_lifecycle_api(self):
        self._call_api("POST", "/users", {"id": "u1", "username": "alice"})
        self._call_api("POST", "/users", {"id": "u2", "username": "bob"})

        status, comm = self._call_api("POST", "/communities", {
            "id": "c1",
            "name": "Machine Learning Research",
            "creator_id": "u1",
            "description": "Collaborative ML discussions",
            "is_private": False
        })
        self.assertIn(status, (200, 201))

        status, join_resp = self._call_api("POST", "/communities/c1/join", {
            "user_id": "u2"
        })
        self.assertIn(status, (200, 201))

        status, ch = self._call_api("POST", "/communities/c1/channels", {
            "id": "ch1",
            "name": "papers",
            "description": "Weekly paper discussion"
        })
        self.assertIn(status, (200, 201))

        status, disc = self._call_api("POST", "/discussions", {
            "id": "d2",
            "author_id": "u2",
            "content": "New paper on Transformers #deeplearning",
            "community_id": "c1",
            "channel_id": "ch1"
        })
        self.assertIn(status, (200, 201))

        status, feed = self._call_api("GET", "/users/u1/feed/community?community_id=c1")
        self.assertEqual(status, 200)
        self.assertTrue(any(item.get("id") == "d2" for item in feed))

    def test_moderation_and_appeal_workflow(self):
        self._call_api("POST", "/users", {"id": "u1", "username": "alice"})
        self._call_api("POST", "/users", {"id": "u2", "username": "bob"})
        self._call_api("POST", "/discussions", {"id": "d10", "author_id": "u2", "content": "Spam message"})

        status, report = self._call_api("POST", "/reports", {
            "id": "r1",
            "reporter_id": "u1",
            "target_type": "discussion",
            "target_id": "d10",
            "reason": "spam",
            "category": "spam"
        })
        self.assertIn(status, (200, 201))

        status, resolve_resp = self._call_api("POST", "/reports/r1/resolve", {
            "action": "hide",
            "admin_id": "u1",
            "reason": "Confirmed spam violation"
        })
        self.assertIn(status, (200, 201))

        status, disc = self._call_api("GET", "/discussions/d10")
        self.assertEqual(status, 200)
        self.assertTrue(disc.get("is_hidden"))

        status, appeal = self._call_api("POST", "/appeals", {
            "id": "ap1",
            "target_type": "discussion",
            "target_id": "d10",
            "appellant_id": "u2",
            "reason": "This was a false positive, please review context"
        })
        self.assertIn(status, (200, 201))


if __name__ == "__main__":
    unittest.main()
