import unittest
import json
import io
import time
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer

from social_platform.core.models import (
    User, Discussion, DirectMessage, Notification,
    NotificationType, NotificationPreferences, PushSubscription, PushNotificationDispatch,
    ContentFilterPreferences
)
from social_platform.core.database import SocialDatabase
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


class TestNotificationModelsAndPreferences(unittest.TestCase):
    def test_notification_preferences_defaults_and_serialization(self):
        prefs = NotificationPreferences(user_id="u_ada")
        self.assertEqual(prefs.user_id, "u_ada")
        self.assertTrue(prefs.mentions)
        self.assertTrue(prefs.replies)
        self.assertTrue(prefs.endorsements)
        self.assertTrue(prefs.direct_messages)
        self.assertTrue(prefs.connections)
        self.assertTrue(prefs.in_app_enabled)
        self.assertTrue(prefs.push_enabled)
        self.assertFalse(prefs.email_enabled)
        self.assertEqual(prefs.digest_frequency, "instant")
        self.assertFalse(prefs.quiet_hours_enabled)
        self.assertEqual(prefs.min_endorsement_weight, 0.0)
        self.assertEqual(prefs.muted_senders, [])

        # Properties
        self.assertTrue(prefs.notify_mentions)
        self.assertTrue(prefs.notify_replies)
        self.assertTrue(prefs.notify_endorsements)
        self.assertTrue(prefs.notify_dms)
        self.assertTrue(prefs.notify_follows)

        # Serialization
        d = prefs.to_dict()
        self.assertEqual(d["user_id"], "u_ada")
        self.assertEqual(d["digest_frequency"], "instant")
        self.assertTrue(d["push_enabled"])

    def test_preferences_should_notify_and_muting(self):
        prefs = NotificationPreferences(
            user_id="u_ada",
            mentions=True,
            replies=False,
            endorsements=True,
            min_endorsement_weight=3.0,
            muted_senders=["u_spammer"]
        )

        # Muted sender check
        self.assertTrue(prefs.is_sender_muted("u_spammer"))
        self.assertFalse(prefs.is_sender_muted("u_babbage"))
        self.assertFalse(prefs.should_notify(NotificationType.MENTION, actor_id="u_spammer"))

        # Category check
        self.assertTrue(prefs.should_notify(NotificationType.MENTION, actor_id="u_babbage"))
        self.assertFalse(prefs.should_notify(NotificationType.REPLY, actor_id="u_babbage"))

        # Weight threshold on endorsements
        self.assertFalse(prefs.should_notify(NotificationType.ENDORSEMENT, actor_id="u_babbage", weight=2.5))
        self.assertTrue(prefs.should_notify(NotificationType.ENDORSEMENT, actor_id="u_babbage", weight=5.0))

    def test_quiet_hours_logic(self):
        # Quiet hours from 22:00 to 07:00 (spans midnight)
        prefs = NotificationPreferences(
            user_id="u_ada",
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00"
        )
        t_night = datetime(2026, 9, 6, 23, 30)
        t_early = datetime(2026, 9, 6, 6, 15)
        t_day = datetime(2026, 9, 6, 14, 0)

        self.assertTrue(prefs.is_in_quiet_hours(t_night))
        self.assertTrue(prefs.is_in_quiet_hours(t_early))
        self.assertFalse(prefs.is_in_quiet_hours(t_day))

        self.assertFalse(prefs.should_notify(NotificationType.MENTION, current_time=t_night))
        self.assertTrue(prefs.should_notify(NotificationType.MENTION, current_time=t_day))

    def test_push_subscription_model(self):
        sub = PushSubscription(
            id="sub_123",
            user_id="u_ada",
            endpoint="https://push.example.com/sub/123",
            p256dh="key_p256dh",
            auth="auth_secret",
            platform="web",
            device_name="MacBook Chrome"
        )
        self.assertTrue(sub.is_active)
        self.assertEqual(sub.platform, "web")
        d = sub.to_dict()
        self.assertEqual(d["id"], "sub_123")
        self.assertEqual(d["endpoint"], "https://push.example.com/sub/123")
        self.assertEqual(d["device_name"], "MacBook Chrome")


class TestNotificationDatabaseOperations(unittest.TestCase):
    def setUp(self):
        self.db = SocialDatabase(":memory:")
        self.db.create_user(User(id="u_ada", username="ada"))
        self.db.create_user(User(id="u_babbage", username="babbage"))
        self.db.create_user(User(id="u_turing", username="turing"))

    def test_push_subscription_lifecycle(self):
        # Register device
        sub = self.db.register_push_subscription(
            user_id="u_ada",
            endpoint="https://fcm.googleapis.com/fcm/send/token_ada_1",
            p256dh="key1",
            auth="auth1",
            platform="android",
            device_name="Pixel 9"
        )
        self.assertIsNotNone(sub.id)
        self.assertEqual(sub.user_id, "u_ada")
        self.assertEqual(sub.platform, "android")

        # List active subscriptions
        subs = self.db.get_push_subscriptions("u_ada", active_only=True)
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0].endpoint, "https://fcm.googleapis.com/fcm/send/token_ada_1")

        # Re-register same endpoint updates existing
        sub2 = self.db.register_push_subscription(
            user_id="u_ada",
            endpoint="https://fcm.googleapis.com/fcm/send/token_ada_1",
            device_name="Pixel 9 Pro"
        )
        self.assertEqual(sub.id, sub2.id)
        self.assertEqual(sub2.device_name, "Pixel 9 Pro")
        subs_after = self.db.get_push_subscriptions("u_ada")
        self.assertEqual(len(subs_after), 1)

        # Deactivate subscription
        self.db.deactivate_push_subscription(sub.id)
        self.assertEqual(len(self.db.get_push_subscriptions("u_ada", active_only=True)), 0)
        self.assertEqual(len(self.db.get_push_subscriptions("u_ada", active_only=False)), 1)

        # Unregister subscription
        unreg = self.db.unregister_push_subscription(sub.id)
        self.assertTrue(unreg)
        self.assertEqual(len(self.db.get_push_subscriptions("u_ada", active_only=False)), 0)

    def test_notification_preferences_crud_and_muting(self):
        # Default prefs
        prefs = self.db.get_notification_preferences("u_ada")
        self.assertTrue(prefs.mentions)
        self.assertTrue(prefs.push_enabled)

        # Update prefs
        updated = self.db.update_notification_preferences(
            "u_ada",
            replies=False,
            min_endorsement_weight=5.0,
            quiet_hours_enabled=True,
            quiet_hours_start="23:00",
            quiet_hours_end="06:00"
        )
        self.assertFalse(updated.replies)
        self.assertEqual(updated.min_endorsement_weight, 5.0)
        self.assertTrue(updated.quiet_hours_enabled)

        # Mute / unmute sender
        self.db.mute_notification_sender("u_ada", "u_turing")
        prefs_muted = self.db.get_notification_preferences("u_ada")
        self.assertIn("u_turing", prefs_muted.muted_senders)

        self.db.unmute_notification_sender("u_ada", "u_turing")
        prefs_unmuted = self.db.get_notification_preferences("u_ada")
        self.assertNotIn("u_turing", prefs_unmuted.muted_senders)

    def test_event_dispatching_for_replies_mentions_and_push_logs(self):
        # Register push devices for Ada
        self.db.register_push_subscription(
            user_id="u_ada",
            endpoint="https://push.apple.com/endpoint/ada_iphone",
            platform="ios",
            device_name="iPhone 16"
        )

        # Create root post by Ada
        root = self.db.create_discussion(
            Discussion(
                id="d_analytic",
                author_id="u_ada",
                content="Analytical Engine algorithms and Bernoulli numbers."
            )
        )

        # Babbage replies to Ada's post and mentions Turing (@turing)
        reply = self.db.create_discussion(
            Discussion(
                id="d_reply_babbage",
                author_id="u_babbage",
                parent_id="d_analytic",
                content="Splendid observation @turing! We must build the gears."
            )
        )

        # Verify Ada got reply notification & push dispatch
        ada_notifs = self.db.get_notifications("u_ada")
        self.assertTrue(any(n.type == "reply" and n.actor_id == "u_babbage" for n in ada_notifs))

        ada_dispatches = self.db.get_dispatched_notifications(user_id="u_ada")
        self.assertTrue(len(ada_dispatches) >= 1)
        self.assertEqual(ada_dispatches[0].channel, "push")
        self.assertEqual(ada_dispatches[0].status, "delivered")
        self.assertIn("notification_id", ada_dispatches[0].payload)

        # Verify Turing got mention notification
        turing_notifs = self.db.get_notifications("u_turing")
        self.assertTrue(any(n.type == "mention" and n.actor_id == "u_babbage" for n in turing_notifs))

    def test_endorsement_notification_weight_threshold(self):
        # Ada requires minimum endorsement weight of 10.0 to be notified
        self.db.update_notification_preferences("u_ada", min_endorsement_weight=10.0)

        post = self.db.create_discussion(Discussion(id="d_note_g", author_id="u_ada", content="Note G on computer algorithms"))

        # Low weight endorsement (weight = 2.0) -> suppressed by preference
        self.db.dispatch_notification(
            user_id="u_ada",
            type="endorsement",
            actor_id="u_babbage",
            target_id=post.id,
            content="Endorsed with 2.0",
            weight=2.0
        )
        notifs1 = self.db.get_notifications("u_ada")
        self.assertEqual(len(notifs1), 0)

        # High weight endorsement (weight = 15.0) -> dispatched
        self.db.dispatch_notification(
            user_id="u_ada",
            type="endorsement",
            actor_id="u_babbage",
            target_id=post.id,
            content="Endorsed with 15.0",
            weight=15.0
        )
        notifs2 = self.db.get_notifications("u_ada")
        self.assertEqual(len(notifs2), 1)
        self.assertEqual(notifs2[0].type, "endorsement")

    def test_suppression_on_block_and_muted_keyword(self):
        # Turing blocks Babbage
        self.db.block_user("u_turing", "u_babbage")

        notif = self.db.dispatch_notification(
            user_id="u_turing",
            type="direct_message",
            actor_id="u_babbage",
            target_id="dm_1",
            content="Hello Alan"
        )
        self.assertIsNone(notif)
        self.assertEqual(len(self.db.get_notifications("u_turing")), 0)

        # Content filtering mute
        self.db.set_content_filter_preferences(
            ContentFilterPreferences(
                user_id="u_ada",
                mute_keywords=["crypto", "spam"],
                filter_notifications=True
            )
        )
        filtered_notif = self.db.dispatch_notification(
            user_id="u_ada",
            type="mention",
            actor_id="u_babbage",
            target_id="d_123",
            content="Check out this crypto spam token!"
        )
        self.assertIsNone(filtered_notif)
        self.assertEqual(len(self.db.get_notifications("u_ada")), 0)

    def test_user_data_export_includes_notification_system_state(self):
        self.db.update_notification_preferences("u_ada", digest_frequency="daily")
        self.db.register_push_subscription(user_id="u_ada", endpoint="https://example.com/push/1")
        self.db.dispatch_notification(user_id="u_ada", type="announcement", actor_id="admin", target_id="sys", content="Welcome")

        export = self.db.export_user_data("u_ada")
        self.assertIn("notification_preferences", export)
        self.assertEqual(export["notification_preferences"]["digest_frequency"], "daily")
        self.assertIn("push_subscriptions", export)
        self.assertEqual(len(export["push_subscriptions"]), 1)
        self.assertIn("dispatched_notifications", export)


class TestNotificationClientAndAPIIntegration(unittest.TestCase):
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
        self.client = SocialPlatformClient(base_url=self.base_url)
        if not self.db.get_user("u_hypatia"):
            self.client.create_user(username="hypatia", user_id="u_hypatia")
        if not self.db.get_user("u_ptolemy"):
            self.client.create_user(username="ptolemy", user_id="u_ptolemy")
        conn = self.db.get_connection()
        conn.execute("DELETE FROM push_subscriptions WHERE user_id IN ('u_hypatia', 'u_ptolemy')")
        conn.execute("DELETE FROM notifications WHERE user_id IN ('u_hypatia', 'u_ptolemy')")
        conn.execute("DELETE FROM dispatched_notifications WHERE user_id IN ('u_hypatia', 'u_ptolemy')")
        conn.commit()

    def test_preferences_api_client_and_session(self):
        session = self.client.session("u_hypatia")

        # 1. Get default preferences
        prefs = session.get_notification_preferences()
        self.assertEqual(prefs["user_id"], "u_hypatia")
        self.assertTrue(prefs["mentions"])
        self.assertTrue(prefs["push_enabled"])

        # 2. Update preferences
        updated = session.update_notification_preferences(
            mentions=True,
            replies=False,
            digest_frequency="weekly",
            quiet_hours_enabled=True,
            quiet_hours_start="22:30",
            quiet_hours_end="07:30"
        )
        self.assertFalse(updated["replies"])
        self.assertEqual(updated["digest_frequency"], "weekly")
        self.assertTrue(updated["quiet_hours_enabled"])

        # 3. Verify persistence
        fetched = self.client.get_notification_preferences("u_hypatia")
        self.assertEqual(fetched["digest_frequency"], "weekly")
        self.assertFalse(fetched["replies"])

    def test_push_device_registration_and_dispatch_api(self):
        session = self.client.session("u_hypatia")

        # 1. Register push device
        sub = session.register_push_device(
            endpoint="https://fcm.googleapis.com/fcm/send/token_hypatia_web",
            p256dh="p256dh_key_xyz",
            auth="auth_secret_xyz",
            platform="web",
            device_name="Library Desktop"
        )
        sub_id = sub["id"]
        self.assertEqual(sub["endpoint"], "https://fcm.googleapis.com/fcm/send/token_hypatia_web")

        # 2. List push devices
        subs = session.list_push_subscriptions()
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["id"], sub_id)

        # 3. Dispatch notification via client
        disp_res = self.client.dispatch_notification(
            user_id="u_hypatia",
            type="course_update",
            actor_id="u_ptolemy",
            target_id="c_astronomy",
            content="New lecture notes on epicycles published.",
            title="Astronomy 101"
        )
        self.assertIn("id", disp_res)
        self.assertEqual(disp_res["type"], "course_update")

        # 4. View notifications and dispatches
        notifs = session.get_notifications(unread_only=True)
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["target_id"], "c_astronomy")

        dispatches = session.get_dispatched_notifications()
        self.assertTrue(len(dispatches) >= 1)
        self.assertEqual(dispatches[0]["subscription_id"], sub_id)
        self.assertEqual(dispatches[0]["payload"]["title"], "Astronomy 101")

        # 5. Mark read
        session.mark_all_notifications_read()
        self.assertEqual(session.get_unread_notification_count(), 0)

        # 6. Unregister device
        unreg = session.unregister_push_device(sub_id)
        self.assertTrue(unreg.get("success", True))
        self.assertEqual(len(session.list_push_subscriptions()), 0)

    def test_cli_notification_commands(self):
        cli = SocialCLI(base_url=self.base_url)

        # Test CLI prefs-get
        ret_get = cli.run(["notifs", "prefs-get", "u_hypatia", "--json"])
        self.assertEqual(ret_get, 0)

        # Test CLI prefs-set
        ret_set = cli.run(["notifs", "prefs-set", "u_hypatia", "--digest", "daily", "--min-weight", "4.5", "--json"])
        self.assertEqual(ret_set, 0)

        prefs = self.client.get_notification_preferences("u_hypatia")
        self.assertEqual(prefs["digest_frequency"], "daily")
        self.assertEqual(prefs["min_endorsement_weight"], 4.5)

        # Test CLI push-register
        ret_reg = cli.run(["notifs", "push-register", "u_hypatia", "https://push.example.com/token/cli_test", "--platform", "cli", "--device-name", "CLI Device", "--json"])
        self.assertEqual(ret_reg, 0)

        # Test CLI push-list
        ret_list = cli.run(["notifs", "push-list", "u_hypatia", "--json"])
        self.assertEqual(ret_list, 0)

        # Test CLI dispatches
        ret_disp = cli.run(["notifs", "dispatches", "u_hypatia", "--json"])
        self.assertEqual(ret_disp, 0)


if __name__ == "__main__":
    unittest.main()
