import unittest
import io
import json
from datetime import datetime, timedelta
from social_platform.core.models import (
    User, Discussion, Community, Channel, ModerationReport, CommunityMember, CommunityBan, Notification,
    UserBlock, DirectMessage, FeedItem, CommunityJoinRequest, CommunityInvite, CommunityRole, COMMUNITY_ROLES,
    Visibility, Course, CourseEnrollment, CourseResource, StudyGroup, StudyGroupMember,
    PrivacySettings, DMPrivacy, DirectMessagePrivacy, UserPrivacySettings,
    AcademicSpace, CourseSpace, ClassmateVerification, CourseMember, StudyResource, Syllabus, AcademicStudyGroup,
    MediaAttachment, Media, MediaMetadata, MediaAccessibility,
    ContentFilterPreferences, UserContentFilter, UserContentFilterPreferences, ContentFilteringPreferences,
    UserAccessibilitySettings, AccessibilitySettings, UserSettingsAccessibility,
    ContentLifecycleState, ContentLifecycleAction, ContentLifecycleEvent, ContentInteraction,
    ModerationAppeal, ContentAppeal, ContentReport
)
from social_platform.core.database import SocialDatabase
from social_platform.core.feed import (
    generate_chronological_feed, generate_following_feed,
    generate_interest_matched_feed, generate_community_scoped_feed,
    generate_feed, FeedService, FeedMode
)
import social_platform.api.server as api_server



class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = SocialDatabase(":memory:")

    def test_user_creation(self):
        u1 = User(id="u1", username="alice")
        self.db.create_user(u1)
        fetched = self.db.get_user("u1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.username, "alice")
        self.assertFalse(fetched.is_publicly_discoverable)

    def test_feed_generation_with_db(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        u3 = User(id="u3", username="charlie")
        for u in [u1, u2, u3]: self.db.create_user(u)

        self.db.create_connection("u1", "u2")
        
        self.db.create_discussion(Discussion(id="d1", author_id="u2", content="Bob post"))
        self.db.create_discussion(Discussion(id="d2", author_id="u3", content="Charlie post"))
        self.db.create_discussion(Discussion(id="d3", author_id="u1", content="Alice post"))
        
        conns = self.db.get_connections("u1")
        all_discs = self.db.get_all_discussions()
        
        feed = generate_chronological_feed("u1", conns, all_discs)
        
        # Should contain u1 and u2 posts, NOT u3
        self.assertEqual(len(feed), 2)
        authors = {d.author_id for d in feed}
        self.assertIn("u1", authors)
        self.assertIn("u2", authors)
        self.assertNotIn("u3", authors)

    def test_discussion_retrieval(self):
        disc = Discussion(id="d_test", author_id="u1", content="Quality discussion content")
        self.db.create_discussion(disc)
        fetched = self.db.get_discussion("d_test")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, "d_test")
        self.assertEqual(fetched.author_id, "u1")
        self.assertEqual(fetched.content, "Quality discussion content")
        self.assertEqual(fetched.value_endorsements, 0)
        self.assertIsNone(fetched.parent_id)

        self.assertIsNone(self.db.get_discussion("non_existent"))

    def test_discussion_endorsement(self):
        disc = Discussion(id="d_endorse", author_id="u1", content="Valuable insight")
        self.db.create_discussion(disc)

        # First endorsement
        success = self.db.endorse_discussion("d_endorse")
        self.assertTrue(success)
        fetched = self.db.get_discussion("d_endorse")
        self.assertEqual(fetched.value_endorsements, 1)

        # Second endorsement
        success = self.db.endorse_discussion("d_endorse")
        self.assertTrue(success)
        fetched = self.db.get_discussion("d_endorse")
        self.assertEqual(fetched.value_endorsements, 2)

        # Endorsing non-existent discussion
        self.assertFalse(self.db.endorse_discussion("non_existent"))

    def test_discussion_replies(self):
        root = Discussion(id="d_root", author_id="u1", content="Root topic")
        reply1 = Discussion(id="d_rep1", author_id="u2", content="Reply 1", parent_id="d_root")
        reply2 = Discussion(id="d_rep2", author_id="u3", content="Reply 2", parent_id="d_root")
        unrelated = Discussion(id="d_other", author_id="u1", content="Other post")

        self.db.create_discussion(root)
        self.db.create_discussion(reply1)
        self.db.create_discussion(reply2)
        self.db.create_discussion(unrelated)

        replies = self.db.get_replies("d_root")
        self.assertEqual(len(replies), 2)
        self.assertEqual([r.id for r in replies], ["d_rep1", "d_rep2"])
        self.assertEqual(replies[0].parent_id, "d_root")
        self.assertEqual(replies[1].parent_id, "d_root")

        self.assertEqual(self.db.get_replies("d_rep1"), [])
        self.assertEqual(self.db.get_replies("non_existent"), [])


    def test_community_crud_and_membership(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.db.create_user(u1)
        self.db.create_user(u2)

        # Create community
        c1 = Community(id="c1", name="Python Developers", description="Discuss Python", creator_id="u1")
        self.db.create_community(c1)

        fetched = self.db.get_community("c1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Python Developers")
        self.assertEqual(fetched.creator_id, "u1")

        # Creator is automatically owner member
        members = self.db.get_community_members("c1")
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].user_id, "u1")
        self.assertEqual(members[0].role, "owner")

        # Bob joins
        joined = self.db.join_community("c1", "u2", "member")
        self.assertTrue(joined)
        members = self.db.get_community_members("c1")
        self.assertEqual(len(members), 2)

        # User communities
        bob_comms = self.db.get_user_communities("u2")
        self.assertEqual(len(bob_comms), 1)
        self.assertEqual(bob_comms[0].id, "c1")

        # Bob leaves
        left = self.db.leave_community("c1", "u2")
        self.assertTrue(left)
        members = self.db.get_community_members("c1")
        self.assertEqual(len(members), 1)

    def test_topic_channels_and_discussions(self):
        u1 = User(id="u1", username="alice")
        self.db.create_user(u1)
        c1 = Community(id="c1", name="Tech Hub", creator_id="u1")
        self.db.create_community(c1)

        # Create channels
        ch1 = Channel(id="ch1", community_id="c1", name="general", description="General discussions")
        ch2 = Channel(id="ch2", community_id="c1", name="announcements", description="Announcements")
        self.db.create_channel(ch1)
        self.db.create_channel(ch2)

        channels = self.db.get_community_channels("c1")
        self.assertEqual(len(channels), 2)
        self.assertEqual([c.name for c in channels], ["general", "announcements"])

        # Post discussions to channels
        d1 = Discussion(id="d1", author_id="u1", content="General topic", community_id="c1", channel_id="ch1")
        d2 = Discussion(id="d2", author_id="u1", content="Announcement topic", community_id="c1", channel_id="ch2")
        self.db.create_discussion(d1)
        self.db.create_discussion(d2)

        ch1_discs = self.db.get_channel_discussions("ch1")
        self.assertEqual(len(ch1_discs), 1)
        self.assertEqual(ch1_discs[0].id, "d1")

        comm_discs = self.db.get_community_discussions("c1")
        self.assertEqual(len(comm_discs), 2)

    def test_moderation_reports_and_actions(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="spammer")
        self.db.create_user(u1)
        self.db.create_user(u2)

        disc = Discussion(id="d_spam", author_id="u2", content="Spam message")
        self.db.create_discussion(disc)

        # Create report
        rep = ModerationReport(
            id="r1", reporter_id="u1", target_type="discussion", target_id="d_spam", reason="Spam and abuse"
        )
        self.db.create_moderation_report(rep)

        reports = self.db.get_moderation_reports(status="pending")
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].reason, "Spam and abuse")

        # Hide discussion
        self.db.hide_discussion("d_spam")
        self.assertEqual(len(self.db.get_all_discussions(include_hidden=False)), 0)
        self.assertEqual(len(self.db.get_all_discussions(include_hidden=True)), 1)

        # Resolve report
        resolved = self.db.resolve_moderation_report("r1", status="resolved")
        self.assertTrue(resolved)
        fetched_rep = self.db.get_moderation_report("r1")
        self.assertEqual(fetched_rep.status, "resolved")

        # Unhide discussion
        self.db.unhide_discussion("d_spam")
        self.assertEqual(len(self.db.get_all_discussions(include_hidden=False)), 1)

    def test_community_bans(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bad_actor")
        self.db.create_user(u1)
        self.db.create_user(u2)
        c1 = Community(id="c1", name="Safe Haven", creator_id="u1")
        self.db.create_community(c1)
        self.db.join_community("c1", "u2")

        # Ban u2
        self.db.ban_user_from_community("c1", "u2", banned_by="u1", reason="Harassment")
        self.assertTrue(self.db.is_user_banned("c1", "u2"))

        # Check membership removed
        members = self.db.get_community_members("c1")
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].user_id, "u1")

        # Banned user cannot join
        can_join = self.db.join_community("c1", "u2")
        self.assertFalse(can_join)

        # Banned user cannot post to community
        banned_disc = Discussion(id="d_banned", author_id="u2", content="Banned post", community_id="c1")
        with self.assertRaises(PermissionError):
            self.db.create_discussion(banned_disc)

        # Unban u2
        self.db.unban_user_from_community("c1", "u2")
        self.assertFalse(self.db.is_user_banned("c1", "u2"))
        self.assertTrue(self.db.join_community("c1", "u2"))

    def test_notifications_mentions_replies_endorsements(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        u3 = User(id="u3", username="charlie")
        for u in [u1, u2, u3]:
            self.db.create_user(u)

        # 1. Bob creates root post
        root_post = Discussion(id="d_root", author_id="u2", content="Hello everyone")
        self.db.create_discussion(root_post)

        # 2. Alice replies to Bob and mentions Charlie
        reply_post = Discussion(
            id="d_rep", author_id="u1", content="Great thoughts, cc @charlie", parent_id="d_root"
        )
        self.db.create_discussion(reply_post)

        # Bob should receive a reply notification
        bob_notifs = self.db.get_notifications("u2")
        self.assertEqual(len(bob_notifs), 1)
        self.assertEqual(bob_notifs[0].type, "reply")
        self.assertEqual(bob_notifs[0].actor_id, "u1")
        self.assertEqual(bob_notifs[0].target_id, "d_rep")
        self.assertFalse(bob_notifs[0].is_read)

        # Charlie should receive a mention notification
        charlie_notifs = self.db.get_notifications("u3")
        self.assertEqual(len(charlie_notifs), 1)
        self.assertEqual(charlie_notifs[0].type, "mention")
        self.assertEqual(charlie_notifs[0].actor_id, "u1")
        self.assertEqual(charlie_notifs[0].target_id, "d_rep")

        # 3. Charlie endorses Alice's reply
        self.db.endorse_discussion("d_rep", actor_id="u3")

        # Alice should receive an endorsement notification
        alice_notifs = self.db.get_notifications("u1")
        self.assertEqual(len(alice_notifs), 1)
        self.assertEqual(alice_notifs[0].type, "endorsement")
        self.assertEqual(alice_notifs[0].actor_id, "u3")
        self.assertEqual(alice_notifs[0].target_id, "d_rep")

        # Check unread count and marking as read
        self.assertEqual(self.db.get_unread_notification_count("u1"), 1)
        self.db.mark_notification_as_read(alice_notifs[0].id)
        self.assertEqual(self.db.get_unread_notification_count("u1"), 0)
        self.assertEqual(len(self.db.get_notifications("u1", unread_only=True)), 0)
        self.assertEqual(len(self.db.get_notifications("u1", unread_only=False)), 1)

        # Test mark all as read for Bob
        self.assertEqual(self.db.get_unread_notification_count("u2"), 1)
        updated = self.db.mark_all_notifications_as_read("u2")
        self.assertEqual(updated, 1)
        self.assertEqual(self.db.get_unread_notification_count("u2"), 0)

    def test_keyword_search_discovery(self):
        # Users
        u1 = User(id="u1", username="quantum_alice", is_publicly_discoverable=True)
        u2 = User(id="u2", username="quantum_bob", is_publicly_discoverable=False)
        u3 = User(id="u3", username="neural_charlie", is_publicly_discoverable=True)
        for u in [u1, u2, u3]:
            self.db.create_user(u)

        # Communities
        c1 = Community(id="c1", name="Quantum Computing", description="Physics and algorithms", creator_id="u1", is_private=False)
        c2 = Community(id="c2", name="Quantum Secret Society", description="Private quantum group", creator_id="u2", is_private=True)
        c3 = Community(id="c3", name="Neural Networks", description="Deep learning", creator_id="u3", is_private=False)
        for c in [c1, c2, c3]:
            self.db.create_community(c)

        # Discussions
        d1 = Discussion(id="d1", author_id="u1", content="Exploring quantum supremacy in computing", is_hidden=False)
        d2 = Discussion(id="d2", author_id="u2", content="Spammy quantum text that got hidden", is_hidden=True)
        d3 = Discussion(id="d3", author_id="u3", content="Transformers and neural architectures", is_hidden=False)
        for d in [d1, d2, d3]:
            self.db.create_discussion(d)

        # 1. Search discussions
        discs = self.db.search_discussions("quantum", include_hidden=False)
        self.assertEqual(len(discs), 1)
        self.assertEqual(discs[0].id, "d1")

        discs_all = self.db.search_discussions("quantum", include_hidden=True)
        self.assertEqual(len(discs_all), 2)

        # 2. Search communities
        comms = self.db.search_communities("quantum", include_private=False)
        self.assertEqual(len(comms), 1)
        self.assertEqual(comms[0].id, "c1")

        comms_all = self.db.search_communities("quantum", include_private=True)
        self.assertEqual(len(comms_all), 2)

        # Search by description
        comms_desc = self.db.search_communities("algorithms")
        self.assertEqual(len(comms_desc), 1)
        self.assertEqual(comms_desc[0].id, "c1")

        # 3. Search users (privacy by default)
        users_pub = self.db.search_users("quantum", publicly_discoverable_only=True)
        self.assertEqual(len(users_pub), 1)
        self.assertEqual(users_pub[0].username, "quantum_alice")

        users_all = self.db.search_users("quantum", publicly_discoverable_only=False)
        self.assertEqual(len(users_all), 2)

        # 4. Unified search
        unified = self.db.search("quantum", publicly_discoverable_only=True, include_private_communities=False, include_hidden_discussions=False)
        self.assertEqual(len(unified["discussions"]), 1)
        self.assertEqual(len(unified["communities"]), 1)
        self.assertEqual(len(unified["users"]), 1)

    def test_direct_messaging_send_and_retrieve(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.db.create_user(u1)
        self.db.create_user(u2)

        dm = DirectMessage(id="dm1", sender_id="u1", recipient_id="u2", content="Hey Bob, let's collaborate.")
        self.db.send_direct_message(dm)

        fetched = self.db.get_direct_message("dm1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, "dm1")
        self.assertEqual(fetched.sender_id, "u1")
        self.assertEqual(fetched.recipient_id, "u2")
        self.assertEqual(fetched.content, "Hey Bob, let's collaborate.")
        self.assertEqual(fetched.delivery_state, "sent")
        self.assertEqual(fetched.status, "sent")
        self.assertIsNone(fetched.read_at)

        # Check notification was created for Bob
        notifs = self.db.get_notifications("u2")
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0].type, "direct_message")
        self.assertEqual(notifs[0].actor_id, "u1")
        self.assertEqual(notifs[0].target_id, "dm1")

    def test_direct_messaging_conversation_history(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        u3 = User(id="u3", username="charlie")
        for u in [u1, u2, u3]:
            self.db.create_user(u)

        dm1 = DirectMessage(id="dm1", sender_id="u1", recipient_id="u2", content="Hi Bob")
        dm2 = DirectMessage(id="dm2", sender_id="u2", recipient_id="u1", content="Hi Alice, what's up?")
        dm3 = DirectMessage(id="dm3", sender_id="u1", recipient_id="u2", content="Working on the project.")
        dm4 = DirectMessage(id="dm4", sender_id="u3", recipient_id="u1", content="Hey Alice, Charlie here.")
        for d in [dm1, dm2, dm3, dm4]:
            self.db.create_direct_message(d)

        conv = self.db.get_direct_messages("u1", "u2")
        self.assertEqual(len(conv), 3)
        self.assertEqual([m.id for m in conv], ["dm1", "dm2", "dm3"])

        conv_alias = self.db.get_conversation("u2", "u1")
        self.assertEqual(len(conv_alias), 3)
        self.assertEqual([m.id for m in conv_alias], ["dm1", "dm2", "dm3"])

    def test_direct_messaging_delivery_states_and_read_tracking(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.db.create_user(u1)
        self.db.create_user(u2)

        dm = DirectMessage(id="dm1", sender_id="u1", recipient_id="u2", content="Confidential info")
        self.db.create_direct_message(dm)

        self.assertEqual(self.db.get_unread_message_count("u2"), 1)

        # Mark as delivered
        self.db.mark_message_delivered("dm1")
        fetched = self.db.get_direct_message("dm1")
        self.assertEqual(fetched.delivery_state, "delivered")
        self.assertEqual(self.db.get_unread_message_count("u2"), 1)

        # Mark as read
        self.db.mark_message_read("dm1")
        fetched = self.db.get_direct_message("dm1")
        self.assertEqual(fetched.delivery_state, "read")
        self.assertIsNotNone(fetched.read_at)
        self.assertEqual(self.db.get_unread_message_count("u2"), 0)

        # Send another message and mark whole conversation as read
        dm2 = DirectMessage(id="dm2", sender_id="u1", recipient_id="u2", content="Second message")
        dm3 = DirectMessage(id="dm3", sender_id="u1", recipient_id="u2", content="Third message")
        self.db.create_direct_message(dm2)
        self.db.create_direct_message(dm3)
        self.assertEqual(self.db.get_unread_message_count("u2"), 2)

        marked_count = self.db.mark_conversation_as_read("u2", "u1")
        self.assertEqual(marked_count, 2)
        self.assertEqual(self.db.get_unread_message_count("u2"), 0)

    def test_user_conversations_summary(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        u3 = User(id="u3", username="charlie")
        for u in [u1, u2, u3]:
            self.db.create_user(u)

        dm1 = DirectMessage(id="dm1", sender_id="u1", recipient_id="u2", content="Hi Bob")
        dm2 = DirectMessage(id="dm2", sender_id="u3", recipient_id="u1", content="Hi Alice from Charlie")
        for d in [dm1, dm2]:
            self.db.create_direct_message(d)

        convs = self.db.get_user_conversations("u1")
        self.assertEqual(len(convs), 2)
        partner_ids = {c["partner_id"] for c in convs}
        self.assertEqual(partner_ids, {"u2", "u3"})

    def test_user_blocklist_privacy_controls(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="harasser")
        self.db.create_user(u1)
        self.db.create_user(u2)

        # Initially not blocked
        self.assertFalse(self.db.is_user_blocked("u1", "u2"))
        self.assertFalse(self.db.is_blocked("u1", "u2"))
        self.assertFalse(self.db.are_users_blocked("u1", "u2"))

        # Alice blocks Harasser
        self.db.block_user("u1", "u2", reason="Unsolicited spam")
        self.assertTrue(self.db.is_user_blocked("u1", "u2"))
        self.assertFalse(self.db.is_user_blocked("u2", "u1"))
        self.assertTrue(self.db.are_users_blocked("u1", "u2"))

        blocked_list = self.db.get_blocked_users("u1")
        self.assertEqual(len(blocked_list), 1)
        self.assertEqual(blocked_list[0].blocked_id, "u2")
        self.assertEqual(blocked_list[0].reason, "Unsolicited spam")
        self.assertEqual(self.db.get_blocked_user_ids("u1"), ["u2"])

        # Blocked user attempting to send message to blocker -> PermissionError
        dm_blocked = DirectMessage(id="dm_bad", sender_id="u2", recipient_id="u1", content="Spam attempt")
        with self.assertRaises(PermissionError):
            self.db.create_direct_message(dm_blocked)

        # Blocker attempting to send message to blocked user -> PermissionError
        dm_blocker = DirectMessage(id="dm_bad2", sender_id="u1", recipient_id="u2", content="Blocked message")
        with self.assertRaises(PermissionError):
            self.db.create_direct_message(dm_blocker)

        # Alice unblocks Harasser
        unblocked = self.db.unblock_user("u1", "u2")
        self.assertTrue(unblocked)
        self.assertFalse(self.db.is_user_blocked("u1", "u2"))
        self.assertFalse(self.db.are_users_blocked("u1", "u2"))

        # Now messages can be sent normally
        dm_ok = DirectMessage(id="dm_ok", sender_id="u2", recipient_id="u1", content="Peace")
        self.db.create_direct_message(dm_ok)
        self.assertEqual(len(self.db.get_direct_messages("u1", "u2")), 1)

    def test_user_profile_customization_and_crud(self):
        u1 = User(
            id="u_prof1",
            username="diana",
            bio="Robotics researcher and distributed systems enthusiast",
            avatar_url="https://example.com/avatars/diana.png",
            school="School of Engineering",
            university="MIT",
            class_year="2026",
            interests=["robotics", "distributed-systems", "ai"]
        )
        self.db.create_user(u1)

        fetched = self.db.get_user("u_prof1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.username, "diana")
        self.assertEqual(fetched.bio, "Robotics researcher and distributed systems enthusiast")
        self.assertEqual(fetched.avatar_url, "https://example.com/avatars/diana.png")
        self.assertEqual(fetched.school, "School of Engineering")
        self.assertEqual(fetched.university, "MIT")
        self.assertEqual(fetched.class_year, "2026")
        self.assertEqual(fetched.interests, ["robotics", "distributed-systems", "ai"])
        self.assertEqual(fetched.topic_interests, ["robotics", "distributed-systems", "ai"])
        self.assertEqual(fetched.class_affiliation, "2026")

        # Update profile fields
        updated = self.db.update_user_profile(
            "u_prof1",
            bio="Updated bio for Diana",
            university="Harvard",
            interests=["quantum-computing", "robotics"]
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.bio, "Updated bio for Diana")
        self.assertEqual(updated.university, "Harvard")
        self.assertEqual(updated.school, "School of Engineering")  # preserved
        self.assertEqual(updated.interests, ["quantum-computing", "robotics"])

        # Update via update_profile alias with kwargs
        updated2 = self.db.update_profile("u_prof1", class_affiliation="2027", topic_interests=["ai", "ml"])
        self.assertIsNotNone(updated2)
        self.assertEqual(updated2.class_year, "2027")
        self.assertEqual(updated2.interests, ["ai", "ml"])

        # Update non-existent user returns None
        self.assertIsNone(self.db.update_user_profile("non_existent", bio="Hello"))

    def test_user_profile_search_and_filtering(self):
        u1 = User(
            id="u1", username="alice_mit", is_publicly_discoverable=True,
            bio="AI researcher at MIT CSAIL", school="EECS", university="MIT",
            class_year="2025", interests=["ai", "nlp", "machine-learning"]
        )
        u2 = User(
            id="u2", username="bob_stanford", is_publicly_discoverable=True,
            bio="Robotics and vision student", school="Engineering", university="Stanford",
            class_year="2026", interests=["robotics", "computer-vision", "ai"]
        )
        u3 = User(
            id="u3", username="charlie_private", is_publicly_discoverable=False,
            bio="Stealth quantum physics researcher at MIT", school="Physics", university="MIT",
            class_year="2025", interests=["quantum", "physics"]
        )
        u4 = User(
            id="u4", username="dana_harvard", is_publicly_discoverable=True,
            bio="Computational biology fellow", school="Biomedical Sciences", university="Harvard",
            class_year="2026", interests=["biology", "machine-learning"]
        )
        for u in [u1, u2, u3, u4]:
            self.db.create_user(u)

        # 1. Search across all profile fields
        results = self.db.search_users("CSAIL")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "u1")

        # 2. Filter by school / department
        results_school = self.db.filter_users(school="Engineering")
        self.assertEqual(len(results_school), 1)
        self.assertEqual(results_school[0].id, "u2")

        # 3. Filter by university
        results_uni = self.db.filter_users(university="MIT", publicly_discoverable_only=True)
        self.assertEqual(len(results_uni), 1)
        self.assertEqual(results_uni[0].id, "u1")

        # MIT including private users
        results_uni_all = self.db.filter_users(university="MIT", publicly_discoverable_only=False)
        self.assertEqual(len(results_uni_all), 2)
        self.assertEqual({u.id for u in results_uni_all}, {"u1", "u3"})

        # 4. Filter by class year
        results_class = self.db.filter_users(class_year="2026")
        self.assertEqual(len(results_class), 2)
        self.assertEqual({u.id for u in results_class}, {"u2", "u4"})

        # 5. Filter by interest
        results_ai = self.db.get_users_by_interest("ai")
        self.assertEqual(len(results_ai), 2)
        self.assertEqual({u.id for u in results_ai}, {"u1", "u2"})

        # 6. Filter by affiliation convenience method
        results_aff = self.db.get_users_by_affiliation(university="Stanford", class_year="2026")
        self.assertEqual(len(results_aff), 1)
        self.assertEqual(results_aff[0].id, "u2")

        # 7. Combined search + filter
        results_comb = self.db.search_users(query="learning", university="Harvard")
        self.assertEqual(len(results_comb), 1)
        self.assertEqual(results_comb[0].id, "u4")

        # 8. Unified search with profile fields
        unified = self.db.search("biology")
        self.assertEqual(len(unified["users"]), 1)
        self.assertEqual(unified["users"][0].id, "u4")

    def test_multi_mode_feed_modes_and_explainability(self):
        u1 = User(id="u1", username="alice", interests=["robotics", "ai"])
        u2 = User(id="u2", username="bob", interests=["web", "databases"])
        u3 = User(id="u3", username="charlie", interests=["quantum", "physics"])
        u4 = User(id="u4", username="dana", interests=["robotics", "hardware"])
        for u in [u1, u2, u3, u4]:
            self.db.create_user(u)

        # u1 follows u2
        self.db.create_connection("u1", "u2")

        # Communities
        c1 = Community(id="c1", name="Robotics Hub", creator_id="u1")
        c2 = Community(id="c2", name="Quantum Hub", creator_id="u3")
        self.db.create_community(c1)
        self.db.create_community(c2)

        # Discussions
        d1 = Discussion(id="d1", author_id="u1", content="My thoughts on robotics and automation", community_id="c1")
        d2 = Discussion(id="d2", author_id="u2", content="New web database benchmark released")
        d3 = Discussion(id="d3", author_id="u3", content="Quantum computing breakthroughs in physics", community_id="c2")
        d4 = Discussion(id="d4", author_id="u4", content="Advanced robotics design and hardware controllers")
        d_hidden = Discussion(id="d_hidden", author_id="u2", content="Spammy content", is_hidden=True)
        for d in [d1, d2, d3, d4, d_hidden]:
            self.db.create_discussion(d)

        # 1. Chronological Mode
        feed_chrono = self.db.get_feed("u1", mode="chronological")
        self.assertTrue(len(feed_chrono) >= 2)
        for item in feed_chrono:
            self.assertIn("mode:chronological", item.explanation_tags)
            self.assertTrue(len(item.explanation) > 0)
            self.assertFalse(item.is_hidden)

        # 2. Following Mode (u1's own posts + posts from followed user u2)
        feed_following = self.db.get_following_feed("u1")
        self.assertEqual(len(feed_following), 2)
        following_ids = [item.id for item in feed_following]
        self.assertIn("d1", following_ids)
        self.assertIn("d2", following_ids)
        for item in feed_following:
            self.assertIn("mode:following", item.explanation_tags)
            if item.author_id == "u1":
                self.assertIn("author:self", item.explanation_tags)
            else:
                self.assertIn("following", item.explanation_tags)
                self.assertIn("following:u2", item.explanation_tags)

        # 3. Interest-Matched Mode (Alice interested in 'robotics', 'ai')
        feed_interest = self.db.get_interest_matched_feed("u1")
        # d1 and d4 contain 'robotics'
        interest_ids = [item.id for item in feed_interest]
        self.assertIn("d1", interest_ids)
        self.assertIn("d4", interest_ids)
        self.assertNotIn("d2", interest_ids)  # 'web database'
        self.assertNotIn("d3", interest_ids)  # 'quantum'
        for item in feed_interest:
            self.assertIn("mode:interest_matched", item.explanation_tags)
            self.assertIn("interest_match", item.explanation_tags)
            self.assertIn("matched_interest:robotics", item.explanation_tags)
            self.assertIn("robotics", item.explanation)
            self.assertGreater(item.score, 0.0)

        # Explicit interest override
        feed_quantum = self.db.get_interest_matched_feed("u1", interests=["quantum"])
        quantum_ids = [item.id for item in feed_quantum]
        self.assertIn("d3", quantum_ids)
        self.assertNotIn("d1", quantum_ids)

        # 4. Community-Scoped Mode (Alice is in c1)
        feed_comm = self.db.get_community_scoped_feed("u1")
        comm_ids = [item.id for item in feed_comm]
        self.assertIn("d1", comm_ids)
        self.assertNotIn("d3", comm_ids)  # c2
        for item in feed_comm:
            self.assertIn("mode:community_scoped", item.explanation_tags)
            self.assertIn("community_member", item.explanation_tags)

        # Scoped to specific community_id
        feed_comm2 = self.db.get_community_scoped_feed("u1", community_id="c2")
        comm2_ids = [item.id for item in feed_comm2]
        self.assertIn("d3", comm2_ids)

        # 5. Privacy & Block Filtering
        # Alice blocks u4 -> d4 should be filtered out from all feed modes
        self.db.block_user("u1", "u4")
        feed_interest_after_block = self.db.get_interest_matched_feed("u1")
    def test_community_roles_and_permission_enforcement(self):
        u_owner = User(id="u_owner", username="owner_user")
        u_admin = User(id="u_admin", username="admin_user")
        u_mod = User(id="u_mod", username="mod_user")
        u_member = User(id="u_member", username="member_user")
        u_stranger = User(id="u_stranger", username="stranger_user")
        for u in [u_owner, u_admin, u_mod, u_member, u_stranger]:
            self.db.create_user(u)

        # 1. Create community -> owner role assigned to creator
        c1 = Community(id="c_roles", name="Roles Community", creator_id="u_owner")
        self.db.create_community(c1)

        owner_member = self.db.get_community_member("c_roles", "u_owner")
        self.assertIsNotNone(owner_member)
        self.assertEqual(owner_member.role, CommunityRole.OWNER)
        self.assertTrue(owner_member.is_owner)
        self.assertTrue(owner_member.is_admin)
        self.assertTrue(owner_member.is_moderator)

        # 2. Add other members with roles
        self.db.join_community("c_roles", "u_admin", role=CommunityRole.ADMIN)
        self.db.join_community("c_roles", "u_mod", role=CommunityRole.MODERATOR)
        self.db.join_community("c_roles", "u_member", role=CommunityRole.MEMBER)

        # Test filtering by role
        admins = self.db.get_community_members("c_roles", role=CommunityRole.ADMIN)
        self.assertEqual(len(admins), 1)
        self.assertEqual(admins[0].user_id, "u_admin")

        mods = self.db.get_community_members("c_roles", role=CommunityRole.MODERATOR)
        self.assertEqual(len(mods), 1)
        self.assertEqual(mods[0].user_id, "u_mod")

        # 3. Permissions check
        self.assertTrue(self.db.has_community_permission("c_roles", "u_owner", "transfer_ownership"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_owner", "delete_community"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_owner", "manage_roles"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_owner", "ban_users"))

        self.assertFalse(self.db.has_community_permission("c_roles", "u_admin", "transfer_ownership"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_admin", "manage_roles"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_admin", "manage_channels"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_admin", "ban_users"))

        self.assertFalse(self.db.has_community_permission("c_roles", "u_mod", "manage_roles"))
        self.assertFalse(self.db.has_community_permission("c_roles", "u_mod", "manage_channels"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_mod", "ban_users"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_mod", "approve_join_requests"))

        self.assertFalse(self.db.has_community_permission("c_roles", "u_member", "ban_users"))
        self.assertFalse(self.db.has_community_permission("c_roles", "u_member", "manage_roles"))
        self.assertTrue(self.db.has_community_permission("c_roles", "u_member", "post"))

        # 4. Role management via update_member_role
        # Admin promoting member to moderator -> success
        promoted = self.db.update_member_role("c_roles", "u_member", CommunityRole.MODERATOR, actor_id="u_admin")
        self.assertTrue(promoted)
        self.assertEqual(self.db.get_member_role("c_roles", "u_member"), CommunityRole.MODERATOR)

        # Admin attempting to promote moderator to admin -> PermissionError
        with self.assertRaises(PermissionError):
            self.db.update_member_role("c_roles", "u_member", CommunityRole.ADMIN, actor_id="u_admin")

        # Moderator attempting to change roles -> PermissionError
        with self.assertRaises(PermissionError):
            self.db.update_member_role("c_roles", "u_member", CommunityRole.MEMBER, actor_id="u_mod")

        # Owner transferring ownership to admin
        transferred = self.db.transfer_community_ownership("c_roles", "u_owner", "u_admin")
        self.assertTrue(transferred)
        self.assertEqual(self.db.get_member_role("c_roles", "u_admin"), CommunityRole.OWNER)
        self.assertEqual(self.db.get_member_role("c_roles", "u_owner"), CommunityRole.ADMIN)

        # Non-owner attempting to transfer ownership -> PermissionError
        with self.assertRaises(PermissionError):
            self.db.transfer_community_ownership("c_roles", "u_owner", "u_mod")

        # 5. Ban permission enforcement
        # Moderator banning member -> success
        self.db.update_member_role("c_roles", "u_member", CommunityRole.MEMBER)
        banned = self.db.ban_user_from_community("c_roles", "u_member", banned_by="u_mod", reason="Disruptive")
        self.assertTrue(banned)
        self.assertTrue(self.db.is_user_banned("c_roles", "u_member"))

        # Moderator attempting to ban admin -> PermissionError
        with self.assertRaises(PermissionError):
            self.db.ban_user_from_community("c_roles", "u_owner", banned_by="u_mod")

        # Admin attempting to ban owner -> PermissionError
        with self.assertRaises(PermissionError):
            self.db.ban_user_from_community("c_roles", "u_admin", banned_by="u_owner")

    def test_private_community_join_requests_and_approvals(self):
        u_owner = User(id="u_owner", username="owner_priv")
        u_admin = User(id="u_admin", username="admin_priv")
        u_applicant1 = User(id="u_app1", username="app_user1")
        u_applicant2 = User(id="u_app2", username="app_user2")
        u_banned = User(id="u_banned", username="banned_user")
        for u in [u_owner, u_admin, u_applicant1, u_applicant2, u_banned]:
            self.db.create_user(u)

        c_priv = Community(id="c_priv", name="Secret Society", creator_id="u_owner", is_private=True)
        self.db.create_community(c_priv)
        self.db.join_community("c_priv", "u_admin", role=CommunityRole.ADMIN)
        self.db.ban_user_from_community("c_priv", "u_banned", banned_by="u_owner")

        # 1. Direct join on private community auto-creates join request and returns False
        direct_joined = self.db.join_community("c_priv", "u_app1")
        self.assertFalse(direct_joined)

        # Check join request was created
        reqs = self.db.get_community_join_requests("c_priv", status="pending")
        self.assertEqual(len(reqs), 1)
        req1 = reqs[0]
        self.assertEqual(req1.user_id, "u_app1")
        self.assertEqual(req1.status, "pending")

        # Owner/Admin received notification
        notifs = self.db.get_notifications("u_owner")
        self.assertTrue(any(n.type == "join_request" for n in notifs))

        # Explicit request_to_join for applicant2
        req2 = self.db.request_to_join("c_priv", "u_app2", message="I want to contribute")
        self.assertEqual(req2.user_id, "u_app2")
        self.assertEqual(req2.message, "I want to contribute")

        # Banned user attempting to request join -> PermissionError
        with self.assertRaises(PermissionError):
            self.db.create_join_request("c_priv", "u_banned")

        # User join requests retrieval
        user_reqs = self.db.get_user_join_requests("u_app2")
        self.assertEqual(len(user_reqs), 1)
        self.assertEqual(user_reqs[0].id, req2.id)

        # 2. Approve join request
        approved = self.db.approve_join_request(req1.id, reviewer_id="u_admin", role="member")
        self.assertTrue(approved)

        # Check membership and status
        member_rec = self.db.get_community_member("c_priv", "u_app1")
        self.assertIsNotNone(member_rec)
        self.assertEqual(member_rec.role, "member")

        req1_fetched = self.db.get_join_request(req1.id)
        self.assertEqual(req1_fetched.status, "approved")
        self.assertEqual(req1_fetched.reviewed_by, "u_admin")

        # Applicant received approval notification
        app1_notifs = self.db.get_notifications("u_app1")
        self.assertEqual(len(app1_notifs), 1)
        self.assertEqual(app1_notifs[0].type, "join_request_approved")

        # Already a member requesting again -> ValueError
        with self.assertRaises(ValueError):
            self.db.create_join_request("c_priv", "u_app1")

        # 3. Reject join request
        rejected = self.db.reject_join_request(req2.id, reviewer_id="u_owner", reason="Not suitable")
        self.assertTrue(rejected)

        req2_fetched = self.db.get_join_request(req2.id)
        self.assertEqual(req2_fetched.status, "rejected")
        self.assertEqual(req2_fetched.reviewed_by, "u_owner")

        # Applicant 2 is NOT in community
        self.assertIsNone(self.db.get_community_member("c_priv", "u_app2"))

        # Applicant 2 received rejection notification
        app2_notifs = self.db.get_notifications("u_app2")
        self.assertEqual(len(app2_notifs), 1)
        self.assertEqual(app2_notifs[0].type, "join_request_rejected")

    def test_member_invite_tokens(self):
        u_owner = User(id="u_owner", username="inv_owner")
        u_admin = User(id="u_admin", username="inv_admin")
        u_regular = User(id="u_reg", username="inv_regular")
        u_guest1 = User(id="u_guest1", username="guest_user1")
        u_guest2 = User(id="u_guest2", username="guest_user2")
        u_guest3 = User(id="u_guest3", username="guest_user3")
        u_banned = User(id="u_banned", username="banned_guest")
        for u in [u_owner, u_admin, u_regular, u_guest1, u_guest2, u_guest3, u_banned]:
            self.db.create_user(u)

        c_inv = Community(id="c_inv", name="Invite-Only Hub", creator_id="u_owner", is_private=True)
        self.db.create_community(c_inv)
        self.db.join_community("c_inv", "u_admin", role=CommunityRole.ADMIN)
        self.db.join_community("c_inv", "u_reg", role=CommunityRole.MEMBER)
        self.db.ban_user_from_community("c_inv", "u_banned", banned_by="u_owner")

        # 1. Regular member cannot create invite in private community
        with self.assertRaises(PermissionError):
            self.db.create_invite("c_inv", created_by="u_reg")

        # 2. Admin creates valid invite with max_uses=2 and custom role="moderator"
        expires_tomorrow = datetime.utcnow() + timedelta(days=1)
        invite = self.db.create_invite(
            "c_inv",
            created_by="u_admin",
            role=CommunityRole.MODERATOR,
            max_uses=2,
            expires_at=expires_tomorrow,
            token="TEST_TOKEN_123"
        )
        self.assertIsNotNone(invite)
        self.assertEqual(invite.token, "TEST_TOKEN_123")
        self.assertEqual(invite.role, CommunityRole.MODERATOR)
        self.assertEqual(invite.max_uses, 2)
        self.assertEqual(invite.uses_count, 0)
        self.assertTrue(invite.is_valid)
        self.assertFalse(invite.is_expired)

        # Check retrieval
        fetched_inv = self.db.get_invite("TEST_TOKEN_123")
        self.assertIsNotNone(fetched_inv)
        self.assertEqual(fetched_inv.id, invite.id)

        invites_list = self.db.get_community_invites("c_inv")
        self.assertEqual(len(invites_list), 1)

        # 3. Guest 1 uses invite to join
        used1 = self.db.use_invite("TEST_TOKEN_123", "u_guest1")
        self.assertTrue(used1)
        m1 = self.db.get_community_member("c_inv", "u_guest1")
        self.assertIsNotNone(m1)
        self.assertEqual(m1.role, CommunityRole.MODERATOR)

        fetched_inv1 = self.db.get_invite("TEST_TOKEN_123")
        self.assertEqual(fetched_inv1.uses_count, 1)
        self.assertTrue(fetched_inv1.is_valid)

        # 4. Guest 2 uses invite -> hits max_uses (2)
        used2 = self.db.join_community("c_inv", "u_guest2", invite_token="TEST_TOKEN_123")
        self.assertTrue(used2)
        m2 = self.db.get_community_member("c_inv", "u_guest2")
        self.assertIsNotNone(m2)

        fetched_inv2 = self.db.get_invite("TEST_TOKEN_123")
        self.assertEqual(fetched_inv2.uses_count, 2)
        self.assertFalse(fetched_inv2.is_valid)

        # 5. Guest 3 tries to use maxed-out invite -> fails
        used3 = self.db.use_invite("TEST_TOKEN_123", "u_guest3")
        self.assertFalse(used3)
        self.assertIsNone(self.db.get_community_member("c_inv", "u_guest3"))

        # 6. Expired invite test
        expired_time = datetime.utcnow() - timedelta(hours=1)
        exp_invite = self.db.create_invite("c_inv", created_by="u_owner", expires_at=expired_time, token="EXPIRED_TOKEN")
        self.assertTrue(exp_invite.is_expired)
        self.assertFalse(exp_invite.is_valid)
        self.assertFalse(self.db.use_invite("EXPIRED_TOKEN", "u_guest3"))

        # 7. Revoke invite test
        rev_invite = self.db.create_invite("c_inv", created_by="u_admin", token="REVOKE_ME")
        self.assertTrue(rev_invite.is_valid)
        revoked = self.db.revoke_invite("REVOKE_ME", actor_id="u_admin")
        self.assertTrue(revoked)
        fetched_rev = self.db.get_invite("REVOKE_ME")
        self.assertFalse(fetched_rev.is_active)
        self.assertFalse(self.db.use_invite("REVOKE_ME", "u_guest3"))

        # 8. Banned user cannot join even with valid invite
        valid_inv = self.db.create_invite("c_inv", created_by="u_owner", token="VALID_TOKEN")
        banned_join = self.db.use_invite("VALID_TOKEN", "u_banned")
        self.assertFalse(banned_join)
        self.assertIsNone(self.db.get_community_member("c_inv", "u_banned"))

    def test_user_visibility_settings_and_enforcement(self):
        u_owner = User(id="u_owner", username="owner_user", visibility="public")
        u_conn = User(id="u_conn", username="conn_user")
        u_stranger = User(id="u_stranger", username="stranger_user")
        u_blocked = User(id="u_blocked", username="blocked_user")
        for u in [u_owner, u_conn, u_stranger, u_blocked]:
            self.db.create_user(u)

        self.db.create_connection("u_conn", "u_owner")
        self.db.block_user("u_owner", "u_blocked")

        # 1. Default / Public
        self.assertEqual(self.db.get_user_visibility("u_owner"), Visibility.PUBLIC)
        self.assertTrue(self.db.can_user_view_profile("u_owner", "u_owner"))
        self.assertTrue(self.db.can_user_view_profile("u_owner", "u_conn"))
        self.assertTrue(self.db.can_user_view_profile("u_owner", "u_stranger"))
        self.assertFalse(self.db.can_user_view_profile("u_owner", "u_blocked"))

        # 2. Connections Only
        self.db.set_user_visibility("u_owner", Visibility.CONNECTIONS_ONLY)
        self.assertEqual(self.db.get_user_visibility("u_owner"), Visibility.CONNECTIONS_ONLY)
        self.assertTrue(self.db.can_user_view_profile("u_owner", "u_owner"))
        self.assertTrue(self.db.can_user_view_profile("u_owner", "u_conn"))
        self.assertFalse(self.db.can_user_view_profile("u_owner", "u_stranger"))
        self.assertFalse(self.db.can_user_view_profile("u_owner", "u_blocked"))

        # 3. Private
        self.db.set_user_visibility("u_owner", Visibility.PRIVATE)
        self.assertEqual(self.db.get_user_visibility("u_owner"), Visibility.PRIVATE)
        self.assertTrue(self.db.can_user_view_profile("u_owner", "u_owner"))
        self.assertFalse(self.db.can_user_view_profile("u_owner", "u_conn"))
        self.assertFalse(self.db.can_user_view_profile("u_owner", "u_stranger"))
        self.assertFalse(self.db.can_user_view_profile("u_owner", "u_blocked"))

        # Invalid visibility setting raises ValueError
        with self.assertRaises(ValueError):
            self.db.set_user_visibility("u_owner", "invalid_setting")

    def test_account_deactivation_and_reactivation(self):
        u = User(id="u_deact", username="to_be_deactivated")
        self.db.create_user(u)
        self.assertTrue(self.db.is_user_active("u_deact"))
        self.assertTrue(self.db.is_account_active("u_deact"))

        # Deactivate
        deact_res = self.db.deactivate_user("u_deact")
        self.assertTrue(deact_res)
        self.assertFalse(self.db.is_user_active("u_deact"))
        self.assertFalse(self.db.is_account_active("u_deact"))
        fetched = self.db.get_user("u_deact")
        self.assertFalse(fetched.is_active)
        self.assertTrue(fetched.is_deactivated)

        # Reactivate
        react_res = self.db.reactivate_user("u_deact")
        self.assertTrue(react_res)
        self.assertTrue(self.db.is_user_active("u_deact"))
        self.assertTrue(self.db.is_account_active("u_deact"))
        fetched = self.db.get_user("u_deact")
        self.assertTrue(fetched.is_active)
        self.assertFalse(fetched.is_deactivated)

        # Non-existent user
        self.assertFalse(self.db.deactivate_user("non_existent"))
        self.assertFalse(self.db.reactivate_user("non_existent"))
        self.assertFalse(self.db.is_user_active("non_existent"))

    def test_discussion_visibility_controls_and_permissions(self):
        u_author = User(id="u_auth", username="author")
        u_conn = User(id="u_conn", username="connected")
        u_stranger = User(id="u_strang", username="stranger")
        u_blocked = User(id="u_block", username="blocked")
        for u in [u_author, u_conn, u_stranger, u_blocked]:
            self.db.create_user(u)

        self.db.create_connection("u_conn", "u_auth")
        self.db.block_user("u_auth", "u_block")

        # Public discussion
        d_pub = Discussion(id="d_pub", author_id="u_auth", content="Public thought", visibility=Visibility.PUBLIC)
        self.db.create_discussion(d_pub)
        self.assertTrue(self.db.can_user_view_discussion("d_pub", "u_auth"))
        self.assertTrue(self.db.can_user_view_discussion("d_pub", "u_conn"))
        self.assertTrue(self.db.can_user_view_discussion("d_pub", "u_strang"))
        self.assertFalse(self.db.can_user_view_discussion("d_pub", "u_block"))

        # Connections-only discussion
        d_conn = Discussion(id="d_conn", author_id="u_auth", content="Friends only", visibility=Visibility.CONNECTIONS_ONLY)
        self.db.create_discussion(d_conn)
        self.assertTrue(self.db.can_user_view_discussion("d_conn", "u_auth"))
        self.assertTrue(self.db.can_user_view_discussion("d_conn", "u_conn"))
        self.assertFalse(self.db.can_user_view_discussion("d_conn", "u_strang"))
        self.assertFalse(self.db.can_user_view_discussion("d_conn", "u_block"))

        # Private discussion
        d_priv = Discussion(id="d_priv", author_id="u_auth", content="Diary entry", visibility=Visibility.PRIVATE)
        self.db.create_discussion(d_priv)
        self.assertTrue(self.db.can_user_view_discussion("d_priv", "u_auth"))
        self.assertFalse(self.db.can_user_view_discussion("d_priv", "u_conn"))
        self.assertFalse(self.db.can_user_view_discussion("d_priv", "u_strang"))

        # Changing discussion visibility
        self.db.set_discussion_visibility("d_priv", Visibility.PUBLIC)
        self.assertEqual(self.db.get_discussion_visibility("d_priv"), Visibility.PUBLIC)
        self.assertTrue(self.db.can_user_view_discussion("d_priv", "u_strang"))

        # get_user_discussions filtered by viewer
        discs_author_view = self.db.get_user_discussions("u_auth", viewer_id="u_auth")
        self.assertEqual(len(discs_author_view), 3)

        self.db.set_discussion_visibility("d_conn", Visibility.CONNECTIONS_ONLY)
        self.db.set_discussion_visibility("d_priv", Visibility.PRIVATE)

        discs_conn_view = self.db.get_user_discussions("u_auth", viewer_id="u_conn")
        self.assertEqual(len(discs_conn_view), 2)  # public and connections_only

        discs_strang_view = self.db.get_user_discussions("u_auth", viewer_id="u_strang")
        self.assertEqual(len(discs_strang_view), 1)  # only public

    def test_full_user_data_export(self):
        u1 = User(id="u_exp", username="export_user", bio="Export Bio", school="MIT", interests=["ai", "systems"])
        u2 = User(id="u_peer", username="peer_user")
        self.db.create_user(u1)
        self.db.create_user(u2)

        # Connections
        self.db.create_connection("u_exp", "u_peer")
        # Topic subscriptions
        self.db.subscribe_topic("u_exp", "ai")
        # Community & membership
        comm = Community(id="c_exp", name="Export Club", creator_id="u_exp")
        self.db.create_community(comm)
        # Block
        self.db.block_user("u_exp", "u_blocked_guy", reason="Spam")
        # Discussions & replies
        d_root = Discussion(id="d_exp1", author_id="u_exp", content="Export root post")
        d_reply = Discussion(id="d_exp2", author_id="u_exp", content="Export reply", parent_id="d_exp1")
        self.db.create_discussion(d_root)
        self.db.create_discussion(d_reply)
        # Direct messages (sent & received)
        dm_sent = DirectMessage(id="dm_s1", sender_id="u_exp", recipient_id="u_peer", content="Hello peer")
        dm_recv = DirectMessage(id="dm_r1", sender_id="u_peer", recipient_id="u_exp", content="Hello export")
        self.db.create_direct_message(dm_sent)
        self.db.create_direct_message(dm_recv)

        # Export user data
        export = self.db.export_user_data("u_exp")
        self.assertIsNotNone(export)
        self.assertIn("user", export)
        self.assertEqual(export["user"]["id"], "u_exp")
        self.assertEqual(export["user"]["username"], "export_user")
        self.assertEqual(export["user"]["bio"], "Export Bio")

        # Verify discussions
        self.assertIn("discussions", export)
        self.assertIn("replies", export)
        self.assertEqual(len(export["discussions"]), 1)
        self.assertEqual(export["discussions"][0]["id"], "d_exp1")
        self.assertEqual(len(export["replies"]), 1)
        self.assertEqual(export["replies"][0]["id"], "d_exp2")

        # Verify messages
        self.assertIn("messages", export)
        self.assertIn("sent_messages", export)
        self.assertIn("received_messages", export)
        self.assertEqual(len(export["sent_messages"]), 1)
        self.assertEqual(len(export["received_messages"]), 1)
        self.assertEqual(len(export["messages"]), 2)

        # Verify connections, subscriptions, memberships, blocks
        self.assertIn("connections", export)
        self.assertEqual(len(export["connections"]), 1)
        self.assertEqual(export["connections"][0]["followed_id"], "u_peer")

        self.assertIn("topic_subscriptions", export)
        self.assertIn("ai", export["topic_subscriptions"])

        self.assertIn("memberships", export)
        self.assertEqual(len(export["memberships"]), 1)
        self.assertEqual(export["memberships"][0]["community_id"], "c_exp")

        self.assertIn("blocks", export)
        self.assertEqual(len(export["blocks"]), 1)
        self.assertEqual(export["blocks"][0]["blocked_id"], "u_blocked_guy")

        self.assertIn("exported_at", export)

        # Export non-existent user returns None
        self.assertIsNone(self.db.export_user_data("non_existent"))

    def test_academic_course_crud_and_search(self):
        u_prof = User(id="u_prof", username="professor_oak")
        self.db.create_user(u_prof)

        # Create Course
        c1 = Course(
            id="c_cs101",
            code="CS101",
            name="Introduction to Computer Science",
            department="Computer Science",
            institution="Stanford",
            term="Fall 2026",
            instructor="Prof. Oak",
            description="Fundamental programming concepts in Python and C",
            created_by="u_prof"
        )
        created = self.db.create_course(c1)
        self.assertEqual(created.id, "c_cs101")
        self.assertEqual(created.code, "CS101")

        # Duplicate ID should return None
        self.assertIsNone(self.db.create_course(c1))

        # Retrieve Course
        fetched = self.db.get_course("c_cs101")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Introduction to Computer Science")
        self.assertEqual(fetched.institution, "Stanford")

        # Retrieve by code
        by_code = self.db.get_course_by_code("cs101", institution="stanford", term="fall 2026")
        self.assertIsNotNone(by_code)
        self.assertEqual(by_code.id, "c_cs101")

        # Aliases test: AcademicSpace and CourseSpace
        c2 = AcademicSpace(
            id="c_math201",
            code="MATH201",
            name="Linear Algebra",
            department="Mathematics",
            institution="MIT",
            term="Fall 2026",
            created_by="u_prof"
        )
        self.db.add_course(c2)
        self.assertIsNotNone(self.db.get_academic_space("c_math201"))
        self.assertEqual(len(self.db.get_academic_spaces()), 2)

        # Search Courses
        search_res = self.db.search_courses("Computer")
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0].id, "c_cs101")

        search_res_inst = self.db.search_courses("", institution="MIT")
        self.assertEqual(len(search_res_inst), 1)
        self.assertEqual(search_res_inst[0].id, "c_math201")

        search_res_dept = self.db.get_courses(department="Mathematics")
        self.assertEqual(len(search_res_dept), 1)
        self.assertEqual(search_res_dept[0].id, "c_math201")

        # Update Course
        c1.description = "Updated description with algorithms"
        self.assertTrue(self.db.update_course(c1))
        self.assertEqual(self.db.get_course("c_cs101").description, "Updated description with algorithms")

        # Delete Course
        self.assertTrue(self.db.delete_course("c_math201"))
        self.assertIsNone(self.db.get_course("c_math201"))
        self.assertFalse(self.db.delete_course("c_math201"))

    def test_academic_enrollment_and_classmate_verification(self):
        u1 = User(id="u_s1", username="student1")
        u2 = User(id="u_s2", username="student2")
        u3 = User(id="u_s3", username="student3")
        u4 = User(id="u_s4", username="student4")
        for u in [u1, u2, u3, u4]:
            self.db.create_user(u)

        c = Course(id="c_bio101", code="BIO101", name="General Biology", institution="Harvard", term="Spring 2026")
        self.db.create_course(c)

        # Enrollments
        enr1 = self.db.enroll_in_course(CourseEnrollment(
            id="enr1", course_id="c_bio101", user_id="u_s1", institution="Harvard", term="Spring 2026", role="student"
        ))
        self.assertIsNotNone(enr1)

        enr2 = self.db.enroll_in_course(CourseEnrollment(
            id="enr2", course_id="c_bio101", user_id="u_s2", institution="Harvard", term="Spring 2026", role="ta"
        ))
        self.assertIsNotNone(enr2)

        # Student 3 enrolled in different term/institution
        enr3 = self.db.enroll_in_course(CourseEnrollment(
            id="enr3", course_id="c_bio101", user_id="u_s3", institution="Yale", term="Fall 2025", role="student", is_verified=False
        ))
        self.assertIsNotNone(enr3)

        # Check is_user_enrolled
        self.assertTrue(self.db.is_user_enrolled("c_bio101", "u_s1"))
        self.assertFalse(self.db.is_user_enrolled("c_bio101", "u_s4"))

        # Check get_course_enrollments
        enrollments = self.db.get_course_enrollments("c_bio101")
        self.assertEqual(len(enrollments), 3)

        members = self.db.get_course_members("c_bio101", role="ta")
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].user_id, "u_s2")

        user_courses = self.db.get_user_courses("u_s1")
        self.assertEqual(len(user_courses), 1)
        self.assertEqual(user_courses[0].id, "c_bio101")

        # Verification Logic
        # u1 and u2 are both enrolled in same course, same institution and term, is_verified=True -> verified classmates
        self.assertTrue(self.db.is_verified_classmate("u_s1", "u_s2", "c_bio101"))
        self.assertTrue(self.db.is_verified_classmate("u_s1", "u_s2"))  # across all shared courses

        # u1 and u3 have different institutions and terms, u3 is_verified=False
        self.assertFalse(self.db.is_verified_classmate("u_s1", "u_s3", "c_bio101"))

        # Explicit verification
        self.assertTrue(self.db.verify_classmate("c_bio101", "u_s3", verified=True))
        # Now u3 is verified in the course enrollment
        self.assertTrue(self.db.is_verified_classmate("u_s1", "u_s3", "c_bio101"))

        # Get verified classmates list
        classmates = self.db.get_verified_classmates("u_s1", "c_bio101")
        classmate_ids = [u.id for u in classmates]
        self.assertIn("u_s2", classmate_ids)
        self.assertIn("u_s3", classmate_ids)
        self.assertNotIn("u_s1", classmate_ids)
        self.assertNotIn("u_s4", classmate_ids)

        # Unenroll
        self.assertTrue(self.db.unenroll_from_course("c_bio101", "u_s3"))
        self.assertFalse(self.db.is_user_enrolled("c_bio101", "u_s3"))

    def test_academic_course_and_study_group_discussions(self):
        u1 = User(id="u_a1", username="alice_acad")
        u2 = User(id="u_a2", username="bob_acad")
        self.db.create_user(u1)
        self.db.create_user(u2)

        c = Course(id="c_econ101", code="ECON101", name="Principles of Economics")
        self.db.create_course(c)

        sg = StudyGroup(id="sg_econ_team", name="Econ Final Prep", course_id="c_econ101", created_by="u_a1")
        self.db.create_study_group(sg)

        # Course Discussion
        d_course_root = self.db.create_course_discussion("c_econ101", Discussion(
            id="d_c1", author_id="u_a1", content="Exam 1 review questions thread"
        ))
        self.assertIsNotNone(d_course_root)
        self.assertEqual(d_course_root.course_id, "c_econ101")

        # Reply to course discussion
        d_course_reply = self.db.create_course_discussion("c_econ101", Discussion(
            id="d_c2", author_id="u_a2", content="What is question 4 asking?", parent_id="d_c1"
        ))
        self.assertIsNotNone(d_course_reply)

        # Study Group Discussion
        d_sg = Discussion(
            id="d_sg1", author_id="u_a1", content="Meeting at library at 5pm", study_group_id="sg_econ_team"
        )
        self.db.create_discussion(d_sg)

        # Retrieve course discussions (top-level only vs with replies)
        course_discs = self.db.get_course_discussions("c_econ101", include_replies=False)
        self.assertEqual(len(course_discs), 1)
        self.assertEqual(course_discs[0].id, "d_c1")

        course_discs_all = self.db.get_course_discussions("c_econ101", include_replies=True)
        self.assertEqual(len(course_discs_all), 2)

        # Retrieve study group discussions
        sg_discs = self.db.get_study_group_discussions("sg_econ_team")
        self.assertEqual(len(sg_discs), 1)
        self.assertEqual(sg_discs[0].id, "d_sg1")

    def test_academic_syllabus_and_resource_sharing(self):
        u_prof = User(id="u_prof2", username="dr_smith")
        u_stud = User(id="u_stud2", username="charlie_stud")
        self.db.create_user(u_prof)
        self.db.create_user(u_stud)

        c = Course(id="c_phys201", code="PHYS201", name="Mechanics and Waves")
        self.db.create_course(c)

        # Create Syllabus
        syllabus = CourseResource(
            id="res_syl",
            course_id="c_phys201",
            title="PHYS 201 Fall Syllabus",
            description="Official syllabus and grading rubric",
            resource_type="syllabus",
            url="https://example.edu/phys201/syllabus.pdf",
            author_id="u_prof2",
            is_official=True
        )
        self.db.create_course_resource(syllabus)

        # Retrieve Syllabus
        fetched_syl = self.db.get_course_syllabus("c_phys201")
        self.assertIsNotNone(fetched_syl)
        self.assertEqual(fetched_syl.id, "res_syl")
        self.assertTrue(fetched_syl.is_official)

        # Create Lecture Notes & Study Guide
        res_notes = StudyResource(
            id="res_notes1",
            course_id="c_phys201",
            title="Week 1 Kinematics Summary",
            description="Detailed lecture notes and formula sheet",
            resource_type="lecture_notes",
            author_id="u_stud2",
            tags=["kinematics", "week1", "formulas"]
        )
        self.db.add_course_resource(res_notes)

        # Filter resources by type and tags
        notes = self.db.get_course_resources("c_phys201", resource_type="lecture_notes")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].id, "res_notes1")

        tagged = self.db.get_course_resources("c_phys201", tag="formulas")
        self.assertEqual(len(tagged), 1)
        self.assertEqual(tagged[0].id, "res_notes1")

        # Endorse Resource
        success = self.db.endorse_resource("res_notes1", user_id="u_prof2")
        self.assertTrue(success)
        self.assertEqual(self.db.get_resource("res_notes1").endorsements_count, 1)

        # Verify author received notification
        notifs = self.db.get_user_notifications("u_stud2")
        self.assertTrue(any(n.type == "resource_endorsed" for n in notifs))

        # Upvote resource
        self.assertTrue(self.db.upvote_resource("res_notes1"))
        self.assertEqual(self.db.get_resource("res_notes1").upvotes_count, 1)

        # Delete resource
        self.assertTrue(self.db.delete_resource("res_notes1"))
        self.assertIsNone(self.db.get_resource("res_notes1"))

    def test_academic_verified_classmate_study_groups(self):
        u1 = User(id="u_lead", username="group_leader")
        u2 = User(id="u_classmate", username="verified_peer")
        u3 = User(id="u_outsider", username="outsider_user")
        for u in [u1, u2, u3]:
            self.db.create_user(u)

        c = Course(id="c_chem301", code="CHEM301", name="Organic Chemistry", institution="Berkeley", term="Fall 2026")
        self.db.create_course(c)

        # Enroll leader and classmate with verified status
        self.db.enroll_in_course(CourseEnrollment(
            id="enr_l", course_id="c_chem301", user_id="u_lead", institution="Berkeley", term="Fall 2026", is_verified=True
        ))
        self.db.enroll_in_course(CourseEnrollment(
            id="enr_c", course_id="c_chem301", user_id="u_classmate", institution="Berkeley", term="Fall 2026", is_verified=True
        ))
        # u3 is not enrolled

        # Create Verified-Only Study Group with capacity limit of 2
        sg = AcademicStudyGroup(
            id="sg_orgo",
            course_id="c_chem301",
            name="Orgo Reaction Mechanisms Study Team",
            description="Focused problem sets for midterm",
            created_by="u_lead",
            verified_only=True,
            max_members=2
        )
        self.db.create_study_group(sg)

        # Leader should automatically be a member with leader role
        self.assertTrue(self.db.is_study_group_member("sg_orgo", "u_lead"))
        leader_member = self.db.get_study_group_member("sg_orgo", "u_lead")
        self.assertEqual(leader_member.role, "leader")

        # Outsider attempting to join verified-only study group should raise PermissionError
        with self.assertRaises(PermissionError):
            self.db.join_study_group("sg_orgo", "u_outsider")

        # Verified classmate joins successfully
        member_c = self.db.join_study_group("sg_orgo", "u_classmate")
        self.assertIsNotNone(member_c)
        self.assertTrue(self.db.is_study_group_member("sg_orgo", "u_classmate"))

        # Study group is now at capacity (2/2). Another verified user shouldn't be able to join.
        u4 = User(id="u_classmate2", username="verified_peer2")
        self.db.create_user(u4)
        self.db.enroll_in_course(CourseEnrollment(
            id="enr_c2", course_id="c_chem301", user_id="u_classmate2", institution="Berkeley", term="Fall 2026", is_verified=True
        ))
        with self.assertRaises(ValueError):
            self.db.join_study_group("sg_orgo", "u_classmate2")

        # Search study groups
        sg_search = self.db.search_study_groups("Reaction")
        self.assertEqual(len(sg_search), 1)
        self.assertEqual(sg_search[0].id, "sg_orgo")

        # Update member role
        self.assertTrue(self.db.update_study_group_member_role("sg_orgo", "u_classmate", "moderator"))
        self.assertEqual(self.db.get_study_group_member("sg_orgo", "u_classmate").role, "moderator")

        # Member leaves
        self.assertTrue(self.db.leave_study_group("sg_orgo", "u_classmate"))
        self.assertFalse(self.db.is_study_group_member("sg_orgo", "u_classmate"))

        # Delete study group
        self.assertTrue(self.db.delete_study_group("sg_orgo"))
        self.assertIsNone(self.db.get_study_group("sg_orgo"))

    def test_academic_unified_search_and_export(self):
        u = User(id="u_export_acad", username="scholar")
        self.db.create_user(u)

        c = Course(id="c_lit100", code="LIT100", name="World Literature", created_by="u_export_acad")
        self.db.create_course(c)

        self.db.enroll_in_course(CourseEnrollment(
            id="enr_lit", course_id="c_lit100", user_id="u_export_acad", institution="Oxford", term="2026", is_verified=True
        ))

        sg = StudyGroup(id="sg_lit", name="Shakespeare Analysis", course_id="c_lit100", created_by="u_export_acad")
        self.db.create_study_group(sg)

        res = CourseResource(
            id="res_lit1", course_id="c_lit100", title="Hamlet Essay Guide", author_id="u_export_acad"
        )
        self.db.create_course_resource(res)

        # Unified search
        search_courses = self.db.search("World Literature", search_type="courses")
        self.assertEqual(len(search_courses["courses"]), 1)

        search_groups = self.db.search("Shakespeare", search_type="study_groups")
        self.assertEqual(len(search_groups["study_groups"]), 1)

        # Export user data
        export = self.db.export_user_data("u_export_acad")
        self.assertIsNotNone(export)
        self.assertIn("course_enrollments", export)
        self.assertEqual(len(export["course_enrollments"]), 1)
        self.assertIn("study_groups", export)
        self.assertEqual(len(export["study_groups"]), 1)
        self.assertIn("shared_resources", export)
        self.assertEqual(len(export["shared_resources"]), 1)

    def test_media_accessibility_metadata(self):
        u1 = User(id="u_med1", username="photographer")
        self.db.create_user(u1)

        # 1. Create media attachment with accessibility metadata
        m1 = MediaAttachment(
            id="med_img1",
            url="https://example.com/images/campus.jpg",
            media_type="image",
            alt_text="Sunny university campus courtyard with brick paths and oak trees",
            description="Main quad in autumn",
            uploader_id="u_med1",
            content_warnings=["campus_life"],
            is_sensitive=False
        )
        created = self.db.create_media(m1)
        self.assertEqual(created.id, "med_img1")
        self.assertTrue(created.has_alt_text)
        self.assertFalse(created.has_audio_transcript)

        # 2. Retrieve media
        fetched = self.db.get_media("med_img1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.alt_text, "Sunny university campus courtyard with brick paths and oak trees")
        self.assertEqual(fetched.media_type, "image")
        self.assertEqual(fetched.uploader_id, "u_med1")

        # 3. Create audio media with transcript
        m2 = MediaAttachment(
            id="med_aud1",
            url="https://example.com/audio/lecture1.mp3",
            media_type="audio",
            audio_transcript="Welcome to Computer Science 101. Today we discuss time complexity and Big-O notation.",
            captions_url="https://example.com/captions/lecture1.vtt",
            uploader_id="u_med1"
        )
        self.db.create_media(m2)
        fetched_aud = self.db.get_media("med_aud1")
        self.assertIsNotNone(fetched_aud)
        self.assertTrue(fetched_aud.has_audio_transcript)
        self.assertEqual(fetched_aud.transcript, fetched_aud.audio_transcript)
        self.assertEqual(fetched_aud.captions_url, "https://example.com/captions/lecture1.vtt")

        # 4. User media list
        user_media = self.db.get_user_media("u_med1")
        self.assertEqual(len(user_media), 2)

        # 5. Update accessibility metadata
        updated = self.db.update_media_accessibility(
            "med_img1",
            alt_text="Updated alt text: Wide shot of university quad with students walking",
            description="Autumn quad scenic photo"
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.alt_text, "Updated alt text: Wide shot of university quad with students walking")
        self.assertEqual(updated.description, "Autumn quad scenic photo")

        # 6. Create discussion with media attachment
        d1 = Discussion(
            id="d_media_post",
            author_id="u_med1",
            content="Check out the campus today!",
            alt_text="Photo of campus quad in autumn",
            content_warnings=["photography"],
            media=[m1]
        )
        self.db.create_discussion(d1)
        fetched_d = self.db.get_discussion("d_media_post")
        self.assertIsNotNone(fetched_d)
        self.assertEqual(fetched_d.alt_text, "Photo of campus quad in autumn")
        self.assertEqual(fetched_d.content_warnings, ["photography"])
        self.assertTrue(fetched_d.has_content_warning)

        # 7. Discussion media retrieval & attach media
        disc_media = self.db.get_discussion_media("d_media_post")
        self.assertEqual(len(disc_media), 1)
        self.assertEqual(disc_media[0].id, "med_img1")

        # Attach second media to discussion
        self.db.attach_media_to_discussion("d_media_post", ["med_aud1"])
        disc_media2 = self.db.get_discussion_media("d_media_post")
        self.assertEqual(len(disc_media2), 2)

        # 8. Delete media
        deleted = self.db.delete_media("med_img1")
        self.assertTrue(deleted)
        self.assertIsNone(self.db.get_media("med_img1"))

    def test_user_content_filtering_preferences(self):
        u1 = User(id="u_filter_user", username="reader")
        u2 = User(id="u_poster_user", username="author")
        self.db.create_user(u1)
        self.db.create_user(u2)

        # 1. Default preferences
        default_prefs = self.db.get_content_filter_preferences("u_filter_user")
        self.assertEqual(default_prefs.user_id, "u_filter_user")
        self.assertEqual(default_prefs.mute_keywords, [])
        self.assertEqual(default_prefs.content_warning_tags, [])
        self.assertEqual(default_prefs.filter_level, "hide")

        # 2. Set preferences
        prefs = ContentFilterPreferences(
            user_id="u_filter_user",
            mute_keywords=["spoilers", "crypto"],
            content_warning_tags=["violence", "politics"],
            hide_sensitive_media=True,
            filter_level="hide",
            filter_notifications=True
        )
        saved = self.db.set_content_filter_preferences(prefs)
        self.assertEqual(saved.mute_keywords, ["spoilers", "crypto"])
        self.assertEqual(saved.content_warning_tags, ["violence", "politics"])
        self.assertTrue(saved.hide_sensitive_media)

        # 3. Add and remove mute keywords
        self.db.add_mute_keyword("u_filter_user", "spam")
        kw = self.db.get_mute_keywords("u_filter_user")
        self.assertIn("spam", kw)
        self.assertEqual(len(kw), 3)

        self.db.remove_mute_keyword("u_filter_user", "crypto")
        kw_after = self.db.get_mute_keywords("u_filter_user")
        self.assertNotIn("crypto", kw_after)
        self.assertIn("spoilers", kw_after)

        # 4. Add and remove content warning tags
        self.db.add_content_warning_tag("u_filter_user", "flashing_lights")
        cw = self.db.get_content_warning_tags("u_filter_user")
        self.assertIn("flashing_lights", cw)

        self.db.remove_content_warning_tag("u_filter_user", "violence")
        cw_after = self.db.get_content_warning_tags("u_filter_user")
        self.assertNotIn("violence", cw_after)
        self.assertIn("politics", cw_after)

        # 5. should_filter_discussion_for_user and filter_discussions_for_user
        d_clean = Discussion(id="d_clean", author_id="u_poster_user", content="Today we learned Python syntax")
        d_spoiler = Discussion(id="d_spoil", author_id="u_poster_user", content="Huge SPOILERS for the final episode!")
        d_cw = Discussion(id="d_pol", author_id="u_poster_user", content="Debate summary", content_warnings=["politics"])
        d_own = Discussion(id="d_own", author_id="u_filter_user", content="My own post about spoilers and politics", content_warnings=["politics"])

        for d in [d_clean, d_spoiler, d_cw, d_own]:
            self.db.create_discussion(d)

        self.assertFalse(self.db.should_filter_discussion_for_user("u_filter_user", d_clean))
        self.assertTrue(self.db.should_filter_discussion_for_user("u_filter_user", d_spoiler))
        self.assertTrue(self.db.should_filter_discussion_for_user("u_filter_user", d_cw))
        self.assertFalse(self.db.should_filter_discussion_for_user("u_filter_user", d_own))

        filtered_list = self.db.filter_discussions_for_user("u_filter_user", [d_clean, d_spoiler, d_cw, d_own])
        filtered_ids = [d.id for d in filtered_list]
        self.assertIn("d_clean", filtered_ids)
        self.assertIn("d_own", filtered_ids)
        self.assertNotIn("d_spoil", filtered_ids)
        self.assertNotIn("d_pol", filtered_ids)

        # 6. Feed integration with content filters
        self.db.create_connection("u_filter_user", "u_poster_user")
        feed = self.db.get_feed("u_filter_user", mode="chronological")
        feed_ids = [item.id for item in feed]
        self.assertIn("d_clean", feed_ids)
        self.assertIn("d_own", feed_ids)
        self.assertNotIn("d_spoil", feed_ids)
        self.assertNotIn("d_pol", feed_ids)

    def test_user_accessibility_settings(self):
        u1 = User(id="u_acc_user", username="access_user")
        self.db.create_user(u1)

        # 1. Default accessibility settings
        default_sett = self.db.get_accessibility_settings("u_acc_user")
        self.assertEqual(default_sett.user_id, "u_acc_user")
        self.assertFalse(default_sett.high_contrast)
        self.assertFalse(default_sett.reduce_motion)
        self.assertFalse(default_sett.screen_reader_optimized)
        self.assertEqual(default_sett.font_size, "medium")
        self.assertFalse(default_sett.closed_captions_enabled)
        self.assertTrue(default_sett.audio_transcripts_enabled)
        self.assertFalse(default_sett.alt_text_required_on_post)
        self.assertFalse(default_sett.dyslexia_font)
        self.assertEqual(default_sett.color_blind_mode, "none")

        # 2. Set customized accessibility settings
        settings = UserAccessibilitySettings(
            user_id="u_acc_user",
            high_contrast=True,
            reduce_motion=True,
            screen_reader_optimized=True,
            font_size="large",
            closed_captions_enabled=True,
            audio_transcripts_enabled=True,
            alt_text_required_on_post=True,
            autoplay_media=False,
            dyslexia_font=True,
            color_blind_mode="deuteranopia"
        )
        saved = self.db.set_accessibility_settings(settings)
        self.assertTrue(saved.high_contrast)
        self.assertTrue(saved.high_contrast_mode)
        self.assertTrue(saved.reduce_motion)
        self.assertTrue(saved.screen_reader_optimized)
        self.assertTrue(saved.screen_reader_mode)
        self.assertEqual(saved.font_size, "large")
        self.assertTrue(saved.closed_captions_enabled)
        self.assertTrue(saved.captions_enabled)
        self.assertTrue(saved.alt_text_required_on_post)
        self.assertTrue(saved.dyslexia_font)
        self.assertEqual(saved.color_blind_mode, "deuteranopia")

        # 3. Update individual fields via update_accessibility_settings
        updated = self.db.update_accessibility_settings(
            "u_acc_user",
            font_size="x-large",
            color_blind_mode="protanopia"
        )
        self.assertEqual(updated.font_size, "x-large")
        self.assertEqual(updated.color_blind_mode, "protanopia")
        self.assertTrue(updated.high_contrast)

        # 4. User data export includes accessibility and filter settings
        m = MediaAttachment(id="med_exp1", url="https://example.com/pic.png", uploader_id="u_acc_user", alt_text="User pic")
        self.db.create_media(m)

        export = self.db.export_user_data("u_acc_user")
        self.assertIsNotNone(export)
        self.assertIn("accessibility_settings", export)
        self.assertTrue(export["accessibility_settings"]["high_contrast"])
        self.assertEqual(export["accessibility_settings"]["font_size"], "x-large")
        self.assertIn("content_filter_preferences", export)
        self.assertIn("media_attachments", export)
        self.assertEqual(len(export["media_attachments"]), 1)
        self.assertEqual(export["media_attachments"][0]["id"], "med_exp1")


class DummyAPIHandler(api_server.SocialAPIHandler):
    def __init__(self, method, path, body=None, headers=None):
        self.command = method
        self.path = path
        self.requestline = f"{method} {path} HTTP/1.1"
        self.request_version = "HTTP/1.1"
        self.close_connection = True
        body_bytes = json.dumps(body).encode("utf-8") if isinstance(body, dict) else (body or b"")
        self.rfile = io.BytesIO(body_bytes)
        self.wfile = io.BytesIO()
        self.headers = headers or {"Content-Length": str(len(body_bytes))}
        self._response_status = None
        self._response_headers = {}

    def send_response(self, code, message=None):
        self._response_status = code

    def send_header(self, keyword, value):
        self._response_headers[keyword] = value

    def end_headers(self):
        pass

    def get_response_json(self):
        self.wfile.seek(0)
        return json.loads(self.wfile.read().decode('utf-8'))


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.test_db = SocialDatabase(":memory:")
        self._orig_db = api_server.db
        api_server.db = self.test_db

    def tearDown(self):
        api_server.db = self._orig_db

    def test_api_discussion_creation_and_retrieval(self):
        u = User(id="u1", username="alice")
        self.test_db.create_user(u)

        # POST /discussions
        handler = DummyAPIHandler("POST", "/discussions", body={"id": "d1", "author_id": "u1", "content": "Hello world"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["id"], "d1")
        self.assertEqual(res["content"], "Hello world")

        # GET /discussions/d1
        handler = DummyAPIHandler("GET", "/discussions/d1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["id"], "d1")
        self.assertEqual(res["value_endorsements"], 0)

        # GET /discussions/d_unknown (404)
        handler = DummyAPIHandler("GET", "/discussions/d_unknown")
        handler.do_GET()
        self.assertEqual(handler._response_status, 404)

    def test_api_discussion_endorsement(self):
        u = User(id="u1", username="alice")
        self.test_db.create_user(u)
        d = Discussion(id="d1", author_id="u1", content="Insightful post")
        self.test_db.create_discussion(d)

        # POST /discussions/d1/endorse
        handler = DummyAPIHandler("POST", "/discussions/d1/endorse")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["value_endorsements"], 1)

        # POST /endorsements with {"discussion_id": "d1"}
        handler = DummyAPIHandler("POST", "/endorsements", body={"discussion_id": "d1"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["value_endorsements"], 2)

        # Endorse non-existent
        handler = DummyAPIHandler("POST", "/discussions/non_existent/endorse")
        handler.do_POST()
        self.assertEqual(handler._response_status, 404)

    def test_api_discussion_replies(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        root = Discussion(id="d_root", author_id="u1", content="Topic question")
        self.test_db.create_discussion(root)

        # POST /discussions/d_root/replies
        handler = DummyAPIHandler("POST", "/discussions/d_root/replies", body={"id": "r1", "author_id": "u2", "content": "Helpful answer"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["id"], "r1")
        self.assertEqual(res["parent_id"], "d_root")

        # GET /discussions/d_root/replies
        handler = DummyAPIHandler("GET", "/discussions/d_root/replies")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "r1")
        self.assertEqual(res[0]["content"], "Helpful answer")

        # Reply to non-existent parent
        handler = DummyAPIHandler("POST", "/discussions/non_existent/replies", body={"author_id": "u2", "content": "Orphan"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 404)

    def test_api_community_and_channel_endpoints(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        # POST /communities
        handler = DummyAPIHandler("POST", "/communities", body={
            "id": "c1", "name": "AI Builders", "creator_id": "u1", "description": "Building AI"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["name"], "AI Builders")

        # GET /communities/c1
        handler = DummyAPIHandler("GET", "/communities/c1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)

        # POST /communities/c1/join
        handler = DummyAPIHandler("POST", "/communities/c1/join", body={"user_id": "u2"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # GET /communities/c1/members
        handler = DummyAPIHandler("GET", "/communities/c1/members")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(len(res), 2)

        # GET /users/u2/communities
        handler = DummyAPIHandler("GET", "/users/u2/communities")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(len(res), 1)

        # POST /communities/c1/channels
        handler = DummyAPIHandler("POST", "/communities/c1/channels", body={
            "id": "ch_models", "name": "models", "description": "Model discussions"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /communities/c1/channels
        handler = DummyAPIHandler("GET", "/communities/c1/channels")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "models")

        # POST /channels/ch_models/discussions
        handler = DummyAPIHandler("POST", "/channels/ch_models/discussions", body={
            "id": "d_model1", "author_id": "u2", "content": "Transformer architecture question"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /channels/ch_models/discussions
        handler = DummyAPIHandler("GET", "/channels/ch_models/discussions")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "d_model1")

    def test_api_moderation_and_bans(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="troll")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        c1 = Community(id="c1", name="Friendly Community", creator_id="u1")
        self.test_db.create_community(c1)

        d = Discussion(id="d_bad", author_id="u2", content="Bad content", community_id="c1")
        self.test_db.create_discussion(d)

        # POST /reports
        handler = DummyAPIHandler("POST", "/reports", body={
            "id": "rep1", "reporter_id": "u1", "target_type": "discussion",
            "target_id": "d_bad", "reason": "Toxic behavior"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /reports
        handler = DummyAPIHandler("GET", "/reports?status=pending")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(len(res), 1)

        # POST /discussions/d_bad/moderate (hide)
        handler = DummyAPIHandler("POST", "/discussions/d_bad/moderate", body={"action": "hide"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Discussion hidden from general list
        handler = DummyAPIHandler("GET", "/discussions")
        handler.do_GET()
        self.assertEqual(len(handler.get_response_json()), 0)

        # POST /reports/rep1/resolve
        handler = DummyAPIHandler("POST", "/reports/rep1/resolve", body={"status": "resolved"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # POST /communities/c1/ban
        handler = DummyAPIHandler("POST", "/communities/c1/ban", body={
            "user_id": "u2", "moderator_id": "u1", "reason": "Repeated violations"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Banned user posting discussion -> 403
        handler = DummyAPIHandler("POST", "/discussions", body={
            "author_id": "u2", "content": "Troll attempt", "community_id": "c1"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 403)

        # GET /communities/c1/bans
        handler = DummyAPIHandler("GET", "/communities/c1/bans")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # POST /communities/c1/unban
        handler = DummyAPIHandler("POST", "/communities/c1/unban", body={"user_id": "u2"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertFalse(self.test_db.is_user_banned("c1", "u2"))

    def test_api_notifications_endpoints(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        # Create root post
        d1 = Discussion(id="d1", author_id="u1", content="Alice initial topic")
        self.test_db.create_discussion(d1)

        # Bob replies and mentions Alice
        handler = DummyAPIHandler("POST", "/discussions", body={
            "id": "d2", "author_id": "u2", "content": "Bob reply @alice", "parent_id": "d1"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /users/u1/notifications
        handler = DummyAPIHandler("GET", "/users/u1/notifications")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        notifs = handler.get_response_json()
        self.assertTrue(len(notifs) >= 1)
        notif_id = notifs[0]["id"]

        # GET /users/u1/notifications/count
        handler = DummyAPIHandler("GET", "/users/u1/notifications/count")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertTrue(res["unread_count"] >= 1)

        # POST /notifications/<id>/read
        handler = DummyAPIHandler("POST", f"/notifications/{notif_id}/read")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # POST /users/u1/notifications/read_all
        handler = DummyAPIHandler("POST", "/users/u1/notifications/read_all")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Confirm count is 0
        handler = DummyAPIHandler("GET", "/users/u1/notifications/count")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["unread_count"], 0)

    def test_api_search_discovery_endpoints(self):
        u1 = User(id="u1", username="solaris_dev", is_publicly_discoverable=True)
        self.test_db.create_user(u1)
        c1 = Community(id="c1", name="Solaris Community", description="Solar energy tech", creator_id="u1")
        self.test_db.create_community(c1)
        d1 = Discussion(id="d1", author_id="u1", content="Solaris power breakthroughs in 2026")
        self.test_db.create_discussion(d1)

        # GET /search?q=solaris
        handler = DummyAPIHandler("GET", "/search?q=solaris")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(len(res["users"]), 1)
        self.assertEqual(len(res["communities"]), 1)
        self.assertEqual(len(res["discussions"]), 1)

        # GET /discovery?q=solaris
        handler = DummyAPIHandler("GET", "/discovery?q=solaris")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()["discussions"]), 1)

        # GET /search/discussions?q=solaris
        handler = DummyAPIHandler("GET", "/search/discussions?q=solaris")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /search/communities?q=solaris
        handler = DummyAPIHandler("GET", "/search/communities?q=solaris")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /search/users?q=solaris
        handler = DummyAPIHandler("GET", "/search/users?q=solaris")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

    def test_api_direct_messaging_endpoints(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        # POST /messages
        handler = DummyAPIHandler("POST", "/messages", body={
            "id": "dm1", "sender_id": "u1", "recipient_id": "u2", "content": "Hello Bob via API"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["id"], "dm1")
        self.assertEqual(res["delivery_state"], "sent")

        # GET /messages/dm1
        handler = DummyAPIHandler("GET", "/messages/dm1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["content"], "Hello Bob via API")

        # GET /messages/dm_unknown -> 404
        handler = DummyAPIHandler("GET", "/messages/dm_unknown")
        handler.do_GET()
        self.assertEqual(handler._response_status, 404)

        # GET /conversations/u1/u2
        handler = DummyAPIHandler("GET", "/conversations/u1/u2")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /messages?user1=u1&user2=u2
        handler = DummyAPIHandler("GET", "/messages?user1=u1&user2=u2")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /users/u1/conversations
        handler = DummyAPIHandler("GET", "/users/u1/conversations")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

    def test_api_message_delivery_states(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        dm = DirectMessage(id="dm1", sender_id="u1", recipient_id="u2", content="Secret memo")
        self.test_db.create_direct_message(dm)

        # POST /messages/dm1/deliver
        handler = DummyAPIHandler("POST", "/messages/dm1/deliver")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["delivery_state"], "delivered")

        # POST /messages/dm1/read
        handler = DummyAPIHandler("POST", "/messages/dm1/read")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["delivery_state"], "read")

        # Send another message and mark whole conversation as read via API
        dm2 = DirectMessage(id="dm2", sender_id="u1", recipient_id="u2", content="Follow up")
        self.test_db.create_direct_message(dm2)

        handler = DummyAPIHandler("POST", "/conversations/u2/u1/read")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["updated_count"], 1)

        # GET /users/u2/messages/count
        handler = DummyAPIHandler("GET", "/users/u2/messages/count")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["unread_count"], 0)

    def test_api_blocklist_privacy_controls(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="harasser")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        # POST /users/u1/block
        handler = DummyAPIHandler("POST", "/users/u1/block", body={"blocked_id": "u2", "reason": "Trolling"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # GET /users/u1/blocks
        handler = DummyAPIHandler("GET", "/users/u1/blocks")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        blocks = handler.get_response_json()
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["blocked_id"], "u2")

        # Blocked user attempting to send message -> 403 Forbidden
        handler = DummyAPIHandler("POST", "/messages", body={
            "id": "dm_fail", "sender_id": "u2", "recipient_id": "u1", "content": "Spam attack"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 403)

        # DELETE /blocks/u1/u2 (Unblock)
        handler = DummyAPIHandler("DELETE", "/blocks/u1/u2")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

        # Now sending succeeds
        handler = DummyAPIHandler("POST", "/messages", body={
            "id": "dm_success", "sender_id": "u2", "recipient_id": "u1", "content": "Peace message"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

    def test_api_multi_mode_feed_endpoints(self):
        u1 = User(id="u1", username="alice", interests=["distributed_systems", "algorithms"])
        u2 = User(id="u2", username="bob", interests=["databases"])
        u3 = User(id="u3", username="charlie", interests=["algorithms"])
        for u in [u1, u2, u3]:
            self.test_db.create_user(u)

        self.test_db.create_connection("u1", "u2")

        c1 = Community(id="c1", name="Systems Hub", creator_id="u1")
        self.test_db.create_community(c1)

        d1 = Discussion(id="d1", author_id="u1", content="Consensus algorithms in distributed systems", community_id="c1")
        d2 = Discussion(id="d2", author_id="u2", content="B-Tree indexes in database engines")
        d3 = Discussion(id="d3", author_id="u3", content="Graph search algorithms and optimization")
        for d in [d1, d2, d3]:
            self.test_db.create_discussion(d)

        # 1. GET /feed/<user_id>?mode=following
        handler = DummyAPIHandler("GET", "/feed/u1?mode=following")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        feed = handler.get_response_json()
        self.assertEqual(len(feed), 2)
        feed_ids = [item["id"] for item in feed]
        self.assertIn("d1", feed_ids)
        self.assertIn("d2", feed_ids)
        self.assertIn("mode:following", feed[0]["explanation_tags"])

        # 2. GET /feed/<user_id>?mode=interest_matched
        handler = DummyAPIHandler("GET", "/feed/u1?mode=interest_matched")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        feed_int = handler.get_response_json()
        int_ids = [item["id"] for item in feed_int]
        self.assertIn("d1", int_ids)
        self.assertIn("d3", int_ids)
        self.assertNotIn("d2", int_ids)
        self.assertIn("mode:interest_matched", feed_int[0]["explanation_tags"])
        self.assertTrue(len(feed_int[0]["explanation"]) > 0)

        # 3. GET /feed/<user_id>/following
        handler = DummyAPIHandler("GET", "/feed/u1/following")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 2)

        # 4. GET /feed/<user_id>/interests
        handler = DummyAPIHandler("GET", "/feed/u1/interests")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 2)

        # 5. GET /feed/<user_id>/community/c1
        handler = DummyAPIHandler("GET", "/feed/u1/community/c1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        comm_feed = handler.get_response_json()
        self.assertEqual(len(comm_feed), 1)
        self.assertEqual(comm_feed[0]["id"], "d1")
        self.assertIn("mode:community_scoped", comm_feed[0]["explanation_tags"])

        # 6. GET /users/<user_id>/feed?mode=interest_matched
        handler = DummyAPIHandler("GET", "/users/u1/feed?mode=interest_matched")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 2)

        # 7. POST /feed with custom query body
        handler = DummyAPIHandler("POST", "/feed", body={
            "user_id": "u1",
            "mode": "interest_matched",
            "interests": ["database"]
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        post_feed = handler.get_response_json()
        self.assertIn("matched_interest:database", post_feed[0]["explanation_tags"])

    def test_api_community_roles_and_management(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        u3 = User(id="u3", username="charlie")
        for u in [u1, u2, u3]:
            self.test_db.create_user(u)

        # 1. Create community via API (u1 is creator/owner)
        handler = DummyAPIHandler("POST", "/communities", body={
            "id": "c_api", "name": "API Community", "creator_id": "u1"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # Verify u1 is owner
        handler = DummyAPIHandler("GET", "/communities/c_api/members/u1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["role"], "owner")

        # 2. Add u2 as member
        handler = DummyAPIHandler("POST", "/communities/c_api/members", body={"user_id": "u2"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # 3. Promote u2 to admin (by owner u1)
        handler = DummyAPIHandler("POST", "/communities/c_api/roles", body={
            "actor_id": "u1", "user_id": "u2", "role": "admin"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Check role of u2
        handler = DummyAPIHandler("GET", "/communities/c_api/members/u2")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["role"], "admin")

        # 4. Filter members by role
        handler = DummyAPIHandler("GET", "/communities/c_api/members?role=admin")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        admins = handler.get_response_json()
        self.assertEqual(len(admins), 1)
        self.assertEqual(admins[0]["user_id"], "u2")

        # 5. Transfer ownership from u1 to u2
        handler = DummyAPIHandler("POST", "/communities/c_api/transfer_ownership", body={
            "actor_id": "u1", "new_owner_id": "u2"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Check u2 is owner, u1 is admin
        handler = DummyAPIHandler("GET", "/communities/c_api/members/u2")
        handler.do_GET()
        self.assertEqual(handler.get_response_json()["role"], "owner")
        handler = DummyAPIHandler("GET", "/communities/c_api/members/u1")
        handler.do_GET()
        self.assertEqual(handler.get_response_json()["role"], "admin")

    def test_api_join_requests_workflow(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        u3 = User(id="u3", username="charlie")
        for u in [u1, u2, u3]:
            self.test_db.create_user(u)

        # Create private community
        self.test_db.create_community(Community(id="c_priv", name="Private Hub", creator_id="u1", is_private=True))

        # 1. User 2 requests to join via POST /communities/c_priv/join
        handler = DummyAPIHandler("POST", "/communities/c_priv/join", body={"user_id": "u2"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 202)
        res = handler.get_response_json()
        self.assertTrue(res.get("request_created", False))
        req_id = res.get("join_request", {}).get("id")
        self.assertIsNotNone(req_id)

        # 2. GET /communities/c_priv/join_requests
        handler = DummyAPIHandler("GET", "/communities/c_priv/join_requests")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        reqs = handler.get_response_json()
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0]["user_id"], "u2")
        self.assertEqual(reqs[0]["status"], "pending")

        # 3. GET /users/u2/join_requests
        handler = DummyAPIHandler("GET", "/users/u2/join_requests")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # 4. Approve join request by owner u1
        handler = DummyAPIHandler("POST", f"/communities/c_priv/join_requests/{req_id}/approve", body={
            "actor_id": "u1", "role": "member"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Check u2 is now a member
        handler = DummyAPIHandler("GET", "/communities/c_priv/members/u2")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["role"], "member")

        # 5. User 3 submits join request via POST /communities/c_priv/join_requests
        handler = DummyAPIHandler("POST", "/communities/c_priv/join_requests", body={
            "user_id": "u3", "message": "Let me in"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        u3_req_id = handler.get_response_json()["id"]

        # 6. Reject u3 join request
        handler = DummyAPIHandler("POST", f"/communities/c_priv/join_requests/{u3_req_id}/reject", body={
            "actor_id": "u1"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["status"], "rejected")

    def test_api_invites_workflow(self):
        u1 = User(id="u1", username="alice")
        u2 = User(id="u2", username="bob")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        self.test_db.create_community(Community(id="c_inv", name="Invite Hub", creator_id="u1", is_private=True))

        # 1. Create invite token via POST /communities/c_inv/invites
        handler = DummyAPIHandler("POST", "/communities/c_inv/invites", body={
            "created_by": "u1",
            "token": "API_SECRET_TOKEN",
            "role": "moderator",
            "max_uses": 2
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        inv = handler.get_response_json()
        self.assertEqual(inv["token"], "API_SECRET_TOKEN")
        self.assertEqual(inv["role"], "moderator")

        # 2. GET /invites/API_SECRET_TOKEN
        handler = DummyAPIHandler("GET", "/invites/API_SECRET_TOKEN")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["token"], "API_SECRET_TOKEN")

        # 3. GET /communities/c_inv/invites
        handler = DummyAPIHandler("GET", "/communities/c_inv/invites")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # 4. Use invite via POST /communities/c_inv/invites/API_SECRET_TOKEN/use
        handler = DummyAPIHandler("POST", "/communities/c_inv/invites/API_SECRET_TOKEN/use", body={
            "user_id": "u2"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Check u2 joined as moderator
        handler = DummyAPIHandler("GET", "/communities/c_inv/members/u2")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["role"], "moderator")

        # 5. Revoke invite via DELETE /invites/API_SECRET_TOKEN
        handler = DummyAPIHandler("DELETE", "/invites/API_SECRET_TOKEN", body={"actor_id": "u1"})
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

    def test_api_user_data_export(self):
        u1 = User(id="u_api_exp", username="api_exp_user", bio="API Export Bio")
        self.test_db.create_user(u1)
        self.test_db.create_discussion(Discussion(id="d_api1", author_id="u_api_exp", content="API Post"))

        # GET /users/u_api_exp/export
        handler = DummyAPIHandler("GET", "/users/u_api_exp/export")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["user"]["id"], "u_api_exp")
        self.assertEqual(len(res["discussions"]), 1)
        self.assertEqual(res["discussions"][0]["id"], "d_api1")
        self.assertIn("exported_at", res)

        # POST /users/u_api_exp/export
        handler = DummyAPIHandler("POST", "/users/u_api_exp/export")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        res2 = handler.get_response_json()
        self.assertEqual(res2["user"]["id"], "u_api_exp")

        # GET /users/unknown/export -> 404
        handler = DummyAPIHandler("GET", "/users/unknown/export")
        handler.do_GET()
        self.assertEqual(handler._response_status, 404)

    def test_api_account_deactivation_and_reactivation(self):
        u = User(id="u_api_deact", username="api_deact_user")
        self.test_db.create_user(u)

        # POST /users/u_api_deact/deactivate
        handler = DummyAPIHandler("POST", "/users/u_api_deact/deactivate")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["status"], "deactivated")
        self.assertFalse(self.test_db.is_user_active("u_api_deact"))

        # POST /users/u_api_deact/reactivate
        handler = DummyAPIHandler("POST", "/users/u_api_deact/reactivate")
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["status"], "reactivated")
        self.assertTrue(self.test_db.is_user_active("u_api_deact"))

        # DELETE /users/u_api_deact -> deactivates
        handler = DummyAPIHandler("DELETE", "/users/u_api_deact")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)
        self.assertFalse(self.test_db.is_user_active("u_api_deact"))

    def test_api_user_and_discussion_visibility_controls(self):
        u1 = User(id="u_vis1", username="vis_user_1", visibility="public")
        u2 = User(id="u_vis2", username="vis_user_2")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        # POST /users/u_vis1/visibility
        handler = DummyAPIHandler("POST", "/users/u_vis1/visibility", body={"visibility": "connections_only"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["visibility"], "connections_only")
        self.assertEqual(self.test_db.get_user_visibility("u_vis1"), "connections_only")

        # GET /users/u_vis1/visibility
        handler = DummyAPIHandler("GET", "/users/u_vis1/visibility")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["visibility"], "connections_only")

        # POST /discussions with visibility
        handler = DummyAPIHandler("POST", "/discussions", body={
            "id": "d_vis1", "author_id": "u_vis1", "content": "Restricted post", "visibility": "connections_only"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        self.assertEqual(handler.get_response_json()["visibility"], "connections_only")

        # POST /discussions/d_vis1/visibility
        handler = DummyAPIHandler("POST", "/discussions/d_vis1/visibility", body={"visibility": "private"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(self.test_db.get_discussion_visibility("d_vis1"), "private")

        # GET /users/u_vis1/discussions (viewer_id=u2 vs viewer_id=u_vis1)
        handler = DummyAPIHandler("GET", "/users/u_vis1/discussions?viewer_id=u_vis2")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 0)  # private to u1

        handler = DummyAPIHandler("GET", "/users/u_vis1/discussions?viewer_id=u_vis1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /discussions/d_vis1/visibility
        handler = DummyAPIHandler("GET", "/discussions/d_vis1/visibility")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["visibility"], "private")

        # GET /users/u_vis1/status
        handler = DummyAPIHandler("GET", "/users/u_vis1/status")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertTrue(handler.get_response_json()["is_active"])

        # PUT /users/u_vis1/visibility
        handler = DummyAPIHandler("PUT", "/users/u_vis1/visibility", body={"visibility": "public"})
        handler.do_PUT()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(self.test_db.get_user_visibility("u_vis1"), "public")

        # Invalid visibility setting -> 400
        handler = DummyAPIHandler("POST", "/users/u_vis1/visibility", body={"visibility": "invalid_setting"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 400)

        # Export JSON test
        json_export = self.test_db.export_user_data_json("u_vis1")
        self.assertIsNotNone(json_export)
        parsed = json.loads(json_export)
        self.assertEqual(parsed["user"]["id"], "u_vis1")

    def test_api_course_management_and_enrollment(self):
        u1 = User(id="u_api_c1", username="prof_api")
        u2 = User(id="u_api_c2", username="student_api")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)

        # POST /courses
        handler = DummyAPIHandler("POST", "/courses", body={
            "id": "c_api1",
            "code": "CS50",
            "name": "Introduction to CS",
            "department": "CS",
            "institution": "Harvard",
            "term": "Fall 2026",
            "created_by": "u_api_c1"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["code"], "CS50")

        # GET /courses
        handler = DummyAPIHandler("GET", "/courses")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /courses/c_api1
        handler = DummyAPIHandler("GET", "/courses/c_api1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["id"], "c_api1")

        # PUT /courses/c_api1
        handler = DummyAPIHandler("PUT", "/courses/c_api1", body={"description": "Updated CS50 syllabus"})
        handler.do_PUT()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["description"], "Updated CS50 syllabus")

        # POST /courses/c_api1/enroll
        handler = DummyAPIHandler("POST", "/courses/c_api1/enroll", body={
            "id": "enr_api1",
            "user_id": "u_api_c2",
            "role": "student",
            "institution": "Harvard",
            "term": "Fall 2026"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /courses/c_api1/enrollments
        handler = DummyAPIHandler("GET", "/courses/c_api1/enrollments")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /users/u_api_c2/courses
        handler = DummyAPIHandler("GET", "/users/u_api_c2/courses")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # POST /courses/c_api1/verify_classmate
        handler = DummyAPIHandler("POST", "/courses/c_api1/verify_classmate", body={
            "user_id": "u_api_c2",
            "verified": True
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertTrue(handler.get_response_json()["verified"])

        # GET /courses/c_api1/classmates?user_id=u_api_c1
        # First enroll u_api_c1 so they are also enrolled
        self.test_db.enroll_in_course(CourseEnrollment(
            id="enr_api_prof", course_id="c_api1", user_id="u_api_c1", institution="Harvard", term="Fall 2026", is_verified=True
        ))
        handler = DummyAPIHandler("GET", "/courses/c_api1/classmates?user_id=u_api_c1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        classmate_list = handler.get_response_json()
        self.assertEqual(len(classmate_list), 1)
        self.assertEqual(classmate_list[0]["id"], "u_api_c2")

        # DELETE /courses/c_api1/enrollments/u_api_c2
        handler = DummyAPIHandler("DELETE", "/courses/c_api1/enrollments/u_api_c2")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

        # DELETE /courses/c_api1
        handler = DummyAPIHandler("DELETE", "/courses/c_api1")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

    def test_api_course_and_study_group_discussions(self):
        u = User(id="u_disc_user", username="disc_user")
        self.test_db.create_user(u)
        c = Course(id="c_disc_course", code="MATH101", name="Calculus I")
        self.test_db.create_course(c)
        sg = StudyGroup(id="sg_disc_team", course_id="c_disc_course", name="Calc Study Buddies", created_by="u_disc_user")
        self.test_db.create_study_group(sg)

        # POST /courses/c_disc_course/discussions
        handler = DummyAPIHandler("POST", "/courses/c_disc_course/discussions", body={
            "id": "d_c_api1",
            "author_id": "u_disc_user",
            "content": "Tips for problem set 1?"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        self.assertEqual(handler.get_response_json()["course_id"], "c_disc_course")

        # GET /courses/c_disc_course/discussions
        handler = DummyAPIHandler("GET", "/courses/c_disc_course/discussions")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # POST /study_groups/sg_disc_team/discussions
        handler = DummyAPIHandler("POST", "/study_groups/sg_disc_team/discussions", body={
            "id": "d_sg_api1",
            "author_id": "u_disc_user",
            "content": "Zoom link for tonight's session"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        self.assertEqual(handler.get_response_json()["study_group_id"], "sg_disc_team")

        # GET /study_groups/sg_disc_team/discussions
        handler = DummyAPIHandler("GET", "/study_groups/sg_disc_team/discussions")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

    def test_api_syllabus_and_resources(self):
        u1 = User(id="u_res_prof", username="res_prof")
        u2 = User(id="u_res_stud", username="res_stud")
        self.test_db.create_user(u1)
        self.test_db.create_user(u2)
        c = Course(id="c_res_c1", code="HIST101", name="Ancient Civilizations")
        self.test_db.create_course(c)

        # POST /courses/c_res_c1/syllabus
        handler = DummyAPIHandler("POST", "/courses/c_res_c1/syllabus", body={
            "id": "res_syl_api",
            "title": "Course Syllabus",
            "author_id": "u_res_prof",
            "url": "https://example.com/hist101.pdf"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        self.assertTrue(handler.get_response_json()["is_official"])

        # GET /courses/c_res_c1/syllabus
        handler = DummyAPIHandler("GET", "/courses/c_res_c1/syllabus")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["id"], "res_syl_api")

        # POST /courses/c_res_c1/resources
        handler = DummyAPIHandler("POST", "/courses/c_res_c1/resources", body={
            "id": "res_notes_api",
            "title": "Roman Empire Timeline",
            "author_id": "u_res_stud",
            "resource_type": "study_guide"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /courses/c_res_c1/resources
        handler = DummyAPIHandler("GET", "/courses/c_res_c1/resources")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 2)

        # GET /resources/res_notes_api
        handler = DummyAPIHandler("GET", "/resources/res_notes_api")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["title"], "Roman Empire Timeline")

        # POST /resources/res_notes_api/endorse
        handler = DummyAPIHandler("POST", "/resources/res_notes_api/endorse", body={"user_id": "u_res_prof"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["endorsements_count"], 1)

        # DELETE /resources/res_notes_api
        handler = DummyAPIHandler("DELETE", "/resources/res_notes_api")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

    def test_api_study_groups_and_search(self):
        u_lead = User(id="u_sg_lead", username="sg_lead")
        u_member = User(id="u_sg_member", username="sg_member")
        u_stranger = User(id="u_sg_stranger", username="sg_stranger")
        for u in [u_lead, u_member, u_stranger]:
            self.test_db.create_user(u)

        c = Course(id="c_sg_course", code="PHYS300", name="Quantum Mechanics", institution="Caltech", term="Fall 2026")
        self.test_db.create_course(c)

        self.test_db.enroll_in_course(CourseEnrollment(
            id="enr_l2", course_id="c_sg_course", user_id="u_sg_lead", institution="Caltech", term="Fall 2026", is_verified=True
        ))
        self.test_db.enroll_in_course(CourseEnrollment(
            id="enr_m2", course_id="c_sg_course", user_id="u_sg_member", institution="Caltech", term="Fall 2026", is_verified=True
        ))

        # POST /study_groups (verified_only=True)
        handler = DummyAPIHandler("POST", "/study_groups", body={
            "id": "sg_quantum",
            "course_id": "c_sg_course",
            "name": "Quantum Wavefunctions Team",
            "created_by": "u_sg_lead",
            "verified_only": True,
            "max_members": 2
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /study_groups
        handler = DummyAPIHandler("GET", "/study_groups")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # POST /study_groups/sg_quantum/join by stranger -> 403 Forbidden
        handler = DummyAPIHandler("POST", "/study_groups/sg_quantum/join", body={"user_id": "u_sg_stranger"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 403)

        # POST /study_groups/sg_quantum/join by member -> 200 OK
        handler = DummyAPIHandler("POST", "/study_groups/sg_quantum/join", body={"user_id": "u_sg_member"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # GET /study_groups/sg_quantum/members
        handler = DummyAPIHandler("GET", "/study_groups/sg_quantum/members")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 2)

        # GET /users/u_sg_member/study_groups
        handler = DummyAPIHandler("GET", "/users/u_sg_member/study_groups")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # POST /study_groups/sg_quantum/leave
        handler = DummyAPIHandler("POST", "/study_groups/sg_quantum/leave", body={"user_id": "u_sg_member"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # GET /search/courses
        handler = DummyAPIHandler("GET", "/search/courses?q=Quantum")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /search/study_groups
        handler = DummyAPIHandler("GET", "/search/study_groups?q=Wavefunctions")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # GET /search?type=courses
        handler = DummyAPIHandler("GET", "/search?q=Quantum&type=courses")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()["courses"]), 1)

        # GET /search?type=study_groups
        handler = DummyAPIHandler("GET", "/search?q=Wavefunctions&type=study_groups")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()["study_groups"]), 1)

    def test_api_media_accessibility_endpoints(self):
        u = User(id="u_api_med", username="media_creator")
        self.test_db.create_user(u)

        # 1. POST /media
        handler = DummyAPIHandler("POST", "/media", body={
            "id": "med_api1",
            "url": "https://example.com/assets/arch.png",
            "media_type": "image",
            "alt_text": "System architecture diagram with load balancer and replicas",
            "uploader_id": "u_api_med",
            "content_warnings": ["technical_diagram"],
            "is_sensitive": False
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["id"], "med_api1")
        self.assertEqual(res["alt_text"], "System architecture diagram with load balancer and replicas")

        # 2. GET /media/med_api1
        handler = DummyAPIHandler("GET", "/media/med_api1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["media_type"], "image")

        # 3. POST /media/med_api1/accessibility (update metadata)
        handler = DummyAPIHandler("POST", "/media/med_api1/accessibility", body={
            "alt_text": "Updated architecture flow diagram",
            "description": "Load balancer high availability diagram"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["alt_text"], "Updated architecture flow diagram")

        # 4. GET /users/u_api_med/media
        handler = DummyAPIHandler("GET", "/users/u_api_med/media")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)

        # 5. POST /discussions
        handler = DummyAPIHandler("POST", "/discussions", body={
            "id": "d_api_disc1",
            "author_id": "u_api_med",
            "content": "Here is the architectural overview",
            "alt_text": "Overview diagram",
            "content_warnings": ["architecture"]
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # 6. POST /discussions/d_api_disc1/media (attach media)
        handler = DummyAPIHandler("POST", "/discussions/d_api_disc1/media", body={
            "media_ids": ["med_api1"]
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # 7. GET /discussions/d_api_disc1/media
        handler = DummyAPIHandler("GET", "/discussions/d_api_disc1/media")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(len(handler.get_response_json()), 1)
        self.assertEqual(handler.get_response_json()[0]["id"], "med_api1")

        # 8. DELETE /media/med_api1
        handler = DummyAPIHandler("DELETE", "/media/med_api1")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

        # 9. GET /media/med_api1 -> 404
        handler = DummyAPIHandler("GET", "/media/med_api1")
        handler.do_GET()
        self.assertEqual(handler._response_status, 404)

    def test_api_content_filtering_preferences_endpoints(self):
        u = User(id="u_api_filter", username="filter_user")
        self.test_db.create_user(u)

        # 1. GET /users/u_api_filter/content_filtering (defaults)
        handler = DummyAPIHandler("GET", "/users/u_api_filter/content_filtering")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["mute_keywords"], [])

        # 2. POST /users/u_api_filter/content_filtering
        handler = DummyAPIHandler("POST", "/users/u_api_filter/content_filtering", body={
            "mute_keywords": ["spoilers", "crypto"],
            "content_warning_tags": ["violence", "nsfw"],
            "hide_sensitive_media": True,
            "filter_level": "hide"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["mute_keywords"], ["spoilers", "crypto"])
        self.assertEqual(res["content_warning_tags"], ["violence", "nsfw"])
        self.assertTrue(res["hide_sensitive_media"])

        # 3. POST /users/u_api_filter/mute_keywords
        handler = DummyAPIHandler("POST", "/users/u_api_filter/mute_keywords", body={"keyword": "phishing"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # 4. GET /users/u_api_filter/mute_keywords
        handler = DummyAPIHandler("GET", "/users/u_api_filter/mute_keywords")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        kws = handler.get_response_json()["mute_keywords"]
        self.assertIn("phishing", kws)
        self.assertEqual(len(kws), 3)

        # 5. POST /users/u_api_filter/content_warnings
        handler = DummyAPIHandler("POST", "/users/u_api_filter/content_warnings", body={"tag": "flashing_lights"})
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # 6. GET /users/u_api_filter/content_warnings
        handler = DummyAPIHandler("GET", "/users/u_api_filter/content_warnings")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        cws = handler.get_response_json()["content_warning_tags"]
        self.assertIn("flashing_lights", cws)

        # 7. PUT /users/u_api_filter/content_filtering
        handler = DummyAPIHandler("PUT", "/users/u_api_filter/content_filtering", body={"filter_level": "blur"})
        handler.do_PUT()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["filter_level"], "blur")

        # 8. DELETE /users/u_api_filter/mute_keywords/crypto
        handler = DummyAPIHandler("DELETE", "/users/u_api_filter/mute_keywords/crypto")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

        # 9. DELETE /users/u_api_filter/content_warnings/violence
        handler = DummyAPIHandler("DELETE", "/users/u_api_filter/content_warnings/violence")
        handler.do_DELETE()
        self.assertEqual(handler._response_status, 200)

        # 10. GET /content_filtering/u_api_filter
        handler = DummyAPIHandler("GET", "/content_filtering/u_api_filter")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res_final = handler.get_response_json()
        self.assertNotIn("crypto", res_final["mute_keywords"])
        self.assertNotIn("violence", res_final["content_warning_tags"])
        self.assertIn("spoilers", res_final["mute_keywords"])
        self.assertIn("nsfw", res_final["content_warning_tags"])

    def test_api_accessibility_settings_endpoints(self):
        u = User(id="u_api_acc", username="access_tester")
        self.test_db.create_user(u)

        # 1. GET /users/u_api_acc/accessibility (defaults)
        handler = DummyAPIHandler("GET", "/users/u_api_acc/accessibility")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertFalse(handler.get_response_json()["high_contrast"])

        # 2. POST /accessibility
        handler = DummyAPIHandler("POST", "/accessibility", body={
            "user_id": "u_api_acc",
            "high_contrast": True,
            "reduce_motion": True,
            "font_size": "large",
            "closed_captions_enabled": True
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertTrue(res["high_contrast"])
        self.assertTrue(res["reduce_motion"])
        self.assertEqual(res["font_size"], "large")
        self.assertTrue(res["closed_captions_enabled"])

        # 3. PUT /accessibility/u_api_acc
        handler = DummyAPIHandler("PUT", "/accessibility/u_api_acc", body={
            "screen_reader_optimized": True,
            "dyslexia_font": True,
            "color_blind_mode": "protanopia"
        })
        handler.do_PUT()
        self.assertEqual(handler._response_status, 200)
        res2 = handler.get_response_json()
        self.assertTrue(res2["screen_reader_optimized"])
        self.assertTrue(res2["dyslexia_font"])
        self.assertEqual(res2["color_blind_mode"], "protanopia")
        self.assertTrue(res2["high_contrast"])

        # 4. GET /accessibility/u_api_acc
        handler = DummyAPIHandler("GET", "/accessibility/u_api_acc")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["color_blind_mode"], "protanopia")

    def test_api_discussions_with_accessibility_and_content_filtering(self):
        u1 = User(id="u_api_author", username="author_test")
        self.test_db.create_user(u1)

        # POST /discussions with alt_text and content warnings
        handler = DummyAPIHandler("POST", "/discussions", body={
            "id": "d_astronomy",
            "author_id": "u_api_author",
            "content": "Deep space discoveries #astronomy",
            "alt_text": "High resolution James Webb nebula photograph",
            "audio_transcript": "Transcript of the researcher explaining the nebula composition.",
            "content_warnings": ["spoilers", "space_science"],
            "media": [
                {
                    "id": "med_jwst1",
                    "url": "https://example.com/jwst.jpg",
                    "media_type": "image",
                    "alt_text": "JWST Nebula view"
                }
            ]
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["alt_text"], "High resolution James Webb nebula photograph")
        self.assertEqual(res["content_warnings"], ["spoilers", "space_science"])
        self.assertTrue(res["has_content_warning"])

        # GET /discussions/d_astronomy
        handler = DummyAPIHandler("GET", "/discussions/d_astronomy")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        fetched = handler.get_response_json()
        self.assertEqual(fetched["alt_text"], "High resolution James Webb nebula photograph")
        self.assertEqual(fetched["audio_transcript"], "Transcript of the researcher explaining the nebula composition.")
        self.assertEqual(fetched["content_warnings"], ["spoilers", "space_science"])

        # POST /discussions/d_astronomy/replies with accessibility fields
        handler = DummyAPIHandler("POST", "/discussions/d_astronomy/replies", body={
            "id": "d_astronomy_reply",
            "author_id": "u_api_author",
            "content": "Reply with audio explanation",
            "alt_text": "Spectrometry chart",
            "audio_transcript": "Explanation of the spectral lines"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res_rep = handler.get_response_json()
        self.assertEqual(res_rep["alt_text"], "Spectrometry chart")
        self.assertEqual(res_rep["audio_transcript"], "Explanation of the spectral lines")

        # GET /users/u_api_author/export
        handler = DummyAPIHandler("GET", "/users/u_api_author/export")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        export = handler.get_response_json()
        self.assertIn("accessibility_settings", export)
        self.assertIn("content_filter_preferences", export)
        self.assertIn("media_attachments", export)
        self.assertEqual(len(export["media_attachments"]), 1)


class TestPrivacyCoherence(unittest.TestCase):
    def setUp(self):
        self.db = SocialDatabase(":memory:")
        self._orig_db = api_server.db
        api_server.db = self.db
        self.u1 = User(id="u_alice", username="alice", is_active=True, is_publicly_discoverable=True)
        self.u2 = User(id="u_bob", username="bob", is_active=True, is_publicly_discoverable=True)
        self.u3 = User(id="u_charlie", username="charlie", is_active=True, is_publicly_discoverable=False)
        self.u4 = User(id="u_dave", username="dave", is_active=False, is_publicly_discoverable=True)  # deactivated
        for u in [self.u1, self.u2, self.u3, self.u4]:
            self.db.create_user(u)

    def tearDown(self):
        if hasattr(self, "_orig_db"):
            api_server.db = self._orig_db

    def test_privacy_settings_dataclass_and_aliases(self):
        ps = PrivacySettings(user_id="u_alice")
        self.assertEqual(ps.visibility, "public")
        self.assertEqual(ps.dm_privacy, "everyone")
        self.assertFalse(ps.is_publicly_discoverable)
        self.assertTrue(ps.is_active)
        self.assertTrue(ps.is_public)
        self.assertFalse(ps.is_private)
        self.assertFalse(ps.is_connections_only)
        self.assertFalse(ps.is_deactivated)
        self.assertEqual(ps.profile_visibility, "public")
        self.assertEqual(ps.allow_dms_from, "everyone")
        self.assertEqual(ps.direct_message_privacy, "everyone")

        ps_norm = PrivacySettings(user_id="u_bob", visibility="connections-only", dm_privacy="disabled", is_active=False)
        self.assertEqual(ps_norm.visibility, "connections_only")
        self.assertEqual(ps_norm.dm_privacy, "nobody")
        self.assertTrue(ps_norm.is_connections_only)
        self.assertTrue(ps_norm.is_deactivated)

        d = ps_norm.to_dict()
        self.assertEqual(d["user_id"], "u_bob")
        self.assertEqual(d["visibility"], "connections_only")
        self.assertEqual(d["dm_privacy"], "nobody")
        self.assertFalse(d["is_active"])
        self.assertTrue(d["is_deactivated"])

        user = self.db.get_user("u_alice")
        self.assertIsNotNone(user.privacy_settings)
        self.assertEqual(user.privacy_settings.user_id, "u_alice")

    def test_user_privacy_settings_crud_and_validation(self):
        # 1. Get default privacy settings
        ps = self.db.get_privacy_settings("u_alice")
        self.assertIsNotNone(ps)
        self.assertEqual(ps.visibility, "public")
        self.assertEqual(ps.dm_privacy, "everyone")

        # 2. Update privacy settings
        ok = self.db.set_privacy_settings("u_alice", visibility="connections_only", dm_privacy="connections_only", is_publicly_discoverable=False)
        self.assertTrue(ok)
        ps_updated = self.db.get_privacy_settings("u_alice")
        self.assertEqual(ps_updated.visibility, "connections_only")
        self.assertEqual(ps_updated.dm_privacy, "connections_only")
        self.assertFalse(ps_updated.is_publicly_discoverable)

        # 3. Update dm_privacy directly
        ok = self.db.set_dm_privacy("u_alice", "nobody")
        self.assertTrue(ok)
        self.assertEqual(self.db.get_dm_privacy("u_alice"), "nobody")

        # 4. Update discoverability directly
        ok = self.db.set_user_discoverability("u_alice", True)
        self.assertTrue(ok)
        self.assertTrue(self.db.get_user_discoverability("u_alice"))

        # 5. Invalid visibility raises ValueError
        with self.assertRaises(ValueError):
            self.db.set_privacy_settings("u_alice", visibility="invalid_scope")

        # 6. Invalid dm_privacy raises ValueError
        with self.assertRaises(ValueError):
            self.db.set_dm_privacy("u_alice", "invalid_mode")

        # 7. Non-existent user
        self.assertIsNone(self.db.get_privacy_settings("non_existent"))
        self.assertFalse(self.db.set_privacy_settings("non_existent", visibility="public"))

    def test_direct_messaging_privacy_enforcement(self):
        # Initial: everyone can message
        self.assertTrue(self.db.can_send_direct_message("u_alice", "u_bob"))
        msg = self.db.create_direct_message("u_alice", "u_bob", "Hello Bob")
        self.assertIsNotNone(msg)

        # Alice sets dm_privacy to connections_only
        self.db.set_dm_privacy("u_alice", "connections_only")
        # Bob is not connected to Alice -> Bob cannot message Alice
        self.assertFalse(self.db.can_send_direct_message("u_bob", "u_alice"))
        with self.assertRaises(PermissionError):
            self.db.create_direct_message("u_bob", "u_alice", "Hey Alice")

        # Now Alice and Bob connect
        self.db.create_connection("u_alice", "u_bob")
        self.assertTrue(self.db.can_send_direct_message("u_bob", "u_alice"))
        msg2 = self.db.create_direct_message("u_bob", "u_alice", "Hey Alice connected")
        self.assertIsNotNone(msg2)

        # Charlie (not connected) cannot message Alice
        self.assertFalse(self.db.can_send_direct_message("u_charlie", "u_alice"))
        with self.assertRaises(PermissionError):
            self.db.create_direct_message("u_charlie", "u_alice", "Hey Alice from Charlie")

        # Alice sets dm_privacy to nobody
        self.db.set_dm_privacy("u_alice", "nobody")
        self.assertFalse(self.db.can_send_direct_message("u_bob", "u_alice"))
        with self.assertRaises(PermissionError):
            self.db.create_direct_message("u_bob", "u_alice", "Can you hear me?")

        # Blocked user enforcement: Bob sets dm_privacy back to everyone, but blocks Alice
        self.db.set_dm_privacy("u_bob", "everyone")
        self.assertTrue(self.db.can_send_direct_message("u_alice", "u_bob"))
        self.db.block_user("u_bob", "u_alice")
        self.assertFalse(self.db.can_send_direct_message("u_alice", "u_bob"))
        with self.assertRaises(PermissionError):
            self.db.create_direct_message("u_alice", "u_bob", "Why block me?")

        # Inactive / Deactivated user cannot send or receive DMs
        self.assertFalse(self.db.can_send_direct_message("u_alice", "u_dave"))
        self.assertFalse(self.db.can_send_direct_message("u_dave", "u_alice"))
        with self.assertRaises(PermissionError):
            self.db.create_direct_message("u_alice", "u_dave", "Hello inactive")

    def test_profile_visibility_coherence(self):
        # 1. Public profile: everyone can view
        self.assertTrue(self.db.can_user_view_profile("u_bob", "u_alice"))
        self.assertTrue(self.db.can_user_view_profile(None, "u_alice"))

        # 2. Connections only profile
        self.db.set_privacy_settings("u_alice", visibility="connections_only")
        self.assertTrue(self.db.can_user_view_profile("u_alice", "u_alice"))  # Self can view
        self.assertFalse(self.db.can_user_view_profile("u_bob", "u_alice"))  # Bob not connected
        self.assertFalse(self.db.can_user_view_profile(None, "u_alice"))

        self.db.create_connection("u_alice", "u_bob")
        self.assertTrue(self.db.can_user_view_profile("u_bob", "u_alice"))  # Bob now connected
        self.assertFalse(self.db.can_user_view_profile("u_charlie", "u_alice"))  # Charlie not connected

        # 3. Private profile
        self.db.set_privacy_settings("u_alice", visibility="private")
        self.assertTrue(self.db.can_user_view_profile("u_alice", "u_alice"))
        self.assertFalse(self.db.can_user_view_profile("u_bob", "u_alice"))
        self.assertFalse(self.db.can_user_view_profile("u_charlie", "u_alice"))

        # 4. Blocking hides profile
        self.db.set_privacy_settings("u_alice", visibility="public")
        self.db.block_user("u_alice", "u_bob")
        self.assertFalse(self.db.can_user_view_profile("u_bob", "u_alice"))
        self.assertFalse(self.db.can_user_view_profile("u_alice", "u_bob"))

        # 5. Deactivated user profile hidden
        self.assertFalse(self.db.can_user_view_profile("u_alice", "u_dave"))

    def test_community_and_discussion_privacy_coherence(self):
        # 1. Public community & discussion
        comm_pub = Community(id="c_pub", name="Public Comm", is_private=False)
        self.db.create_community(comm_pub)
        self.assertTrue(self.db.can_user_view_community("u_alice", "c_pub"))
        self.assertTrue(self.db.can_user_view_community(None, "c_pub"))

        disc_pub = Discussion(id="d_pub", author_id="u_alice", community_id="c_pub", content="Public announcement")
        self.db.create_discussion(disc_pub)
        self.assertTrue(self.db.can_user_view_discussion("u_bob", "d_pub"))

        # 2. Private community & discussion
        comm_priv = Community(id="c_priv", name="Private Comm", is_private=True)
        self.db.create_community(comm_priv)
        self.db.add_community_member(CommunityMember(community_id="c_priv", user_id="u_alice", role="admin"))

        # Member (Alice) can view community, non-member (Bob) cannot
        self.assertTrue(self.db.can_user_view_community("u_alice", "c_priv"))
        self.assertFalse(self.db.can_user_view_community("u_bob", "c_priv"))
        self.assertFalse(self.db.can_user_view_community(None, "c_priv"))

        # Alice creates discussion in private community
        disc_priv = Discussion(id="d_priv", author_id="u_alice", community_id="c_priv", content="Secret meeting")
        self.db.create_discussion(disc_priv)

        # Alice can view discussion, Bob cannot
        self.assertTrue(self.db.can_user_view_discussion("u_alice", "d_priv"))
        self.assertFalse(self.db.can_user_view_discussion("u_bob", "d_priv"))
        self.assertFalse(self.db.can_user_view_discussion(None, "d_priv"))

        # Bob (non-member) cannot post in private community
        disc_bob = Discussion(id="d_bob_priv", author_id="u_bob", community_id="c_priv", content="Intruder post")
        with self.assertRaises(PermissionError):
            self.db.create_discussion(disc_bob)

        # Bob joins private community -> now can view and post
        self.db.add_community_member(CommunityMember(community_id="c_priv", user_id="u_bob", role="member"))
        self.assertTrue(self.db.can_user_view_community("u_bob", "c_priv"))
        self.assertTrue(self.db.can_user_view_discussion("u_bob", "d_priv"))
        disc_bob_ok = self.db.create_discussion(disc_bob)
        self.assertIsNotNone(disc_bob_ok)

        # 3. Banned member cannot view private community
        self.db.ban_user_from_community("c_priv", "u_bob", "u_alice", "Violated rules")
        self.assertFalse(self.db.can_user_view_community("u_bob", "c_priv"))
        self.assertFalse(self.db.can_user_view_discussion("u_bob", "d_priv"))

        # 4. Hidden discussion is not viewable by other users
        disc_hidden = Discussion(id="d_hid", author_id="u_alice", content="Flagged content", is_hidden=True)
        self.db.create_discussion(disc_hidden)
        self.assertFalse(self.db.can_user_view_discussion("u_bob", "d_hid"))
        self.assertTrue(self.db.can_user_view_discussion("u_alice", "d_hid"))

    def test_search_privacy_coherence(self):
        # Charlie is not publicly discoverable
        self.assertFalse(self.db.get_user("u_charlie").is_publicly_discoverable)

        # Stranger (Alice) searching users should not see Charlie
        results = self.db.search_users("charlie", viewer_id="u_alice")
        self.assertEqual(len(results), 0)

        # Charlie opts into public discoverability
        self.db.set_user_discoverability("u_charlie", True)
        results = self.db.search_users("charlie", viewer_id="u_alice")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "u_charlie")

        # But if Charlie sets profile visibility to private, search hides Charlie from others
        self.db.set_privacy_settings("u_charlie", visibility="private")
        results = self.db.search_users("charlie", viewer_id="u_alice")
        self.assertEqual(len(results), 0)

        # If Charlie searches himself, he appears
        results_self = self.db.search_users("charlie", viewer_id="u_charlie")
        self.assertEqual(len(results_self), 1)

        # Discussions in private communities excluded in search for non-members
        comm_sec = Community(id="c_sec", name="Secret Club", is_private=True)
        self.db.create_community(comm_sec)
        self.db.add_community_member(CommunityMember(community_id="c_sec", user_id="u_alice", role="admin"))
        self.db.create_discussion(Discussion(id="d_sec1", author_id="u_alice", community_id="c_sec", content="Secret quantum computing notes"))

        # Non-member (Bob) search
        disc_results_bob = self.db.search_discussions("quantum", viewer_id="u_bob")
        self.assertEqual(len(disc_results_bob), 0)

        # Member (Alice) search
        disc_results_alice = self.db.search_discussions("quantum", viewer_id="u_alice")
        self.assertEqual(len(disc_results_alice), 1)

        # Multi-entity search passes viewer_id
        search_res_bob = self.db.search("quantum", viewer_id="u_bob")
        self.assertEqual(len(search_res_bob["discussions"]), 0)

        search_res_alice = self.db.search("quantum", viewer_id="u_alice")
        self.assertEqual(len(search_res_alice["discussions"]), 1)

    def test_feed_privacy_coherence(self):
        comm_priv = Community(id="c_feed_priv", name="Feed Priv", is_private=True)
        self.db.create_community(comm_priv)
        self.db.add_community_member(CommunityMember(community_id="c_feed_priv", user_id="u_alice", role="admin"))

        # Alice posts 1 public discussion and 1 private community discussion
        self.db.create_discussion(Discussion(id="d_alice_pub", author_id="u_alice", content="Alice public post"))
        self.db.create_discussion(Discussion(id="d_alice_priv", author_id="u_alice", community_id="c_feed_priv", content="Alice secret post"))

        # Alice and Bob are connected
        self.db.create_connection("u_alice", "u_bob")

        feed_service = FeedService(self.db)
        bob_feed = feed_service.get_feed("u_bob", mode=FeedMode.CHRONOLOGICAL)
        bob_post_ids = [d.id for d in bob_feed]

        # Bob should see the public post, but NOT the private community post
        self.assertIn("d_alice_pub", bob_post_ids)
        self.assertNotIn("d_alice_priv", bob_post_ids)

        # Alice feed should see both
        alice_feed = feed_service.get_feed("u_alice", mode=FeedMode.CHRONOLOGICAL)
        alice_post_ids = [d.id for d in alice_feed]
        self.assertIn("d_alice_pub", alice_post_ids)
        self.assertIn("d_alice_priv", alice_post_ids)

    def test_api_privacy_endpoints(self):
        # 1. GET /users/<id>/privacy
        handler = DummyAPIHandler("GET", "/users/u_alice/privacy")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["user_id"], "u_alice")
        self.assertEqual(res["visibility"], "public")
        self.assertEqual(res["dm_privacy"], "everyone")

        # 2. PUT /users/<id>/privacy
        handler = DummyAPIHandler("PUT", "/users/u_alice/privacy", body={
            "visibility": "connections_only",
            "dm_privacy": "connections_only",
            "is_publicly_discoverable": False
        })
        handler.do_PUT()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertEqual(res["visibility"], "connections_only")
        self.assertEqual(res["dm_privacy"], "connections_only")
        self.assertFalse(res["is_publicly_discoverable"])

        # 3. GET /users/<id>/visibility & PUT /users/<id>/visibility
        handler = DummyAPIHandler("GET", "/users/u_alice/visibility")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["visibility"], "connections_only")

        handler = DummyAPIHandler("PUT", "/users/u_alice/visibility", body={"visibility": "private"})
        handler.do_PUT()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["visibility"], "private")

        # 4. GET /users/<id>/dm_privacy & PUT /users/<id>/dm_privacy
        handler = DummyAPIHandler("GET", "/users/u_alice/dm_privacy")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["dm_privacy"], "connections_only")

        handler = DummyAPIHandler("PUT", "/users/u_alice/dm_privacy", body={"dm_privacy": "nobody"})
        handler.do_PUT()
        self.assertEqual(handler._response_status, 200)
        self.assertEqual(handler.get_response_json()["dm_privacy"], "nobody")

        # 5. GET /users/<sender_id>/can_message/<receiver_id>
        handler = DummyAPIHandler("GET", "/users/u_bob/can_message/u_alice")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertFalse(res["can_message"])

        # 6. GET /users/<viewer_id>/can_view/<target_id>
        handler = DummyAPIHandler("GET", "/users/u_bob/can_view/u_alice")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        res = handler.get_response_json()
        self.assertFalse(res["can_view"])  # alice is private

        # 7. POST /messages blocked with 403 when DM privacy prevents it
        handler = DummyAPIHandler("POST", "/messages", body={
            "sender_id": "u_bob",
            "recipient_id": "u_alice",
            "content": "Secret note"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 403)


    def test_content_lifecycle_full_workflow(self):
        # Setup users
        u_author = User(id="u_author", username="author_alice")
        u_user = User(id="u_user", username="reader_bob")
        u_mod = User(id="u_mod", username="moderator_charlie")
        for u in [u_author, u_user, u_mod]:
            self.db.create_user(u)

        # 1. CREATE
        disc = Discussion(id="d_life1", author_id="u_author", content="Interesting new article #research")
        self.db.create_discussion(disc)

        created_disc = self.db.get_discussion("d_life1")
        self.assertIsNotNone(created_disc)
        self.assertEqual(created_disc.status, ContentLifecycleState.ACTIVE)
        self.assertEqual(created_disc.lifecycle_state, "active")
        self.assertTrue(created_disc.is_active)
        self.assertFalse(created_disc.is_removed)
        self.assertFalse(created_disc.is_moderated)
        self.assertFalse(created_disc.is_appealed)
        self.assertEqual(created_disc.report_count, 0)
        self.assertEqual(created_disc.interaction_count, 0)

        # Check create event recorded
        events = self.db.get_discussion_events("d_life1")
        self.assertTrue(len(events) >= 1)
        self.assertEqual(events[0].event_type, ContentLifecycleAction.CREATE)
        self.assertEqual(events[0].actor_id, "u_author")

        # 2. INTERACT
        self.assertTrue(self.db.can_interact_with_discussion("d_life1", "u_user", "endorse"))
        interaction = self.db.interact_with_discussion("d_life1", actor_id="u_user", action="endorse", metadata={"client": "web"})
        self.assertIsNotNone(interaction)
        self.assertEqual(interaction.user_id, "u_user")
        self.assertEqual(interaction.interaction_type, "endorse")

        # Check discussion updated
        updated_disc = self.db.get_discussion("d_life1")
        self.assertEqual(updated_disc.value_endorsements, 1)
        self.assertEqual(updated_disc.interaction_count, 1)
        self.assertIsNotNone(updated_disc.last_interacted_at)

        interactions = self.db.get_discussion_interactions("d_life1")
        self.assertEqual(len(interactions), 1)

        # 3. REPORT
        rep = self.db.report_discussion(
            discussion_id="d_life1",
            reporter_id="u_user",
            reason="Suspected spam link",
            category="spam",
            details="Link points to unverified domain"
        )
        self.assertIsNotNone(rep)
        self.assertEqual(rep.target_id, "d_life1")
        self.assertEqual(rep.status, "pending")

        reported_disc = self.db.get_discussion("d_life1")
        self.assertEqual(reported_disc.report_count, 1)
        self.assertEqual(reported_disc.moderation_status, "reported")

        reports = self.db.get_discussion_reports("d_life1")
        self.assertEqual(len(reports), 1)

        # 4. MODERATE (Hide/Quarantine)
        mod_success = self.db.moderate_discussion(
            discussion_id="d_life1",
            action="hide",
            moderator_id="u_mod",
            reason="Violation of safety policy",
            notes="Temporary hidden pending review"
        )
        self.assertTrue(mod_success)

        mod_disc = self.db.get_discussion("d_life1")
        self.assertTrue(mod_disc.is_hidden)
        self.assertEqual(mod_disc.status, "hidden")
        self.assertTrue(mod_disc.is_moderated)
        self.assertFalse(mod_disc.is_active)
        self.assertEqual(mod_disc.moderated_by, "u_mod")

        # 5. APPEAL
        appeal = self.db.appeal_discussion(
            discussion_id="d_life1",
            appellant_id="u_author",
            reason="The domain is my verified university research page",
            notes="Please re-examine"
        )
        self.assertIsNotNone(appeal)
        self.assertEqual(appeal.status, "pending")
        self.assertEqual(appeal.target_id, "d_life1")

        appealed_disc = self.db.get_discussion("d_life1")
        self.assertEqual(appealed_disc.status, "appealed")
        self.assertTrue(appealed_disc.is_appealed)
        self.assertTrue(appealed_disc.is_under_appeal)

        appeals = self.db.get_discussion_appeals("d_life1")
        self.assertEqual(len(appeals), 1)

        # 6. REVIEW APPEAL (Approve -> Restored)
        review_success = self.db.review_content_appeal(
            appeal_id=appeal.id,
            status="approved",
            reviewed_by="u_mod",
            notes="Domain verified as legitimate research project"
        )
        self.assertTrue(review_success)

        restored_disc = self.db.get_discussion("d_life1")
        self.assertFalse(restored_disc.is_hidden)
        self.assertEqual(restored_disc.status, "active")
        self.assertTrue(restored_disc.is_active)

        # 7. REMOVE & RESTORE
        # Remove (soft delete)
        rem_success = self.db.remove_discussion("d_life1", actor_id="u_author", reason="Author decided to withdraw")
        self.assertTrue(rem_success)

        removed_disc = self.db.get_discussion("d_life1")
        self.assertTrue(removed_disc.is_hidden)
        self.assertTrue(removed_disc.is_removed)
        self.assertFalse(removed_disc.is_active)
        self.assertIsNotNone(removed_disc.deleted_at)

        # Interaction on removed discussion fails
        self.assertFalse(self.db.can_interact_with_discussion("d_life1", "u_user"))
        with self.assertRaises(ValueError):
            self.db.interact_with_discussion("d_life1", actor_id="u_user", action="endorse")

        # Restore
        res_success = self.db.restore_discussion("d_life1", actor_id="u_mod", reason="Restored after discussion")
        self.assertTrue(res_success)

        final_disc = self.db.get_discussion("d_life1")
        self.assertFalse(final_disc.is_hidden)
        self.assertTrue(final_disc.is_active)
        self.assertFalse(final_disc.is_removed)

        # 8. AUDIT TRAIL & LIFECYCLE SNAPSHOT
        lifecycle = self.db.get_discussion_lifecycle("d_life1")
        self.assertIsNotNone(lifecycle)
        self.assertEqual(lifecycle["id"], "d_life1")
        self.assertEqual(lifecycle["author_id"], "u_author")
        self.assertEqual(lifecycle["status"], "active")
        self.assertTrue(lifecycle["is_active"])
        self.assertFalse(lifecycle["is_removed"])
        self.assertEqual(lifecycle["reports_count"], 1)
        self.assertEqual(lifecycle["appeals_count"], 1)
        self.assertTrue(len(lifecycle["events"]) >= 5)
        self.assertTrue(len(lifecycle["interactions"]) >= 1)

        # Verify event history sequence
        event_types = [e["event_type"] for e in lifecycle["events"]]
        self.assertIn("create", event_types)
        self.assertIn("interact", event_types)
        self.assertIn("report", event_types)
        self.assertIn("moderate", event_types)
        self.assertIn("appeal", event_types)
        self.assertIn("appeal_approved", event_types)
        self.assertIn("remove", event_types)
        self.assertIn("restore", event_types)


class TestContentLifecycleAPI(unittest.TestCase):
    def setUp(self):
        self.test_db = SocialDatabase(":memory:")
        api_server.db = self.test_db

        # Seed test users
        u1 = User(id="u_alice", username="alice")
        u2 = User(id="u_bob", username="bob")
        u3 = User(id="u_mod", username="charlie_mod")
        for u in [u1, u2, u3]:
            self.test_db.create_user(u)

    def test_api_content_lifecycle_endpoints(self):
        # 1. Create discussion via POST /discussions
        handler = DummyAPIHandler("POST", "/discussions", body={
            "id": "d_api_life",
            "author_id": "u_alice",
            "content": "Lifecycle testing post",
            "tags": ["testing", "lifecycle"]
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        res = handler.get_response_json()
        self.assertEqual(res["id"], "d_api_life")
        self.assertEqual(res["status"], "active")

        # 2. Interact via POST /discussions/<id>/interact
        handler = DummyAPIHandler("POST", "/discussions/d_api_life/interact", body={
            "user_id": "u_bob",
            "interaction_type": "endorse",
            "metadata": {"source": "mobile"}
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)

        # GET /discussions/<id>/interactions
        handler = DummyAPIHandler("GET", "/discussions/d_api_life/interactions")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        interactions = handler.get_response_json()
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]["user_id"], "u_bob")

        # 3. Report via POST /discussions/<id>/report
        handler = DummyAPIHandler("POST", "/discussions/d_api_life/report", body={
            "id": "rep_api_1",
            "reporter_id": "u_bob",
            "reason": "Suspected spam",
            "category": "spam",
            "details": "Automated post"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        rep = handler.get_response_json()
        self.assertEqual(rep["id"], "rep_api_1")

        # GET /discussions/<id>/reports
        handler = DummyAPIHandler("GET", "/discussions/d_api_life/reports")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        reports = handler.get_response_json()
        self.assertEqual(len(reports), 1)

        # 4. Moderate via POST /discussions/<id>/moderate
        handler = DummyAPIHandler("POST", "/discussions/d_api_life/moderate", body={
            "action": "hide",
            "moderator_id": "u_mod",
            "reason": "Report verified"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Check status via GET /discussions/<id>/status
        handler = DummyAPIHandler("GET", "/discussions/d_api_life/status")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        status_res = handler.get_response_json()
        self.assertEqual(status_res["status"], "hidden")
        self.assertTrue(status_res["is_moderated"])
        self.assertFalse(status_res["is_active"])

        # 5. Appeal via POST /discussions/<id>/appeal
        handler = DummyAPIHandler("POST", "/discussions/d_api_life/appeal", body={
            "id": "app_api_1",
            "appellant_id": "u_alice",
            "reason": "Not spam, genuine post",
            "report_id": "rep_api_1"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 201)
        appeal_res = handler.get_response_json()
        self.assertEqual(appeal_res["id"], "app_api_1")
        self.assertEqual(appeal_res["status"], "pending")

        # GET /discussions/<id>/appeals
        handler = DummyAPIHandler("GET", "/discussions/d_api_life/appeals")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        appeals = handler.get_response_json()
        self.assertEqual(len(appeals), 1)

        # 6. Review appeal via POST /appeals/<id>/review
        handler = DummyAPIHandler("POST", "/appeals/app_api_1/review", body={
            "decision": "approved",
            "reviewer_id": "u_mod",
            "notes": "Reviewed and restored"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)
        reviewed = handler.get_response_json()
        self.assertEqual(reviewed["status"], "approved")

        # 7. Remove via POST /discussions/<id>/remove
        handler = DummyAPIHandler("POST", "/discussions/d_api_life/remove", body={
            "actor_id": "u_alice",
            "reason": "No longer needed"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # Restore via POST /discussions/<id>/restore
        handler = DummyAPIHandler("POST", "/discussions/d_api_life/restore", body={
            "actor_id": "u_alice"
        })
        handler.do_POST()
        self.assertEqual(handler._response_status, 200)

        # 8. Complete Lifecycle Audit Snapshot via GET /discussions/<id>/lifecycle
        handler = DummyAPIHandler("GET", "/discussions/d_api_life/lifecycle")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        life_snapshot = handler.get_response_json()
        self.assertEqual(life_snapshot["id"], "d_api_life")
        self.assertTrue(life_snapshot["is_active"])
        self.assertFalse(life_snapshot["is_removed"])
        self.assertEqual(life_snapshot["reports_count"], 1)
        self.assertEqual(life_snapshot["appeals_count"], 1)
        self.assertTrue(len(life_snapshot["events"]) >= 5)

        # GET /discussions/<id>/events
        handler = DummyAPIHandler("GET", "/discussions/d_api_life/events")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)
        events = handler.get_response_json()
        self.assertTrue(len(events) >= 5)

        # GET /content/discussion/<id>/lifecycle
        handler = DummyAPIHandler("GET", "/content/discussion/d_api_life/lifecycle")
        handler.do_GET()
        self.assertEqual(handler._response_status, 200)


if __name__ == "__main__":
    unittest.main()




