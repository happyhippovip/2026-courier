import unittest
import threading
import time
from http.server import HTTPServer
from social_platform.core.database import SocialDatabase
import social_platform.api.server as api_server
from social_platform.client import (
    SocialPlatformClient,
    SocialClient,
    UserSession,
    NotFoundError,
    ValidationError,
    APIError,
    ClientError
)


class TestSocialClientLiveHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create fresh in-memory database
        cls.db = SocialDatabase(":memory:")
        api_server.db = cls.db

        # Bind to port 0 to get an ephemeral free port
        cls.server = HTTPServer(("127.0.0.1", 0), api_server.SocialAPIHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        # Start server in background thread
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.client = SocialPlatformClient(base_url=self.base_url)

    def test_user_lifecycle_and_privacy(self):
        # 1. Create user
        user = self.client.create_user(
            username="marie_curie",
            user_id="u_curie",
            bio="Physicist and Chemist",
            university="Sorbonne",
            interests=["physics", "radiology"],
            is_publicly_discoverable=True
        )
        self.assertEqual(user["username"], "marie_curie")
        self.assertEqual(user["id"], "u_curie")

        # 2. Get user & profile
        fetched = self.client.get_user("u_curie")
        self.assertEqual(fetched["university"], "Sorbonne")

        profile = self.client.get_profile("u_curie")
        self.assertEqual(profile["bio"], "Physicist and Chemist")

        # 3. Search users (while public)
        results = self.client.search_users(query="curie", public_only=False)
        self.assertTrue(any(u["id"] == "u_curie" for u in results))

        # 4. Update profile
        updated = self.client.update_profile("u_curie", bio="Two-time Nobel Laureate")
        self.assertEqual(updated["bio"], "Two-time Nobel Laureate")

        # 5. Privacy settings
        privacy = self.client.get_privacy_settings("u_curie")
        self.assertEqual(privacy["visibility"], "public")

        updated_priv = self.client.update_privacy("u_curie", visibility="connections_only", dm_privacy="connections_only")
        self.assertEqual(updated_priv["visibility"], "connections_only")

        # 6. Data export
        export = self.client.export_user_data("u_curie")
        self.assertIn("user", export)
        self.assertEqual(export["user"]["id"], "u_curie")

    def test_content_lifecycle_feed_and_endorsements(self):
        # Create users
        self.client.create_user(username="author1", user_id="u_auth1")
        self.client.create_user(username="reader1", user_id="u_read1")

        # Create discussion
        post = self.client.create_discussion(
            author_id="u_auth1",
            content="Breakthrough discovery in radiation #physics #science",
            tags=["physics", "research"],
            discussion_id="d_rad1"
        )
        self.assertEqual(post["id"], "d_rad1")
        self.assertEqual(post["author_id"], "u_auth1")

        # Reader follows author
        self.client.follow("u_read1", "u_auth1")
        connections = self.client.get_connections("u_read1")
        self.assertTrue(any(c.get("followed_id") == "u_auth1" for c in connections))

        # Endorse post
        end_resp = self.client.endorse_discussion("d_rad1", "u_read1")
        self.assertGreaterEqual(end_resp.get("value_endorsements", 0), 1)

        # Reply to post
        reply = self.client.reply("d_rad1", author_id="u_read1", content="Fascinating results!")
        self.assertEqual(reply["parent_id"], "d_rad1")

        replies = self.client.get_replies("d_rad1")
        self.assertTrue(any(r["content"] == "Fascinating results!" for r in replies))

        # Check following feed
        feed = self.client.get_following_feed("u_read1")
        self.assertTrue(any(item.get("id") == "d_rad1" for item in feed))

    def test_communities_and_channels_workflow(self):
        self.client.create_user(username="founder", user_id="u_founder")
        self.client.create_user(username="member", user_id="u_member")

        # Create public community
        comm = self.client.create_community(
            name="Quantum Computing Research",
            creator_id="u_founder",
            description="Frontiers of QC",
            is_private=False,
            community_id="c_qc"
        )
        self.assertEqual(comm["id"], "c_qc")

        # Member joins
        join_res = self.client.join_community("c_qc", "u_member")
        self.assertIn(join_res.get("status", "joined"), ("joined", "success", "member"))

        # Create channel
        chan = self.client.create_channel("c_qc", name="algorithms", description="QC Algorithms", channel_id="ch_algo")
        self.assertEqual(chan["name"], "algorithms")

        channels = self.client.get_channels("c_qc")
        self.assertTrue(any(c["id"] == "ch_algo" for c in channels))

        # Post inside channel
        chan_post = self.client.create_discussion(
            author_id="u_member",
            content="Grover search speedups #quantum",
            community_id="c_qc",
            channel_id="ch_algo",
            discussion_id="d_qc1"
        )
        self.assertEqual(chan_post["channel_id"], "ch_algo")

        # Community feed
        comm_feed = self.client.get_community_feed("u_member", "c_qc")
        self.assertTrue(any(item.get("id") == "d_qc1" for item in comm_feed))

    def test_academic_spaces_and_study_groups(self):
        self.client.create_user(username="student1", user_id="u_stud1")
        self.client.create_user(username="student2", user_id="u_stud2")

        # Create course
        course = self.client.create_course(
            code="CS501",
            title="Advanced Machine Learning",
            institution="TechUniversity",
            term="Fall 2026",
            instructor="Prof. Turing",
            course_id="crs_cs501"
        )
        self.assertEqual(course["code"], "CS501")

        # Enroll students
        self.client.enroll_course("crs_cs501", "u_stud1", role="student", verified=True)
        self.client.enroll_course("crs_cs501", "u_stud2", role="student", verified=True)

        user_courses = self.client.get_user_courses("u_stud1")
        self.assertTrue(any(c["id"] == "crs_cs501" for c in user_courses))

        # Classmates
        classmates = self.client.get_verified_classmates("crs_cs501", "u_stud1")
        self.assertTrue(any(cm["id"] == "u_stud2" for cm in classmates))

        # Add study resource
        resource = self.client.add_course_resource(
            course_id="crs_cs501",
            uploader_id="u_stud1",
            title="Lecture 1 Summary",
            url="https://notes.edu/cs501/lec1.pdf",
            resource_type="note"
        )
        self.assertEqual(resource["title"], "Lecture 1 Summary")

        # Create and join study group
        sg = self.client.create_study_group(
            course_id="crs_cs501",
            name="Weekend Problem Solvers",
            creator_id="u_stud1",
            institution="TechUniversity",
            group_id="sg_ps1"
        )
        self.assertEqual(sg["name"], "Weekend Problem Solvers")

        self.client.join_study_group("sg_ps1", "u_stud2")
        members = self.client.get_study_group_members("sg_ps1")
        self.assertTrue(any(m["user_id"] == "u_stud2" for m in members))

    def test_direct_messaging_and_unread_counts(self):
        self.client.create_user(username="chatter1", user_id="u_chat1")
        self.client.create_user(username="chatter2", user_id="u_chat2")

        # Send DM
        msg = self.client.send_dm(
            sender_id="u_chat1",
            recipient_id="u_chat2",
            content="Hey! Are you studying for the midterm?",
            message_id="msg_midterm1"
        )
        self.assertEqual(msg["content"], "Hey! Are you studying for the midterm?")

        # Check conversations
        convs = self.client.get_conversations("u_chat2")
        self.assertTrue(len(convs) >= 1)

        # Check thread messages
        thread = self.client.get_messages("u_chat2", "u_chat1")
        self.assertEqual(len(thread), 1)
        self.assertEqual(thread[0]["content"], "Hey! Are you studying for the midterm?")

        # Check unread count
        unread = self.client.get_unread_message_count("u_chat2")
        self.assertGreaterEqual(unread, 1)

    def test_moderation_and_appeal_workflow(self):
        self.client.create_user(username="mod_admin", user_id="u_admin")
        self.client.create_user(username="bad_actor", user_id="u_bad")
        self.client.create_user(username="whistleblower", user_id="u_wb")

        post = self.client.create_discussion(
            author_id="u_bad",
            content="Commercial spam link buy now http://spam.xyz",
            discussion_id="d_spam1"
        )

        # Report content
        report = self.client.report_content(
            reporter_id="u_wb",
            target_type="discussion",
            target_id="d_spam1",
            reason="Unsolicited commercial spam",
            category="spam",
            report_id="rep_spam1"
        )
        self.assertEqual(report["target_id"], "d_spam1")

        # Resolve report by hiding
        self.client.resolve_report("rep_spam1", admin_id="u_admin", action="hide", reason="Confirmed commercial spam")
        hidden_disc = self.client.get_discussion("d_spam1")
        self.assertTrue(hidden_disc["is_hidden"])

        # Bad actor files appeal
        appeal = self.client.appeal(
            appellant_id="u_bad",
            target_type="discussion",
            target_id="d_spam1",
            reason="This was a misunderstanding, please review",
            appeal_id="app_spam1"
        )
        self.assertEqual(appeal["target_id"], "d_spam1")

        # Admin reviews appeal
        app_res = self.client.resolve_appeal("app_spam1", admin_id="u_admin", action="reject", note="Spam confirmed")
        self.assertIn(app_res.get("status", "resolved"), ("approved", "resolved", "rejected", "success"))

    def test_user_session_abstraction(self):
        self.client.create_user(username="session_user", user_id="u_sess1", bio="Session test user")
        session = self.client.session("u_sess1")
        self.assertIsInstance(session, UserSession)

        # Profile via session
        prof = session.get_profile()
        self.assertEqual(prof["username"], "session_user")

        # Post via session
        post = session.post("Posting directly via fluent user session #fluent")
        self.assertEqual(post["author_id"], "u_sess1")

        # Feed via session
        feed = session.feed()
        self.assertTrue(len(feed) >= 1)

    def test_error_handling_not_found(self):
        with self.assertRaises(NotFoundError):
            self.client.get_user("non_existent_user_99999")


if __name__ == "__main__":
    unittest.main()
