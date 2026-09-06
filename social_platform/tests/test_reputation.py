import unittest
import json
import io
from datetime import datetime, timedelta

from social_platform.core.models import (
    User, Discussion, Course, CourseEnrollment, CourseResource,
    StudyGroup, StudyGroupMember, Endorsement,
    DomainReputation, DomainLeaderboardEntry, StudySpaceReputation,
    EndorsementCategory, ReputationBadge, FeedItem
)
from social_platform.core.database import SocialDatabase
from social_platform.core.feed import (
    generate_weighted_value_feed, generate_domain_reputation_feed,
    generate_feed, FeedService, FeedMode
)
from social_platform.api.server import SocialAPIHandler
import social_platform.api.server as api_server
from social_platform.client.client import SocialPlatformClient
from social_platform.client.session import UserSession
from social_platform.client.cli import SocialCLI


class MockRequest:
    def __init__(self, method="GET", path="/", body=None):
        self.method = method
        self.path = path
        self.body_bytes = json.dumps(body).encode("utf-8") if isinstance(body, dict) else (body or b"")


class TestWeightedEndorsementsAndReputation(unittest.TestCase):
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

    def test_endorser_weight_calculation(self):
        # 1. Base user weight
        u1 = User(id="u1", username="student1")
        self.db.create_user(u1)
        base_w = self.db.calculate_endorser_weight("u1", domain="computer_science")
        self.assertGreaterEqual(base_w, 1.0)

        # 2. Instructor in a course
        course = Course(id="c101", code="CS101", title="Algorithms", instructor="u_prof")
        u_prof = User(id="u_prof", username="professor")
        self.db.create_user(u_prof)
        self.db.create_course(course)
        self.db.enroll_user_in_course("c101", "u_prof", role="instructor")

        prof_w = self.db.calculate_endorser_weight("u_prof", target_course_id="c101")
        self.assertGreaterEqual(prof_w, 3.0)  # base (1.0) + instructor (2.0) = 3.0

        # 3. TA in a course
        u_ta = User(id="u_ta", username="ta_user")
        self.db.create_user(u_ta)
        self.db.enroll_user_in_course("c101", "u_ta", role="teaching_assistant")
        ta_w = self.db.calculate_endorser_weight("u_ta", target_course_id="c101")
        self.assertGreaterEqual(ta_w, 2.5)  # base (1.0) + TA (1.5) = 2.5

    def test_discussion_weighted_endorsements_and_reputation_lifecycle(self):
        u_author = User(id="u_auth", username="author1", interests=["physics", "quantum"])
        u_endorser = User(id="u_end", username="endorser1")
        self.db.create_user(u_author)
        self.db.create_user(u_endorser)

        d = Discussion(
            id="d_phys1",
            author_id="u_auth",
            content="Superconductivity breakthrough in twisted bilayer graphene",
            tags=["physics", "quantum"]
        )
        self.db.create_discussion(d)

        # Endorse discussion with explicit domain & category
        success = self.db.endorse_discussion(
            discussion_id="d_phys1",
            actor_id="u_end",
            weight=2.5,
            domain="physics",
            value_category=EndorsementCategory.RESEARCH,
            comment="Rigorous derivation and experimental validation"
        )
        self.assertTrue(success)

        # Verify discussion stats
        disc = self.db.get_discussion("d_phys1")
        self.assertEqual(disc.value_endorsements, 1)
        self.assertAlmostEqual(disc.weighted_value_endorsements, 2.5)
        self.assertEqual(disc.domain, "physics")

        # Verify endorsement record
        endorsements = self.db.get_discussion_endorsements("d_phys1")
        self.assertEqual(len(endorsements), 1)
        self.assertEqual(endorsements[0].domain, "physics")
        self.assertEqual(endorsements[0].value_category, EndorsementCategory.RESEARCH)
        self.assertAlmostEqual(endorsements[0].weight, 2.5)

        # Verify author domain reputation updated
        rep = self.db.get_user_domain_reputation("u_auth", "physics")
        self.assertIsNotNone(rep)
        self.assertEqual(rep.domain, "physics")
        self.assertGreater(rep.reputation_score, 0.0)
        self.assertEqual(rep.total_endorsements_received, 1)
        self.assertAlmostEqual(rep.weighted_endorsements_received, 2.5)

    def test_course_resource_endorsement_and_study_space_reputation(self):
        u_prof = User(id="u_p", username="prof")
        u_student = User(id="u_s", username="stud")
        self.db.create_user(u_prof)
        self.db.create_user(u_student)

        course = Course(id="c_math", code="MATH201", title="Linear Algebra", institution="MIT")
        self.db.create_course(course)

        res = CourseResource(
            id="r_notes",
            course_id="c_math",
            uploader_id="u_p",
            title="Eigenvalues Summary Cheat Sheet",
            url="https://notes.mit.edu/eigen.pdf",
            resource_type="cheat_sheet",
            tags=["linear_algebra", "math"]
        )
        self.db.create_course_resource(res)

        # Endorse the resource
        success = self.db.endorse_resource(
            resource_id="r_notes",
            actor_id="u_s",
            weight=3.0,
            domain="mathematics",
            value_category=EndorsementCategory.CLARITY,
            comment="Crystal clear decomposition"
        )
        self.assertTrue(success)

        # Check resource stats
        updated_res = self.db.get_course_resource("r_notes")
        self.assertEqual(updated_res.endorsements_count, 1)
        self.assertAlmostEqual(updated_res.weighted_endorsements_count, 3.0)

        # Check course aggregate reputation
        c_rep = self.db.get_course_reputation_metrics("c_math")
        self.assertIsNotNone(c_rep)
        self.assertEqual(c_rep.space_id, "c_math")
        self.assertGreaterEqual(c_rep.total_endorsements, 1)
        self.assertGreaterEqual(c_rep.weighted_endorsements, 3.0)

    def test_domain_leaderboard(self):
        u1 = User(id="u_lead1", username="turing")
        u2 = User(id="u_lead2", username="church")
        self.db.create_user(u1)
        self.db.create_user(u2)

        # Create discussions
        d1 = Discussion(id="d_comp1", author_id="u_lead1", content="Computability on Turing Machines")
        d2 = Discussion(id="d_comp2", author_id="u_lead2", content="Lambda Calculus Formalism")
        self.db.create_discussion(d1)
        self.db.create_discussion(d2)

        # Endorse d1 with higher weight
        self.db.endorse_discussion("d_comp1", actor_id="u_lead2", weight=10.0, domain="computer_science")
        self.db.endorse_discussion("d_comp2", actor_id="u_lead1", weight=5.0, domain="computer_science")

        leaderboard = self.db.get_top_contributors_by_domain("computer_science", limit=10)
        self.assertGreaterEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0].user_id, "u_lead1")
        self.assertEqual(leaderboard[0].rank, 1)
        self.assertEqual(leaderboard[1].user_id, "u_lead2")
        self.assertEqual(leaderboard[1].rank, 2)

    def test_feed_weighted_value_and_domain_ranking(self):
        u_viewer = User(id="u_view", username="viewer")
        u_top = User(id="u_top", username="top_author")
        u_mid = User(id="u_mid", username="mid_author")
        self.db.create_user(u_viewer)
        self.db.create_user(u_top)
        self.db.create_user(u_mid)

        now = datetime.utcnow()
        d_top = Discussion(id="d_t", author_id="u_top", content="P vs NP Deep Dive", created_at=now - timedelta(hours=2))
        d_mid = Discussion(id="d_m", author_id="u_mid", content="Sorting algorithms", created_at=now - timedelta(hours=1))
        self.db.create_discussion(d_top)
        self.db.create_discussion(d_mid)

        # Endorse d_top with high weight
        self.db.endorse_discussion("d_t", actor_id="u_viewer", weight=8.0, domain="computer_science")
        self.db.endorse_discussion("d_m", actor_id="u_viewer", weight=2.0, domain="computer_science")

        # Test weighted value feed
        feed_service = FeedService(self.db)
        weighted_feed = feed_service.get_weighted_value_feed("u_view")
        self.assertEqual(len(weighted_feed), 2)
        self.assertEqual(weighted_feed[0].id, "d_t")
        self.assertEqual(weighted_feed[1].id, "d_m")
        self.assertEqual(weighted_feed[0].mode, FeedMode.WEIGHTED_VALUE)
        self.assertTrue(any("mode:weighted_value" in t for t in weighted_feed[0].explanation_tags))

        # Test domain reputation feed
        domain_feed = feed_service.get_domain_reputation_feed("u_view", domain="computer_science")
        self.assertEqual(len(domain_feed), 2)
        self.assertEqual(domain_feed[0].id, "d_t")
        self.assertEqual(domain_feed[0].mode, FeedMode.DOMAIN_REPUTATION)

    def test_rest_api_reputation_and_endorsements(self):
        self._call_api("POST", "/users", {"id": "u_api1", "username": "einstein"})
        self._call_api("POST", "/users", {"id": "u_api2", "username": "bohr"})

        # Post discussion
        status, d_resp = self._call_api("POST", "/discussions", {
            "id": "d_relativity",
            "author_id": "u_api1",
            "content": "General Theory of Relativity and Gravitational Waves"
        })
        self.assertIn(status, (200, 201))

        # Endorse via API
        status, end_resp = self._call_api("POST", "/discussions/d_relativity/endorse", {
            "user_id": "u_api2",
            "weight": 5.0,
            "domain": "physics",
            "value_category": "rigor",
            "comment": "Profound foundation"
        })
        self.assertEqual(status, 200)

        # Get discussion endorsements
        status, ends_list = self._call_api("GET", "/discussions/d_relativity/endorsements")
        self.assertEqual(status, 200)
        self.assertEqual(len(ends_list), 1)
        self.assertEqual(ends_list[0]["domain"], "physics")

        # Get user reputation
        status, rep_resp = self._call_api("GET", "/users/u_api1/reputation/physics")
        self.assertEqual(status, 200)
        self.assertEqual(rep_resp["domain"], "physics")
        self.assertGreater(rep_resp["reputation_score"], 0.0)

        # Get domain leaderboard
        status, lead_resp = self._call_api("GET", "/reputation/leaderboard/physics")
        self.assertEqual(status, 200)
        self.assertTrue(any(e["user_id"] == "u_api1" for e in lead_resp))

        # Get weighted feed via API
        status, feed_resp = self._call_api("GET", "/feed/u_api2?mode=weighted_value")
        self.assertEqual(status, 200)
        self.assertTrue(any(item["id"] == "d_relativity" for item in feed_resp))

    def test_client_and_session_layer(self):
        def mock_caller(method, path, params=None, body=None):
            full_path = path
            if params:
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                if query:
                    full_path = f"{path}?{query}"
            status, resp = self._call_api(method, full_path, body=body)
            if status >= 400:
                raise Exception(f"API Error {status}: {resp}")
            return resp

        client = SocialPlatformClient(handler_caller=mock_caller)
        client.create_user(username="newton", user_id="u_newton")
        client.create_user(username="hooke", user_id="u_hooke")

        session_newton = client.session("u_newton")
        session_hooke = client.session("u_hooke")

        post_res = session_newton.post("Philosophiae Naturalis Principia Mathematica", discussion_id="d_principia")
        self.assertEqual(post_res["id"], "d_principia")

        session_hooke.endorse(
            "d_principia",
            weight=4.0,
            domain="optics_and_gravity",
            value_category="breakthrough"
        )

        rep = session_newton.get_domain_reputation("optics_and_gravity")
        self.assertEqual(rep["domain"], "optics_and_gravity")
        self.assertGreater(rep["reputation_score"], 0.0)

        board = client.get_domain_leaderboard("optics_and_gravity")
        self.assertGreaterEqual(len(board), 1)
        self.assertEqual(board[0]["user_id"], "u_newton")

    def test_cli_integration(self):
        cli = SocialCLI()
        def mock_caller(method, path, params=None, body=None):
            full_path = path
            if params:
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                if query:
                    full_path = f"{path}?{query}"
            status, resp = self._call_api(method, full_path, body=body)
            return resp

        cli.client.handler_caller = mock_caller

        code = cli.run(["user", "create", "--username", "gauss", "--id", "u_gauss"])
        self.assertEqual(code, 0)

        code = cli.run(["post", "create", "--author-id", "u_gauss", "--content", "Disquisitiones Arithmeticae", "--id", "d_gauss"])
        self.assertEqual(code, 0)

        code = cli.run(["post", "endorse", "d_gauss", "--user-id", "u_gauss", "--weight", "5.0", "--domain", "number_theory"])
        self.assertEqual(code, 0)

        code = cli.run(["reputation", "user", "u_gauss", "--domain", "number_theory", "--json"])
        self.assertEqual(code, 0)

        code = cli.run(["reputation", "top", "--domain", "number_theory", "--json"])
        self.assertEqual(code, 0)

        code = cli.run(["feed", "u_gauss", "--mode", "weighted_value", "--json"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

    def test_reputation_summary(self):
        u1 = User(id="u_sum1", username="feynman")
        self.db.create_user(u1)
        
        # Endorse some things
        d1 = Discussion(id="d_sum1", author_id="u_sum1", content="QED")
        self.db.create_discussion(d1)
        self.db.endorse_discussion("d_sum1", actor_id="u_sum2", weight=10.0, domain="physics")
        self.db.endorse_discussion("d_sum1", actor_id="u_sum3", weight=5.0, domain="physics")
        
        summary = self.db.get_user_reputation_summary("u_sum1")
        self.assertEqual(summary["user_id"], "u_sum1")
        self.assertIn("domains", summary)
        self.assertGreaterEqual(summary["total_reputation_score"], 15.0)

        # Test via API
        status, resp = self._call_api("GET", "/reputation/summary/u_sum1")
        self.assertEqual(status, 200)
        self.assertEqual(resp["user_id"], "u_sum1")
        self.assertGreaterEqual(resp["total_reputation_score"], 15.0)

