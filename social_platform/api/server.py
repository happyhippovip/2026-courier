from social_platform.api.pow001_sponsorship import reserve_block, get_genesis_registry
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from social_platform.core.database import SocialDatabase
from social_platform.core.models import (
    User, Discussion, Community, Channel, ModerationReport, CommunityMember, CommunityBan, Notification,
    UserBlock, DirectMessage, FeedItem, TopicSubscription, TopicTrend,
    CommunityJoinRequest, CommunityInvite, CommunityInviteToken, CommunityRole, COMMUNITY_ROLES,
    Course, CourseEnrollment, CourseResource, StudyGroup, StudyGroupMember,
    AcademicSpace, CourseSpace, ClassmateVerification, CourseMember,
    StudyResource, Syllabus, AcademicStudyGroup,
    MediaAttachment, Media, MediaMetadata, MediaAccessibility,
    ContentFilterPreferences, UserContentFilter, UserContentFilterPreferences, ContentFilteringPreferences,
    UserAccessibilitySettings, AccessibilitySettings, UserSettingsAccessibility,
    ModerationAppeal, ContentAppeal, ContentReport, ContentLifecycleEvent, ContentInteraction,
    ContentLifecycleState, ContentStatus, ContentLifecycleAction,
    TransformationOptions, DossierOptions, ExportPackagingOptions,
    DossierSection, TransformationDossier, ExportPackageManifest, ExportPackage,
    DossierFormat, ExportFormat, DossierType, ExportScope,
    NotificationPreferences, UserNotificationPreferences, NotificationPreference,
    PushSubscription, PushDevice, DeviceRegistration, UserPushSubscription,
    PushNotificationDispatch, NotificationDispatchRecord, DispatchedNotification, NotificationDispatch,
    NotificationType
)
from social_platform.core.feed import (
    generate_chronological_feed, generate_following_feed,
    generate_interest_matched_feed, generate_community_scoped_feed,
    generate_feed, FeedService, FeedMode
)

import uuid

# Global db instance for the server
db = SocialDatabase("social.db")

class SocialAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))

    def _send_error(self, message, status=400):
        self._send_json({"error": message}, status)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path_parts = [p for p in parsed.path.strip('/').split('/') if p]
        query_params = urllib.parse.parse_qs(parsed.query)

        if not path_parts:
            self._send_error("Not found", 404)
            return

        # /users/... or /profiles/...
        if path_parts[0] in ("users", "profiles"):
            if len(path_parts) == 1:
                q = query_params.get("q", query_params.get("query", [None]))[0]
                school = query_params.get("school", [None])[0]
                university = query_params.get("university", [None])[0]
                class_year = query_params.get("class_year", query_params.get("class", query_params.get("class_affiliation", [None])))[0]
                interest = query_params.get("interest", [None])[0]
                interests_raw = query_params.get("interests", query_params.get("interest"))
                interests = [i for i in interests_raw if i] if interests_raw else None
                public_only = query_params.get("public_only", query_params.get("publicly_discoverable_only", ["true"]))[0].lower() in ("true", "1")
                users = db.search_users(
                    query=q, school=school, university=university, class_year=class_year,
                    interest=interest, interests=interests, publicly_discoverable_only=public_only
                )
                self._send_json([u.__dict__ for u in users])
            elif len(path_parts) == 2:
                user = db.get_user(path_parts[1])
                if user:
                    self._send_json(user.__dict__)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] == "profile":
                user = db.get_user(path_parts[1])
                if user:
                    self._send_json(user.__dict__)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("dossier", "dossiers"):
                fmt = query_params.get("format", ["markdown"])[0]
                dtype = query_params.get("type", query_params.get("dossier_type", ["user_archive"]))[0]
                style = query_params.get("style", ["standard"])[0]
                anon = query_params.get("anonymize", query_params.get("anonymize_pii", ["false"]))[0].lower() in ("true", "1")
                redact_dms = query_params.get("redact_dms", query_params.get("redact_private_messages", ["false"]))[0].lower() in ("true", "1")
                opts = TransformationOptions(format=fmt, dossier_type=dtype, style=style, anonymize_pii=anon, redact_private_messages=redact_dms)
                dossier = db.generate_user_dossier(path_parts[1], format=fmt, dossier_type=dtype, options=opts)
                if dossier is not None:
                    self._send_json(dossier.to_dict(), 200)
                else:
                    self._send_error("User not found", 404)
            elif (len(path_parts) == 4 and path_parts[2] == "export" and path_parts[3] in ("package", "archive", "bundle")) or (len(path_parts) == 3 and path_parts[2] in ("package", "export_package", "archive")):
                fmt = query_params.get("format", ["zip"])[0]
                pkg = db.create_export_package(path_parts[1], format=fmt)
                if pkg is not None:
                    self._send_json(pkg.to_dict(), 200)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("export", "export_data", "data_export", "data"):
                export = db.export_user_data(path_parts[1])
                if export is not None:
                    self._send_json(export, 200)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("visibility", "privacy", "privacy_settings", "privacy_controls"):
                user = db.get_user(path_parts[1])
                if user:
                    self._send_json({
                        "user_id": path_parts[1],
                        "visibility": user.visibility,
                        "profile_visibility": user.visibility,
                        "dm_privacy": user.dm_privacy,
                        "allow_dms_from": user.dm_privacy,
                        "direct_message_privacy": user.dm_privacy,
                        "is_active": user.is_active,
                        "is_deactivated": user.is_deactivated,
                        "is_publicly_discoverable": user.is_publicly_discoverable
                    }, 200)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("dm_privacy", "direct_message_privacy", "allow_dms_from"):
                user = db.get_user(path_parts[1])
                if user:
                    self._send_json({
                        "user_id": path_parts[1],
                        "dm_privacy": user.dm_privacy,
                        "allow_dms_from": user.dm_privacy,
                        "direct_message_privacy": user.dm_privacy
                    }, 200)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 4 and path_parts[2] in ("can_message", "can_send_dm", "can_dm"):
                can_msg = db.can_send_direct_message(path_parts[1], path_parts[3])
                self._send_json({
                    "sender_id": path_parts[1],
                    "recipient_id": path_parts[3],
                    "can_message": can_msg,
                    "can_send_dm": can_msg,
                    "allowed": can_msg
                }, 200)
            elif len(path_parts) == 4 and path_parts[2] in ("can_view", "can_view_profile"):
                can_view = db.can_user_view_profile(path_parts[1], path_parts[3])
                self._send_json({
                    "viewer_id": path_parts[1],
                    "target_user_id": path_parts[3],
                    "can_view": can_view,
                    "allowed": can_view
                }, 200)
            elif len(path_parts) == 3 and path_parts[2] in ("active", "status", "is_active", "deactivated", "is_deactivated"):
                user = db.get_user(path_parts[1])
                if user:
                    self._send_json({
                        "user_id": path_parts[1],
                        "is_active": user.is_active,
                        "is_deactivated": user.is_deactivated
                    }, 200)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("discussions", "posts"):
                viewer_id = query_params.get("viewer_id", query_params.get("viewer", [None]))[0]
                discs = db.get_user_discussions(path_parts[1], viewer_id=viewer_id, include_replies=False)
                self._send_json([d.to_dict() if hasattr(d, "to_dict") else d.__dict__ for d in discs], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("replies",):
                viewer_id = query_params.get("viewer_id", query_params.get("viewer", [None]))[0]
                reps = db.get_user_replies(path_parts[1], viewer_id=viewer_id)
                self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reps], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("connections", "following"):
                conns = db.get_connections(path_parts[1])
                self._send_json([c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in conns], 200)
            elif len(path_parts) == 3 and path_parts[2] == "communities":
                user_communities = db.get_user_communities(path_parts[1])
                self._send_json([c.__dict__ for c in user_communities])
            elif len(path_parts) == 3 and path_parts[2] in ("topics", "subscriptions", "topic_subscriptions"):
                subs = db.get_user_topic_subscriptions(path_parts[1])
                self._send_json(subs)
            elif len(path_parts) == 4 and path_parts[2] in ("topics", "subscriptions", "topic_subscriptions"):
                is_sub = db.is_user_subscribed_to_topic(path_parts[1], path_parts[3])
                self._send_json({"user_id": path_parts[1], "topic": path_parts[3], "is_subscribed": is_sub})
            elif len(path_parts) == 3 and path_parts[2] in ("join_requests", "requests", "join_request"):
                status_filter = query_params.get("status", [None])[0]
                reqs = db.get_user_join_requests(path_parts[1], status=status_filter)
                self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reqs])
            elif len(path_parts) == 3 and path_parts[2] == "notifications":
                unread_only = query_params.get("unread_only", ["false"])[0].lower() in ("true", "1")
                notifs = db.get_notifications(path_parts[1], unread_only=unread_only)
                self._send_json([n.to_dict() if hasattr(n, "to_dict") else n.__dict__ for n in notifs])
            elif len(path_parts) == 4 and path_parts[2] == "notifications" and path_parts[3] == "count":
                count = db.get_unread_notification_count(path_parts[1])
                self._send_json({"unread_count": count, "user_id": path_parts[1]})
            elif (len(path_parts) == 3 and path_parts[2] in ("notification_preferences", "notification-preferences", "notif_preferences")) or (len(path_parts) == 4 and path_parts[2] == "notifications" and path_parts[3] in ("preferences", "prefs")):
                prefs = db.get_notification_preferences(path_parts[1])
                self._send_json(prefs.to_dict())
            elif (len(path_parts) == 3 and path_parts[2] in ("push_subscriptions", "push-subscriptions", "push_devices")) or (len(path_parts) == 4 and path_parts[2] == "notifications" and path_parts[3] in ("push_subscriptions", "push-subscriptions", "push")):
                active_only = query_params.get("active_only", ["true"])[0].lower() in ("true", "1")
                subs = db.get_push_subscriptions(path_parts[1], active_only=active_only)
                self._send_json([s.to_dict() for s in subs])
            elif (len(path_parts) == 3 and path_parts[2] in ("dispatches", "dispatched_notifications")) or (len(path_parts) == 4 and path_parts[2] == "notifications" and path_parts[3] in ("dispatches", "dispatched")):
                dispatches = db.get_dispatched_notifications(user_id=path_parts[1])
                self._send_json([d.to_dict() for d in dispatches])
            elif len(path_parts) == 3 and path_parts[2] in ("conversations", "dms"):
                convs = db.get_user_conversations(path_parts[1])
                formatted = []
                for c in convs:
                    item = dict(c)
                    if isinstance(item.get("last_message"), DirectMessage):
                        item["last_message"] = item["last_message"].__dict__
                    formatted.append(item)
                self._send_json(formatted)
            elif len(path_parts) == 4 and path_parts[2] in ("messages", "dms") and path_parts[3] in ("count", "unread_count"):
                count = db.get_unread_message_count(path_parts[1])
                self._send_json({"unread_count": count, "user_id": path_parts[1]})
            elif len(path_parts) == 4 and path_parts[2] in ("conversations", "messages", "dms"):
                msgs = db.get_direct_messages(path_parts[1], path_parts[3])
                self._send_json([m.__dict__ for m in msgs])
            elif len(path_parts) >= 3 and path_parts[2] == "feed":
                user_id = path_parts[1]
                sub_mode = path_parts[3] if len(path_parts) >= 4 else None
                mode_param = query_params.get("mode", query_params.get("type", query_params.get("ranking_mode", [None])))[0]
                mode = sub_mode or mode_param or "chronological"
                comm_id = query_params.get("community_id", query_params.get("community", [None]))[0]
                if len(path_parts) >= 5 and sub_mode in ("community", "community_scoped", "communities"):
                    comm_id = path_parts[4]
                channel_id = query_params.get("channel_id", query_params.get("channel", [None]))[0]
                interests_raw = query_params.get("interests", query_params.get("interest"))
                interests = [i for i in interests_raw if i] if interests_raw else None
                limit_param = query_params.get("limit", [None])[0]
                limit = int(limit_param) if limit_param and limit_param.isdigit() else None
                offset_param = query_params.get("offset", [None])[0]
                offset = int(offset_param) if offset_param and offset_param.isdigit() else None
                inc_hidden = query_params.get("include_hidden", ["false"])[0].lower() in ("true", "1")

                feed = db.get_feed(
                    user_id=user_id,
                    mode=mode,
                    community_id=comm_id,
                    channel_id=channel_id,
                    interests=interests,
                    limit=limit,
                    offset=offset,
                    include_hidden=inc_hidden
                )
                self._send_json([item.to_dict() if hasattr(item, "to_dict") else item.__dict__ for item in feed])
            elif len(path_parts) in (3, 4) and path_parts[2] in ("reputation", "reputations", "domain_reputation", "reputation_scores"):
                if len(path_parts) == 4:
                    domain = path_parts[3]
                    rep = db.get_user_domain_reputation(path_parts[1], domain)
                    self._send_json(rep.to_dict() if hasattr(rep, "to_dict") else (rep.__dict__ if rep else {"user_id": path_parts[1], "domain": domain, "reputation_score": 0.0}), 200)
                else:
                    domain = query_params.get("domain", [None])[0]
                    if domain:
                        rep = db.get_user_domain_reputation(path_parts[1], domain)
                        self._send_json(rep.to_dict() if hasattr(rep, "to_dict") else (rep.__dict__ if rep else {"user_id": path_parts[1], "domain": domain, "reputation_score": 0.0}), 200)
                    else:
                        reps = db.get_user_all_reputations(path_parts[1])
                        self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reps], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("courses", "enrolled_courses"):
                user_courses = db.get_user_courses(path_parts[1])
                self._send_json([c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in user_courses], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("enrollments", "course_enrollments"):
                user_enrs = db.get_user_enrollments(path_parts[1])
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in user_enrs], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("study_groups", "study-groups", "groups"):
                user_sgs = db.get_user_study_groups(path_parts[1])
                self._send_json([g.to_dict() if hasattr(g, "to_dict") else g.__dict__ for g in user_sgs], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("accessibility", "accessibility_settings", "accessibility-settings"):
                settings = db.get_accessibility_settings(path_parts[1])
                self._send_json(settings.to_dict() if hasattr(settings, "to_dict") else settings.__dict__, 200)
            elif len(path_parts) == 3 and path_parts[2] in ("content_filtering", "content_filters", "filter_preferences", "filtering_preferences", "content_filtering_preferences", "content-filtering"):
                prefs = db.get_content_filter_preferences(path_parts[1])
                self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)
            elif len(path_parts) == 3 and path_parts[2] in ("mute_keywords", "muted_keywords", "mute-keywords"):
                keywords = db.get_mute_keywords(path_parts[1])
                self._send_json({"user_id": path_parts[1], "mute_keywords": keywords, "muted_keywords": keywords}, 200)
            elif len(path_parts) == 3 and path_parts[2] in ("content_warnings", "content_warning_tags", "content-warnings", "cw_tags"):
                tags = db.get_content_warning_tags(path_parts[1])
                self._send_json({"user_id": path_parts[1], "content_warning_tags": tags, "content_warnings": tags}, 200)
            elif len(path_parts) == 3 and path_parts[2] in ("media", "media_attachments", "uploads"):
                media_list = db.get_user_media(path_parts[1])
                self._send_json([m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in media_list], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("blocks", "blocklist"):
                blocks = db.get_blocked_users(path_parts[1])
                self._send_json([b.__dict__ for b in blocks])
            elif len(path_parts) == 4 and path_parts[2] in ("blocks", "blocklist"):
                is_b = db.is_user_blocked(path_parts[1], path_parts[3])
                self._send_json({"blocker_id": path_parts[1], "blocked_id": path_parts[3], "is_blocked": is_b})
            else:
                self._send_error("Not found", 404)



        # /conversations/...
        elif path_parts[0] == "conversations":
            if len(path_parts) == 2:
                convs = db.get_user_conversations(path_parts[1])
                formatted = []
                for c in convs:
                    item = dict(c)
                    if isinstance(item.get("last_message"), DirectMessage):
                        item["last_message"] = item["last_message"].__dict__
                    formatted.append(item)
                self._send_json(formatted)
            elif len(path_parts) == 3:
                msgs = db.get_direct_messages(path_parts[1], path_parts[2])
                self._send_json([m.__dict__ for m in msgs])
            else:
                self._send_error("Not found", 404)

        # /messages or /direct_messages or /dms...
        elif path_parts[0] in ("messages", "direct_messages", "dms"):
            if len(path_parts) == 1:
                u1 = query_params.get("user1", [None])[0] or query_params.get("user_id", [None])[0]
                u2 = query_params.get("user2", [None])[0] or query_params.get("other_user_id", [None])[0]
                if u1 and u2:
                    msgs = db.get_direct_messages(u1, u2)
                    self._send_json([m.__dict__ for m in msgs])
                elif u1:
                    convs = db.get_user_conversations(u1)
                    formatted = []
                    for c in convs:
                        item = dict(c)
                        if isinstance(item.get("last_message"), DirectMessage):
                            item["last_message"] = item["last_message"].__dict__
                        formatted.append(item)
                    self._send_json(formatted)
                else:
                    self._send_error("user1 and user2 query parameters required")
            elif len(path_parts) == 2:
                msg = db.get_direct_message(path_parts[1])
                if msg:
                    self._send_json(msg.__dict__)
                else:
                    self._send_error("Message not found", 404)
            elif len(path_parts) == 3:
                msgs = db.get_direct_messages(path_parts[1], path_parts[2])
                self._send_json([m.__dict__ for m in msgs])
            else:
                self._send_error("Not found", 404)

        # /blocks or /blocklist...
        elif path_parts[0] in ("blocks", "blocklist"):
            if len(path_parts) == 2:
                blocks = db.get_blocked_users(path_parts[1])
                self._send_json([b.__dict__ for b in blocks])
            elif len(path_parts) == 3:
                is_b = db.is_user_blocked(path_parts[1], path_parts[2])
                self._send_json({"blocker_id": path_parts[1], "blocked_id": path_parts[2], "is_blocked": is_b})
            else:
                self._send_error("Not found", 404)

        # /notifications/...
        elif path_parts[0] == "notifications":
            if len(path_parts) == 2 and path_parts[1] in ("dispatches", "dispatched", "logs"):
                uid = query_params.get("user_id", [None])[0]
                nid = query_params.get("notification_id", [None])[0]
                channel = query_params.get("channel", [None])[0]
                dispatches = db.get_dispatched_notifications(user_id=uid, notification_id=nid, channel=channel)
                self._send_json([d.to_dict() for d in dispatches])
            elif len(path_parts) == 3 and path_parts[1] in ("preferences", "prefs"):
                prefs = db.get_notification_preferences(path_parts[2])
                self._send_json(prefs.to_dict())
            elif len(path_parts) == 2:
                unread_only = query_params.get("unread_only", ["false"])[0].lower() in ("true", "1")
                notifs = db.get_notifications(path_parts[1], unread_only=unread_only)
                self._send_json([n.to_dict() if hasattr(n, "to_dict") else n.__dict__ for n in notifs])
            elif len(path_parts) == 3 and path_parts[2] == "count":
                count = db.get_unread_notification_count(path_parts[1])
                self._send_json({"unread_count": count, "user_id": path_parts[1]})
            elif len(path_parts) == 3 and path_parts[2] in ("dispatches", "dispatched"):
                dispatches = db.get_dispatched_notifications(user_id=path_parts[1])
                self._send_json([d.to_dict() for d in dispatches])
            else:
                self._send_error("Not found", 404)

        # /push_subscriptions or /push_devices...
        elif path_parts[0] in ("push_subscriptions", "push-subscriptions", "push_devices", "push-devices", "push"):
            if len(path_parts) == 1:
                uid = query_params.get("user_id", [None])[0]
                active_only = query_params.get("active_only", ["true"])[0].lower() in ("true", "1")
                if uid:
                    subs = db.get_push_subscriptions(uid, active_only=active_only)
                    self._send_json([s.to_dict() for s in subs])
                else:
                    self._send_error("user_id parameter required", 400)
            elif len(path_parts) == 2:
                sub = db.get_push_subscription(path_parts[1]) or db.get_push_subscription_by_endpoint(path_parts[1])
                if sub:
                    self._send_json(sub.to_dict())
                else:
                    self._send_error("Push subscription not found", 404)
            else:
                self._send_error("Not found", 404)

        # /search or /discovery...
        elif path_parts[0] in ("search", "discovery"):
            q = query_params.get("q", query_params.get("query", [""]))[0]
            search_type = query_params.get("type", ["all"])[0]
            public_only = query_params.get("public_only", query_params.get("publicly_discoverable_only", ["true"]))[0].lower() in ("true", "1")
            viewer_id = query_params.get("viewer_id", query_params.get("viewer", query_params.get("user_id", [None])))[0]
            school = query_params.get("school", [None])[0]
            university = query_params.get("university", [None])[0]
            class_year = query_params.get("class_year", query_params.get("class", query_params.get("class_affiliation", [None])))[0]
            interest = query_params.get("interest", [None])[0]
            interests_raw = query_params.get("interests", query_params.get("interest"))
            interests = [i for i in interests_raw if i] if interests_raw else None

            if len(path_parts) == 2 and path_parts[1] == "discussions":
                discs = db.search_discussions(q, viewer_id=viewer_id)
                self._send_json([d.__dict__ for d in discs])
            elif len(path_parts) == 2 and path_parts[1] == "communities":
                comms = db.search_communities(q, viewer_id=viewer_id)
                self._send_json([c.__dict__ for c in comms])
            elif len(path_parts) == 2 and path_parts[1] in ("users", "profiles"):
                users = db.search_users(
                    query=q, school=school, university=university, class_year=class_year,
                    interest=interest, interests=interests, publicly_discoverable_only=public_only,
                    viewer_id=viewer_id
                )
                self._send_json([u.__dict__ for u in users])
            elif len(path_parts) == 2 and path_parts[1] in ("courses", "academic_spaces", "course_spaces"):
                courses = db.search_courses(q, institution=university or school)
                self._send_json([c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in courses])
            elif len(path_parts) == 2 and path_parts[1] in ("study_groups", "study-groups", "groups"):
                sgs = db.search_study_groups(q, institution=university or school)
                self._send_json([g.to_dict() if hasattr(g, "to_dict") else g.__dict__ for g in sgs])
            elif len(path_parts) == 1:
                if search_type == "discussions":
                    discs = db.search_discussions(q, viewer_id=viewer_id)
                    self._send_json([d.__dict__ for d in discs])
                elif search_type == "communities":
                    comms = db.search_communities(q, viewer_id=viewer_id)
                    self._send_json([c.__dict__ for c in comms])
                elif search_type in ("users", "profiles"):
                    users = db.search_users(
                        query=q, school=school, university=university, class_year=class_year,
                        interest=interest, interests=interests, publicly_discoverable_only=public_only,
                        viewer_id=viewer_id
                    )
                    self._send_json([u.__dict__ for u in users])
                elif search_type in ("courses", "academic_spaces"):
                    courses = db.search_courses(q, institution=university or school)
                    self._send_json({"courses": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in courses]})
                elif search_type in ("study_groups", "study-groups"):
                    sgs = db.search_study_groups(q, institution=university or school)
                    self._send_json({"study_groups": [g.to_dict() if hasattr(g, "to_dict") else g.__dict__ for g in sgs]})
                else:
                    res = db.search(
                        q, publicly_discoverable_only=public_only,
                        school=school, university=university, class_year=class_year, interest=interest,
                        viewer_id=viewer_id
                    )
                    self._send_json({
                        "query": q,
                        "discussions": [d.__dict__ for d in res["discussions"]],
                        "communities": [c.__dict__ for c in res["communities"]],
                        "courses": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in res.get("courses", [])],
                        "study_groups": [g.to_dict() if hasattr(g, "to_dict") else g.__dict__ for g in res.get("study_groups", [])],
                        "users": [u.__dict__ for u in res["users"]]
                    })
            else:
                self._send_error("Not found", 404)

        # /feed/...
        elif path_parts[0] == "feed":
            if len(path_parts) >= 2:
                user_id = path_parts[1]
                sub_mode = path_parts[2] if len(path_parts) >= 3 else None
                mode_param = query_params.get("mode", query_params.get("type", query_params.get("ranking_mode", [None])))[0]
                mode = sub_mode or mode_param or "chronological"
                comm_id = query_params.get("community_id", query_params.get("community", [None]))[0]
                if len(path_parts) >= 4 and sub_mode in ("community", "community_scoped", "communities"):
                    comm_id = path_parts[3]
                channel_id = query_params.get("channel_id", query_params.get("channel", [None]))[0]
                interests_raw = query_params.get("interests", query_params.get("interest"))
                interests = [i for i in interests_raw if i] if interests_raw else None
                limit_param = query_params.get("limit", [None])[0]
                limit = int(limit_param) if limit_param and limit_param.isdigit() else None
                offset_param = query_params.get("offset", [None])[0]
                offset = int(offset_param) if offset_param and offset_param.isdigit() else None
                inc_hidden = query_params.get("include_hidden", ["false"])[0].lower() in ("true", "1")

                domain_param = query_params.get("domain", [None])[0]

                feed = db.get_feed(
                    user_id=user_id,
                    mode=mode,
                    community_id=comm_id,
                    channel_id=channel_id,
                    interests=interests,
                    domain=domain_param,
                    limit=limit,
                    offset=offset,
                    include_hidden=inc_hidden
                )
                self._send_json([item.to_dict() if hasattr(item, "to_dict") else item.__dict__ for item in feed])
            else:
                self._send_error("user_id required for feed", 400)


        # /discussions/...
        elif path_parts[0] == "discussions":
            if len(path_parts) == 1:
                all_discs = db.get_all_discussions()
                self._send_json([d.__dict__ for d in all_discs])
            elif len(path_parts) == 2:
                disc = db.get_discussion(path_parts[1])
                if disc:
                    self._send_json(disc.to_dict() if hasattr(disc, "to_dict") else disc.__dict__)
                else:
                    self._send_error("Discussion not found", 404)
            elif len(path_parts) == 3 and path_parts[2] == "replies":
                replies = db.get_replies(path_parts[1])
                self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in replies])
            elif len(path_parts) == 3 and path_parts[2] in ("endorsements", "endorse", "value_endorsements"):
                ends = db.get_discussion_endorsements(path_parts[1])
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in ends], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("media", "media_attachments", "attachments"):
                media_list = db.get_discussion_media(path_parts[1])
                self._send_json([m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in media_list], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("visibility", "privacy"):
                disc = db.get_discussion(path_parts[1])
                if disc:
                    self._send_json({"discussion_id": path_parts[1], "visibility": disc.visibility}, 200)
                else:
                    self._send_error("Discussion not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("lifecycle", "lifecycle_state", "state"):
                lifecycle = db.get_discussion_lifecycle(path_parts[1])
                if lifecycle:
                    self._send_json(lifecycle, 200)
                else:
                    self._send_error("Discussion not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("events", "lifecycle_events", "history"):
                events = db.get_content_lifecycle_events("discussion", path_parts[1])
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in events], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("reports",):
                reports = db.get_discussion_reports(path_parts[1])
                self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reports], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("appeals",):
                appeals = db.get_moderation_appeals(target_id=path_parts[1])
                self._send_json([a.to_dict() if hasattr(a, "to_dict") else a.__dict__ for a in appeals], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("interactions", "interaction", "interact"):
                interactions = db.get_discussion_interactions(path_parts[1])
                self._send_json([i.to_dict() if hasattr(i, "to_dict") else i.__dict__ for i in interactions], 200)
            elif len(path_parts) == 3 and path_parts[2] in ("dossier", "dossiers", "export"):
                fmt = query_params.get("format", ["markdown"])[0]
                style = query_params.get("style", ["standard"])[0]
                anon = query_params.get("anonymize", query_params.get("anonymize_pii", ["false"]))[0].lower() in ("true", "1")
                opts = TransformationOptions(format=fmt, style=style, anonymize_pii=anon)
                dossier = db.generate_discussion_dossier(path_parts[1], format=fmt, options=opts)
                if dossier:
                    self._send_json(dossier.to_dict(), 200)
                else:
                    self._send_error("Discussion not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("status",):
                disc = db.get_discussion(path_parts[1])
                if disc:
                    self._send_json({
                        "discussion_id": disc.id,
                        "status": disc.status,
                        "moderation_status": disc.moderation_status,
                        "report_count": disc.report_count,
                        "interaction_count": disc.interaction_count,
                        "is_active": disc.is_active,
                        "is_removed": disc.is_removed,
                        "is_moderated": disc.is_moderated,
                        "is_under_appeal": disc.is_under_appeal,
                    }, 200)
                else:
                    self._send_error("Discussion not found", 404)
            else:
                self._send_error("Not found", 404)

        # /pow001/registry
        elif path_parts[0] == "pow001" and len(path_parts) == 2 and path_parts[1] == "registry":
            return self._send_json({"status": "success", "blocks": get_genesis_registry()})

        # /communities/...
        elif path_parts[0] == "communities":
            if len(path_parts) == 1:
                communities = db.get_all_communities()
                self._send_json([c.__dict__ for c in communities])
            elif len(path_parts) == 2:
                comm = db.get_community(path_parts[1])
                if comm:
                    self._send_json(comm.__dict__)
                else:
                    self._send_error("Community not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("dossier", "dossiers", "digest", "export"):
                fmt = query_params.get("format", ["markdown"])[0]
                style = query_params.get("style", ["standard"])[0]
                anon = query_params.get("anonymize", query_params.get("anonymize_pii", ["false"]))[0].lower() in ("true", "1")
                opts = TransformationOptions(format=fmt, style=style, anonymize_pii=anon)
                dossier = db.generate_community_dossier(path_parts[1], format=fmt, options=opts)
                if dossier:
                    self._send_json(dossier.to_dict(), 200)
                else:
                    self._send_error("Community not found", 404)
            elif len(path_parts) == 3 and path_parts[2] == "channels":
                channels = db.get_community_channels(path_parts[1])
                self._send_json([c.__dict__ for c in channels])
            elif len(path_parts) == 3 and path_parts[2] == "members":
                role_filter = query_params.get("role", [None])[0]
                members = db.get_community_members(path_parts[1], role=role_filter)
                self._send_json([m.__dict__ for m in members])
            elif len(path_parts) == 4 and path_parts[2] in ("members", "member", "roles", "role"):
                member = db.get_community_member(path_parts[1], path_parts[3])
                if member:
                    self._send_json(member.__dict__)
                else:
                    self._send_error("Member not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("join_requests", "requests", "join_request"):
                status_filter = query_params.get("status", [None])[0]
                reqs = db.get_community_join_requests(path_parts[1], status=status_filter)
                self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reqs])
            elif len(path_parts) == 3 and path_parts[2] in ("invites", "invite"):
                active_only = query_params.get("active_only", ["true"])[0].lower() in ("true", "1")
                invs = db.get_community_invites(path_parts[1], active_only=active_only)
                self._send_json([i.to_dict() if hasattr(i, "to_dict") else i.__dict__ for i in invs])
            elif len(path_parts) == 3 and path_parts[2] == "discussions":
                discs = db.get_community_discussions(path_parts[1])
                self._send_json([d.__dict__ for d in discs])
            elif len(path_parts) == 3 and path_parts[2] == "bans":
                bans = db.get_community_bans(path_parts[1])
                self._send_json([b.__dict__ for b in bans])
            else:
                self._send_error("Not found", 404)

        # /join_requests/...
        elif path_parts[0] in ("join_requests", "join_request"):
            if len(path_parts) == 2:
                req = db.get_join_request(path_parts[1])
                if req:
                    self._send_json(req.to_dict() if hasattr(req, "to_dict") else req.__dict__)
                else:
                    self._send_error("Join request not found", 404)
            else:
                self._send_error("Not found", 404)

        # /invites/...
        elif path_parts[0] in ("invites", "invite"):
            if len(path_parts) == 2:
                inv = db.get_invite(path_parts[1])
                if inv:
                    self._send_json(inv.to_dict() if hasattr(inv, "to_dict") else inv.__dict__)
                else:
                    self._send_error("Invite not found", 404)
            else:
                self._send_error("Not found", 404)

        # /channels/...
        elif path_parts[0] == "channels":
            if len(path_parts) == 2:
                ch = db.get_channel(path_parts[1])
                if ch:
                    self._send_json(ch.__dict__)
                else:
                    self._send_error("Channel not found", 404)
            elif len(path_parts) == 3 and path_parts[2] == "discussions":
                discs = db.get_channel_discussions(path_parts[1])
                self._send_json([d.__dict__ for d in discs])
            else:
                self._send_error("Not found", 404)

        # /courses or /academic_spaces or /course_spaces...
        elif path_parts[0] in ("courses", "academic_spaces", "course_spaces", "academic"):
            course_sub_parts = path_parts[1:] if path_parts[0] != "academic" else (path_parts[2:] if len(path_parts) >= 2 and path_parts[1] == "courses" else path_parts[1:])
            if len(course_sub_parts) == 0:
                q = query_params.get("q", query_params.get("query", [None]))[0]
                inst = query_params.get("institution", query_params.get("university", query_params.get("school", [None])))[0]
                term = query_params.get("term", query_params.get("semester", [None]))[0]
                code = query_params.get("code", query_params.get("course_code", [None]))[0]
                courses = db.get_courses(institution=inst, term=term, query=q, code=code)
                self._send_json([c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in courses], 200)
            elif len(course_sub_parts) == 1:
                course = db.get_course(course_sub_parts[0]) or db.get_course_by_code(course_sub_parts[0])
                if course:
                    self._send_json(course.to_dict() if hasattr(course, "to_dict") else course.__dict__, 200)
                else:
                    self._send_error("Course not found", 404)
            elif len(course_sub_parts) == 2:
                cid = course_sub_parts[0]
                sub = course_sub_parts[1]
                if sub in ("discussions", "posts"):
                    discs = db.get_course_discussions(cid)
                    self._send_json([d.to_dict() if hasattr(d, "to_dict") else d.__dict__ for d in discs], 200)
                elif sub in ("resources", "materials"):
                    res_type = query_params.get("type", query_params.get("resource_type", [None]))[0]
                    tag = query_params.get("tag", [None])[0]
                    resources = db.get_course_resources(cid, resource_type=res_type, tag=tag)
                    self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in resources], 200)
                elif sub in ("syllabus",):
                    syl = db.get_course_syllabus(cid)
                    if syl:
                        self._send_json(syl.to_dict() if hasattr(syl, "to_dict") else syl.__dict__, 200)
                    else:
                        self._send_error("Syllabus not found", 404)
                elif sub in ("reputation", "reputation_metrics", "metrics"):
                    metrics = db.get_course_reputation_metrics(cid)
                    self._send_json(metrics.to_dict() if hasattr(metrics, "to_dict") else metrics.__dict__, 200)
                elif sub in ("enrollments", "members", "students"):
                    ver_only = query_params.get("verified_only", ["false"])[0].lower() in ("true", "1")
                    role_filter = query_params.get("role", [None])[0]
                    enrs = db.get_course_enrollments(cid, verified_only=ver_only, role=role_filter)
                    self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in enrs], 200)
                elif sub in ("classmates", "verified_classmates"):
                    uid = query_params.get("user_id", [None])[0]
                    if uid:
                        classmates = db.get_verified_classmates(uid, course_id=cid)
                    else:
                        classmates = db.get_verified_classmates(cid)
                    self._send_json([u.to_dict() if hasattr(u, "to_dict") else u.__dict__ for u in classmates], 200)
                elif sub in ("study_groups", "study-groups", "groups"):
                    sgs = db.get_course_study_groups(cid)
                    self._send_json([g.to_dict() if hasattr(g, "to_dict") else g.__dict__ for g in sgs], 200)
                else:
                    self._send_error("Not found", 404)
            elif len(course_sub_parts) == 3 and course_sub_parts[1] in ("enrollments", "members", "classmates", "is_enrolled", "verified"):
                cid = course_sub_parts[0]
                uid = course_sub_parts[2]
                is_enr = db.is_user_enrolled(cid, uid)
                is_ver = db.is_verified_classmate(uid, course_id=cid)
                self._send_json({"course_id": cid, "user_id": uid, "is_enrolled": is_enr, "is_verified_classmate": is_ver}, 200)
            else:
                self._send_error("Not found", 404)

        # /resources or /course_resources...
        elif path_parts[0] in ("resources", "course_resources", "course-resources"):
            if len(path_parts) == 2:
                res = db.get_course_resource(path_parts[1])
                if res:
                    self._send_json(res.to_dict() if hasattr(res, "to_dict") else res.__dict__, 200)
                else:
                    self._send_error("Resource not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("endorsements", "endorse", "value_endorsements"):
                ends = db.get_resource_endorsements(path_parts[1])
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in ends], 200)
            else:
                self._send_error("Not found", 404)

        # /study_groups or /study-groups or /academic_groups...
        elif path_parts[0] in ("study_groups", "study-groups", "academic_groups"):
            if len(path_parts) == 1:
                cid = query_params.get("course_id", [None])[0]
                inst = query_params.get("institution", query_params.get("university", query_params.get("school", [None])))[0]
                uid = query_params.get("user_id", [None])[0]
                q = query_params.get("q", query_params.get("query", [None]))[0]
                groups = db.get_study_groups(course_id=cid, institution=inst, user_id=uid, query=q)
                self._send_json([g.to_dict() if hasattr(g, "to_dict") else g.__dict__ for g in groups], 200)
            elif len(path_parts) == 2:
                sg = db.get_study_group(path_parts[1])
                if sg:
                    self._send_json(sg.to_dict() if hasattr(sg, "to_dict") else sg.__dict__, 200)
                else:
                    self._send_error("Study group not found", 404)
            elif len(path_parts) == 3:
                sg_id = path_parts[1]
                sub = path_parts[2]
                if sub in ("members",):
                    members = db.get_study_group_members(sg_id)
                    self._send_json([m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in members], 200)
                elif sub in ("discussions", "posts"):
                    discs = db.get_study_group_discussions(sg_id)
                    self._send_json([d.to_dict() if hasattr(d, "to_dict") else d.__dict__ for d in discs], 200)
                elif sub in ("resources", "materials"):
                    res_type = query_params.get("type", query_params.get("resource_type", [None]))[0]
                    resources = db.get_study_group_resources(sg_id, resource_type=res_type)
                    self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in resources], 200)
                elif sub in ("reputation", "reputation_metrics", "metrics"):
                    metrics = db.get_study_group_reputation_metrics(sg_id)
                    self._send_json(metrics.to_dict() if hasattr(metrics, "to_dict") else metrics.__dict__, 200)
                else:
                    self._send_error("Not found", 404)
            else:
                self._send_error("Not found", 404)

        # /reports or /moderation/reports...
        elif (path_parts[0] == "reports") or (path_parts[0] == "moderation" and len(path_parts) >= 2 and path_parts[1] == "reports"):
            report_sub_parts = path_parts[1:] if path_parts[0] == "reports" else path_parts[2:]
            if len(report_sub_parts) == 0:
                status_filter = query_params.get("status", [None])[0]
                target_type_filter = query_params.get("target_type", [None])[0]
                reports = db.get_moderation_reports(status=status_filter, target_type=target_type_filter)
                self._send_json([r.__dict__ for r in reports])
            elif len(report_sub_parts) == 1:
                report = db.get_moderation_report(report_sub_parts[0])
                if report:
                    self._send_json(report.__dict__)
                else:
                    self._send_error("Report not found", 404)
            else:
                self._send_error("Not found", 404)

        # /appeals or /moderation/appeals...
        elif (path_parts[0] == "appeals") or (path_parts[0] == "moderation" and len(path_parts) >= 2 and path_parts[1] == "appeals"):
            appeal_sub_parts = path_parts[1:] if path_parts[0] == "appeals" else path_parts[2:]
            if len(appeal_sub_parts) == 0:
                status_filter = query_params.get("status", [None])[0]
                appeals = db.get_moderation_appeals(status=status_filter)
                self._send_json([a.to_dict() if hasattr(a, "to_dict") else a.__dict__ for a in appeals])
            elif len(appeal_sub_parts) == 1:
                appeal = db.get_moderation_appeal(appeal_sub_parts[0])
                if appeal:
                    self._send_json(appeal.to_dict() if hasattr(appeal, "to_dict") else appeal.__dict__)
                else:
                    self._send_error("Appeal not found", 404)
            else:
                self._send_error("Not found", 404)

        # /accessibility/...
        elif path_parts[0] in ("accessibility", "accessibility_settings", "accessibility-settings"):
            if len(path_parts) == 2:
                settings = db.get_accessibility_settings(path_parts[1])
                self._send_json(settings.to_dict() if hasattr(settings, "to_dict") else settings.__dict__, 200)
            else:
                self._send_error("User ID required", 400)

        # /content_filtering or /filter_preferences...
        elif path_parts[0] in ("content_filtering", "content_filters", "filter_preferences", "filtering_preferences", "content_filtering_preferences", "content-filtering"):
            if len(path_parts) == 2:
                prefs = db.get_content_filter_preferences(path_parts[1])
                self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)
            else:
                self._send_error("User ID required", 400)

        # /media or /media_attachments...
        elif path_parts[0] in ("media", "media_attachments", "media_metadata"):
            if len(path_parts) == 1:
                uploader = query_params.get("uploader_id", query_params.get("user_id", [None]))[0]
                disc_id = query_params.get("discussion_id", [None])[0]
                if disc_id:
                    media_list = db.get_discussion_media(disc_id)
                elif uploader:
                    media_list = db.get_user_media(uploader)
                else:
                    media_list = []
                self._send_json([m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in media_list], 200)
            elif len(path_parts) >= 2:
                media_obj = db.get_media(path_parts[1])
                if media_obj:
                    self._send_json(media_obj.to_dict() if hasattr(media_obj, "to_dict") else media_obj.__dict__, 200)
                else:
                    self._send_error("Media not found", 404)

        # /content/<target_type>/<target_id>/...
        elif path_parts[0] in ("content", "lifecycle"):
            if len(path_parts) >= 3:
                target_type = path_parts[1]
                target_id = path_parts[2]
                sub = path_parts[3] if len(path_parts) >= 4 else "lifecycle"
                if sub in ("lifecycle", "state", "status"):
                    lifecycle = db.get_content_lifecycle(target_type, target_id)
                    if lifecycle:
                        self._send_json(lifecycle, 200)
                    else:
                        self._send_error("Content not found", 404)
                elif sub in ("events", "history"):
                    events = db.get_content_lifecycle_events(target_type, target_id)
                    self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in events], 200)
                elif sub in ("reports",):
                    reports = db.get_content_reports(target_type, target_id)
                    self._send_json([r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reports], 200)
                elif sub in ("appeals",):
                    appeals = db.get_content_appeals(target_type, target_id)
                    self._send_json([a.to_dict() if hasattr(a, "to_dict") else a.__dict__ for a in appeals], 200)
                elif sub in ("interactions",):
                    interactions = db.get_content_interactions(target_type, target_id)
                    self._send_json([i.to_dict() if hasattr(i, "to_dict") else i.__dict__ for i in interactions], 200)
                else:
                    self._send_error("Not found", 404)
            else:
                self._send_error("Not found", 404)

        # /export/... or /dossiers/...
        elif path_parts[0] in ("export", "exports", "dossier", "dossiers"):
            if len(path_parts) >= 2 and path_parts[1] in ("formats", "types", "supported", "options"):
                self._send_json({
                    "supported_formats": ["markdown", "html", "json", "text", "csv", "zip", "tar"],
                    "supported_dossier_types": ["user_archive", "user_profile", "academic_portfolio", "research_dossier", "community_digest", "discussion_thread", "gdpr_package"]
                }, 200)
            else:
                self._send_error("Not found", 404)

        # /reputation/...
        elif path_parts[0] in ("reputation", "reputations", "leaderboard", "leaderboards"):
            if len(path_parts) == 3 and path_parts[1] == "summary":
                user_id = path_parts[2]
                summary = db.get_user_reputation_summary(user_id)
                self._send_json(summary, 200)
                return

            limit_param = query_params.get("limit", [None])[0]
            limit = int(limit_param) if limit_param and limit_param.isdigit() else 20
            if len(path_parts) >= 2 and path_parts[1] in ("leaderboard", "top", "rankings"):
                domain = path_parts[2] if len(path_parts) >= 3 else query_params.get("domain", ["general"])[0]
                entries = db.get_top_contributors_by_domain(domain=domain, limit=limit)
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in entries], 200)
            elif len(path_parts) == 2:
                domain = path_parts[1]
                entries = db.get_top_contributors_by_domain(domain=domain, limit=limit)
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in entries], 200)
            else:
                domain = query_params.get("domain", ["general"])[0]
                entries = db.get_top_contributors_by_domain(domain=domain, limit=limit)
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in entries], 200)

        # /endorsements/...
        elif path_parts[0] in ("endorsements", "endorse"):
            if len(path_parts) >= 2:
                target_id = path_parts[1]
                ends = db.get_discussion_endorsements(target_id)
                if not ends:
                    ends = db.get_resource_endorsements(target_id)
                self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in ends], 200)
            else:
                target_type = query_params.get("target_type", query_params.get("type", [None]))[0]
                target_id = query_params.get("target_id", query_params.get("id", [None]))[0]
                if target_type and target_id:
                    ends = db.get_endorsements(target_type, target_id)
                    self._send_json([e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in ends], 200)
                else:
                    self._send_error("target_id required", 400)

        else:
            self._send_error("Not found", 404)

    def _handle_profile_update(self, user_id, body):
        user = db.get_user(user_id)
        if not user:
            return self._send_error("User not found", 404)

        bio = body.get("bio")
        avatar_url = body.get("avatar_url")
        school = body.get("school")
        university = body.get("university")
        class_year = body.get("class_year") or body.get("class_affiliation") or body.get("class_name")
        interests = body.get("interests")
        if interests is None and "topic_interests" in body:
            interests = body.get("topic_interests")
        is_public = body.get("is_publicly_discoverable")
        is_active = body.get("is_active")
        if is_active is None and "is_deactivated" in body:
            is_active = not bool(body.get("is_deactivated"))
        visibility = body.get("visibility") or body.get("profile_visibility")
        username = body.get("username")

        if "affiliations" in body and isinstance(body["affiliations"], dict):
            aff = body["affiliations"]
            if school is None and "school" in aff:
                school = aff["school"]
            if university is None and "university" in aff:
                university = aff["university"]
            if class_year is None and "class_year" in aff:
                class_year = aff["class_year"]
            elif class_year is None and "class" in aff:
                class_year = aff["class"]

        updated = db.update_user_profile(
            user_id=user_id,
            bio=bio,
            avatar_url=avatar_url,
            school=school,
            university=university,
            class_year=class_year,
            interests=interests,
            is_publicly_discoverable=is_public,
            is_active=is_active,
            visibility=visibility,
            username=username
        )
        if updated:
            self._send_json(updated.to_dict() if hasattr(updated, "to_dict") else updated.__dict__, 200)
        else:
            self._send_error("Failed to update profile", 500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path_parts = [p for p in parsed.path.strip('/').split('/') if p]
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        try:
            body = json.loads(post_data.decode('utf-8')) if post_data else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return

        # POST /users
        if parsed.path == "/pow001/reserve":
            return self._send_json(reserve_block(body.get("company_name", "Anonymous"), body.get("logo_url", "")))

        if parsed.path == "/users":
            if "username" not in body:
                return self._send_error("username required")
            uid = body.get("id", str(uuid.uuid4()))
            bio = body.get("bio", "")
            avatar_url = body.get("avatar_url")
            school = body.get("school", "")
            university = body.get("university", "")
            class_year = body.get("class_year") or body.get("class_affiliation") or body.get("class_name") or ""
            interests = body.get("interests", body.get("topic_interests", []))
            is_public = bool(body.get("is_publicly_discoverable", False))
            is_active = bool(body.get("is_active", not bool(body.get("is_deactivated", False))))
            visibility = body.get("visibility", body.get("profile_visibility", "public"))

            if "affiliations" in body and isinstance(body["affiliations"], dict):
                aff = body["affiliations"]
                if not school and "school" in aff:
                    school = aff["school"]
                if not university and "university" in aff:
                    university = aff["university"]
                if not class_year and "class_year" in aff:
                    class_year = aff["class_year"]
                elif not class_year and "class" in aff:
                    class_year = aff["class"]

            u = User(
                id=uid, username=body["username"], is_active=is_active,
                is_publicly_discoverable=is_public, visibility=visibility, bio=bio, avatar_url=avatar_url,
                school=school, university=university, class_year=class_year, interests=interests
            )
            db.create_user(u)
            self._send_json(u.to_dict() if hasattr(u, "to_dict") else u.__dict__, 201)

        # POST /users/<id>/deactivate or /users/<id>/deactivate_account
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("deactivate", "deactivate_account"):
            user_id = path_parts[1]
            success = db.deactivate_user(user_id)
            if success:
                self._send_json({"status": "deactivated", "user_id": user_id, "is_active": False, "is_deactivated": True}, 200)
            else:
                self._send_error("User not found", 404)

        # POST /users/<id>/reactivate or /users/<id>/reactivate_account
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("reactivate", "reactivate_account"):
            user_id = path_parts[1]
            success = db.reactivate_user(user_id)
            if success:
                self._send_json({"status": "reactivated", "user_id": user_id, "is_active": True, "is_deactivated": False}, 200)
            else:
                self._send_error("User not found", 404)

        # POST /users/<id>/visibility or /users/<id>/privacy
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("visibility", "privacy", "privacy_controls", "privacy_settings"):
            user_id = path_parts[1]
            vis = body.get("visibility") or body.get("profile_visibility")
            dm_priv = body.get("dm_privacy") or body.get("allow_dms_from") or body.get("direct_message_privacy")
            is_disc = body.get("is_publicly_discoverable")
            is_act = body.get("is_active")
            if path_parts[-1] == "visibility" and not vis:
                vis = body.get("setting")
            if not vis and not dm_priv and is_disc is None and is_act is None:
                return self._send_error("visibility or privacy settings required", 400)
            try:
                user = db.update_user_profile(
                    user_id,
                    visibility=vis,
                    dm_privacy=dm_priv,
                    is_publicly_discoverable=is_disc,
                    is_active=is_act
                )
                if user:
                    self._send_json({
                        "status": "updated",
                        "user_id": user_id,
                        "visibility": user.visibility,
                        "profile_visibility": user.visibility,
                        "dm_privacy": user.dm_privacy,
                        "allow_dms_from": user.dm_privacy,
                        "direct_message_privacy": user.dm_privacy,
                        "is_active": user.is_active,
                        "is_deactivated": user.is_deactivated,
                        "is_publicly_discoverable": user.is_publicly_discoverable
                    }, 200)
                else:
                    self._send_error("User not found", 404)
            except ValueError as e:
                self._send_error(str(e), 400)

        # POST /users/<id>/dm_privacy
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("dm_privacy", "direct_message_privacy", "allow_dms_from"):
            user_id = path_parts[1]
            dm_priv = body.get("dm_privacy") or body.get("allow_dms_from") or body.get("direct_message_privacy") or body.get("setting")
            if not dm_priv:
                return self._send_error("dm_privacy setting required", 400)
            try:
                user = db.set_dm_privacy(user_id, dm_priv)
                if user:
                    self._send_json({
                        "status": "updated",
                        "user_id": user_id,
                        "dm_privacy": user.dm_privacy,
                        "allow_dms_from": user.dm_privacy,
                        "direct_message_privacy": user.dm_privacy
                    }, 200)
                else:
                    self._send_error("User not found", 404)
            except ValueError as e:
                self._send_error(str(e), 400)

        # POST /users/<id>/dossier
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("dossier", "dossiers"):
            user_id = path_parts[1]
            fmt = body.get("format", "markdown")
            dtype = body.get("dossier_type", body.get("type", "user_archive"))
            options = body.get("options", body)
            dossier = db.generate_user_dossier(user_id, format=fmt, dossier_type=dtype, options=options)
            if dossier:
                self._send_json(dossier.to_dict(), 200)
            else:
                self._send_error("User not found", 404)

        # POST /users/<id>/export/package or /users/<id>/package
        elif (len(path_parts) >= 3 and path_parts[0] == "users" and path_parts[-1] in ("package", "archive", "bundle")) or (len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] in ("export_package", "package")):
            user_id = path_parts[1]
            fmt = body.get("format", "zip")
            pkg = db.create_export_package(user_id, format=fmt, options=body)
            if pkg:
                self._send_json(pkg.to_dict(), 200)
            else:
                self._send_error("User not found", 404)

        # POST /users/<id>/export or /users/<id>/export_data or /users/<id>/data_export
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("export", "export_data", "data_export", "download_data"):
            user_id = path_parts[1]
            export = db.export_user_data(user_id)
            if export:
                self._send_json(export, 200)
            else:
                self._send_error("User not found", 404)

        # POST /users/<id>/accessibility or /users/<id>/accessibility_settings
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("accessibility", "accessibility_settings", "accessibility-settings"):
            user_id = path_parts[1]
            body["user_id"] = user_id
            settings = db.set_accessibility_settings(body)
            self._send_json(settings.to_dict() if hasattr(settings, "to_dict") else settings.__dict__, 200)

        # POST /users/<id>/content_filtering or /users/<id>/filter_preferences
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("content_filtering", "content_filters", "filter_preferences", "filtering_preferences", "content_filtering_preferences", "content-filtering"):
            user_id = path_parts[1]
            body["user_id"] = user_id
            prefs = db.set_content_filter_preferences(body)
            self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)

        # POST /users/<id>/mute_keywords
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("mute_keywords", "muted_keywords", "mute-keywords"):
            user_id = path_parts[1]
            kw = body.get("keyword") or body.get("keywords") or body.get("mute_keyword")
            if isinstance(kw, list):
                for k in kw:
                    db.add_mute_keyword(user_id, str(k))
                prefs = db.get_content_filter_preferences(user_id)
            elif kw:
                prefs = db.add_mute_keyword(user_id, str(kw))
            else:
                prefs = db.get_content_filter_preferences(user_id)
            self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)

        # POST /users/<id>/content_warnings
        elif len(path_parts) >= 2 and path_parts[0] == "users" and path_parts[-1] in ("content_warnings", "content_warning_tags", "content-warnings", "cw_tags"):
            user_id = path_parts[1]
            tag = body.get("tag") or body.get("tags") or body.get("content_warning") or body.get("warning")
            if isinstance(tag, list):
                for t in tag:
                    db.add_content_warning_tag(user_id, str(t))
                prefs = db.get_content_filter_preferences(user_id)
            elif tag:
                prefs = db.add_content_warning_tag(user_id, str(tag))
            else:
                prefs = db.get_content_filter_preferences(user_id)
            self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)

        # POST /users/<id>/profile or /users/<id>/update or /users/<id> or /profiles/<id>
        elif (len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] in ("profile", "update", "edit")) or \
             (len(path_parts) == 2 and path_parts[0] in ("users", "profiles")):
            return self._handle_profile_update(path_parts[1], body)

        # POST /connections
        elif parsed.path == "/connections":
            follower = body.get("follower_id")
            followed = body.get("followed_id")
            if not follower or not followed:
                return self._send_error("follower_id and followed_id required")
            db.create_connection(follower, followed)
            self._send_json({"status": "connected"}, 201)

        # POST /communities
        elif parsed.path == "/communities":
            name = body.get("name")
            creator_id = body.get("creator_id")
            if not name or not creator_id:
                return self._send_error("name and creator_id required")
            cid = body.get("id", str(uuid.uuid4()))
            desc = body.get("description", "")
            is_private = bool(body.get("is_private", False))
            creator_role = body.get("creator_role", "owner")
            comm = Community(id=cid, name=name, creator_id=creator_id, description=desc, is_private=is_private)
            db.create_community(comm, creator_role=creator_role)
            self._send_json(comm.__dict__, 201)

        # POST /communities/<id>/...
        elif len(path_parts) >= 3 and path_parts[0] == "communities":
            comm_id = path_parts[1]
            action = path_parts[2]
            comm = db.get_community(comm_id)
            if not comm:
                return self._send_error("Community not found", 404)

            if action in ("join", "members", "member") and len(path_parts) == 3:
                user_id = body.get("user_id")
                role = body.get("role", "member")
                invite_token = body.get("invite_token") or body.get("token")
                if not user_id:
                    return self._send_error("user_id required")
                if db.is_user_banned(comm_id, user_id):
                    return self._send_error("User is banned from this community", 403)
                success = db.join_community(comm_id, user_id, role=role, invite_token=invite_token)
                if success:
                    status_code = 201 if action in ("members", "member") else 200
                    self._send_json({"status": "joined", "community_id": comm_id, "user_id": user_id, "role": role}, status_code)
                else:
                    if comm.is_private and not invite_token:
                        req = db.create_join_request(comm_id, user_id)
                        self._send_json({"status": "join_request_created", "request_created": True, "join_request": req.to_dict() if hasattr(req, "to_dict") else req.__dict__}, 202)
                    else:
                        self._send_error("Could not join community", 400)

            elif action == "leave":
                user_id = body.get("user_id")
                if not user_id:
                    return self._send_error("user_id required")
                db.leave_community(comm_id, user_id)
                self._send_json({"status": "left", "community_id": comm_id, "user_id": user_id}, 200)

            elif action in ("role", "roles") or (action in ("members", "member") and len(path_parts) >= 4 and (len(path_parts) == 4 or path_parts[4] in ("role", "roles"))):
                user_id = body.get("user_id") or (path_parts[3] if len(path_parts) >= 4 else None)
                new_role = body.get("role") or body.get("new_role")
                actor_id = body.get("actor_id") or body.get("admin_id") or body.get("owner_id")
                if not user_id or not new_role:
                    return self._send_error("user_id and role required")
                try:
                    success = db.update_member_role(comm_id, user_id, new_role, actor_id=actor_id)
                    if success:
                        self._send_json({"status": "role_updated", "community_id": comm_id, "user_id": user_id, "role": new_role}, 200)
                    else:
                        self._send_error("Member not found in community", 404)
                except PermissionError as e:
                    return self._send_error(str(e), 403)
                except ValueError as e:
                    return self._send_error(str(e), 400)

            elif action in ("transfer_ownership", "transfer"):
                curr_owner = body.get("current_owner_id") or body.get("owner_id") or body.get("actor_id")
                new_owner = body.get("new_owner_id") or body.get("user_id")
                if not curr_owner or not new_owner:
                    return self._send_error("current_owner_id and new_owner_id required")
                try:
                    success = db.transfer_community_ownership(comm_id, curr_owner, new_owner)
                    if success:
                        self._send_json({"status": "ownership_transferred", "community_id": comm_id, "new_owner_id": new_owner}, 200)
                    else:
                        self._send_error("Failed to transfer ownership", 400)
                except PermissionError as e:
                    return self._send_error(str(e), 403)
                except ValueError as e:
                    return self._send_error(str(e), 400)

            elif action in ("join_requests", "request_join", "join_request"):
                if len(path_parts) >= 5 and path_parts[4] in ("approve", "reject"):
                    req_id = path_parts[3]
                    sub_action = path_parts[4]
                    rev_id = body.get("reviewer_id") or body.get("actor_id")
                    if sub_action == "approve":
                        role = body.get("role", "member")
                        try:
                            success = db.approve_join_request(req_id, reviewer_id=rev_id, role=role)
                            if success:
                                return self._send_json({"status": "approved", "request_id": req_id}, 200)
                            return self._send_error("Join request not found", 404)
                        except PermissionError as e:
                            return self._send_error(str(e), 403)
                    else:
                        reason = body.get("reason")
                        try:
                            success = db.reject_join_request(req_id, reviewer_id=rev_id, reason=reason)
                            if success:
                                return self._send_json({"status": "rejected", "request_id": req_id}, 200)
                            return self._send_error("Join request not found", 404)
                        except PermissionError as e:
                            return self._send_error(str(e), 403)
                else:
                    user_id = body.get("user_id")
                    message = body.get("message", "")
                    if not user_id:
                        return self._send_error("user_id required")
                    try:
                        req = db.create_join_request(comm_id, user_id, message=message)
                        self._send_json(req.to_dict() if hasattr(req, "to_dict") else req.__dict__, 201)
                    except PermissionError as e:
                        return self._send_error(str(e), 403)
                    except ValueError as e:
                        return self._send_error(str(e), 400)

            elif action in ("invites", "invite"):
                if len(path_parts) >= 4 and path_parts[3] in ("use", "join"):
                    token = body.get("token") or (path_parts[4] if len(path_parts) >= 5 else None)
                    user_id = body.get("user_id")
                    if not token or not user_id:
                        return self._send_error("token and user_id required")
                    success = db.use_invite(token, user_id)
                    if success:
                        return self._send_json({"status": "joined", "community_id": comm_id, "token": token, "user_id": user_id}, 200)
                    return self._send_error("Invalid or expired invite token", 400)
                elif len(path_parts) >= 5 and path_parts[4] in ("use", "join"):
                    token = path_parts[3]
                    user_id = body.get("user_id")
                    if not user_id:
                        return self._send_error("user_id required")
                    success = db.use_invite(token, user_id)
                    if success:
                        return self._send_json({"status": "joined", "community_id": comm_id, "token": token, "user_id": user_id}, 200)
                    return self._send_error("Invalid or expired invite token", 400)
                elif len(path_parts) >= 5 and path_parts[4] == "revoke":
                    token = path_parts[3]
                    actor_id = body.get("actor_id")
                    try:
                        success = db.revoke_invite(token, actor_id=actor_id)
                        if success:
                            return self._send_json({"status": "revoked", "token": token}, 200)
                        return self._send_error("Invite not found", 404)
                    except PermissionError as e:
                        return self._send_error(str(e), 403)
                else:
                    created_by = body.get("created_by") or body.get("user_id")
                    role = body.get("role", "member")
                    max_uses = body.get("max_uses")
                    expires_at = body.get("expires_at")
                    token = body.get("token")
                    if not created_by:
                        return self._send_error("created_by required")
                    try:
                        inv = db.create_invite(comm_id, created_by=created_by, role=role, max_uses=max_uses, expires_at=expires_at, token=token)
                        self._send_json(inv.to_dict() if hasattr(inv, "to_dict") else inv.__dict__, 201)
                    except PermissionError as e:
                        return self._send_error(str(e), 403)
                    except ValueError as e:
                        return self._send_error(str(e), 400)

            elif action == "channels":
                name = body.get("name")
                if not name:
                    return self._send_error("channel name required")
                chid = body.get("id", str(uuid.uuid4()))
                desc = body.get("description", "")
                creator_id = body.get("creator_id") or body.get("user_id")
                ch = Channel(id=chid, community_id=comm_id, name=name, description=desc)
                try:
                    db.create_channel(ch, creator_id=creator_id)
                    self._send_json(ch.__dict__, 201)
                except PermissionError as e:
                    return self._send_error(str(e), 403)

            elif action == "ban":
                user_id = body.get("user_id")
                if not user_id:
                    return self._send_error("user_id required")
                banned_by = body.get("moderator_id") or body.get("banned_by")
                reason = body.get("reason", "")
                try:
                    db.ban_user_from_community(comm_id, user_id, banned_by=banned_by, reason=reason)
                    self._send_json({"status": "banned", "community_id": comm_id, "user_id": user_id}, 200)
                except PermissionError as e:
                    return self._send_error(str(e), 403)

            elif action == "unban":
                user_id = body.get("user_id")
                actor_id = body.get("moderator_id") or body.get("actor_id")
                if not user_id:
                    return self._send_error("user_id required")
                try:
                    db.unban_user_from_community(comm_id, user_id, actor_id=actor_id)
                    self._send_json({"status": "unbanned", "community_id": comm_id, "user_id": user_id}, 200)
                except PermissionError as e:
                    return self._send_error(str(e), 403)

            else:
                self._send_error("Not found", 404)

        # POST /channels
        elif parsed.path == "/channels":
            comm_id = body.get("community_id")
            name = body.get("name")
            creator_id = body.get("creator_id") or body.get("user_id")
            if not comm_id or not name:
                return self._send_error("community_id and name required")
            comm = db.get_community(comm_id)
            if not comm:
                return self._send_error("Community not found", 404)
            chid = body.get("id", str(uuid.uuid4()))
            desc = body.get("description", "")
            ch = Channel(id=chid, community_id=comm_id, name=name, description=desc)
            try:
                db.create_channel(ch, creator_id=creator_id)
                self._send_json(ch.__dict__, 201)
            except PermissionError as e:
                return self._send_error(str(e), 403)

        # POST /channels/<id>/discussions
        elif len(path_parts) == 3 and path_parts[0] == "channels" and path_parts[2] == "discussions":
            chid = path_parts[1]
            ch = db.get_channel(chid)
            if not ch:
                return self._send_error("Channel not found", 404)
            author = body.get("author_id")
            content = body.get("content")
            if not author or not content:
                return self._send_error("author_id and content required")
            if db.is_user_banned(ch.community_id, author):
                return self._send_error("User is banned from this community", 403)
            did = body.get("id", str(uuid.uuid4()))
            d = Discussion(
                id=did, author_id=author, content=content,
                community_id=ch.community_id, channel_id=chid, parent_id=body.get("parent_id")
            )
            db.create_discussion(d)
            self._send_json(d.__dict__, 201)

        # POST /discussions
        elif parsed.path == "/discussions":
            author = body.get("author_id")
            content = body.get("content")
            parent_id = body.get("parent_id")
            community_id = body.get("community_id")
            channel_id = body.get("channel_id")
            visibility = body.get("visibility", "public")
            if not author or not content:
                return self._send_error("author_id and content required")
            if community_id and db.is_user_banned(community_id, author):
                return self._send_error("User is banned from this community", 403)
            did = body.get("id", str(uuid.uuid4()))
            tags = body.get("tags", [])
            cw = body.get("content_warnings", body.get("content_warning_tags", body.get("cw_tags", [])))
            alt = body.get("alt_text")
            transcript = body.get("audio_transcript", body.get("transcript"))
            media = body.get("media", body.get("media_attachments", []))
            course_id = body.get("course_id")
            study_group_id = body.get("study_group_id")
            d = Discussion(
                id=did, author_id=author, content=content,
                parent_id=parent_id, community_id=community_id, channel_id=channel_id,
                course_id=course_id, study_group_id=study_group_id,
                tags=tags, visibility=visibility, content_warnings=cw,
                alt_text=alt, audio_transcript=transcript, media=media
            )
            try:
                db.create_discussion(d)
            except PermissionError as e:
                return self._send_error(str(e), 403)
            self._send_json(d.to_dict() if hasattr(d, "to_dict") else d.__dict__, 201)

        # POST /discussions/<id>/media or /discussions/<id>/attachments
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("media", "attachments", "media_attachments"):
            disc_id = path_parts[1]
            disc = db.get_discussion(disc_id)
            if not disc:
                return self._send_error("Discussion not found", 404)
            media_ids = body.get("media_ids", body.get("media_id"))
            if media_ids:
                if isinstance(media_ids, str):
                    media_ids = [media_ids]
                db.attach_media_to_discussion(disc_id, media_ids)
                media_list = db.get_discussion_media(disc_id)
                self._send_json([m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in media_list], 200)
            else:
                mid = body.get("id", str(uuid.uuid4()))
                url = body.get("url", "")
                mtype = body.get("media_type") or body.get("type", "image")
                alt_text = body.get("alt_text")
                transcript = body.get("audio_transcript") or body.get("transcript")
                captions_url = body.get("captions_url")
                desc = body.get("description", "")
                uploader = body.get("uploader_id") or body.get("user_id") or disc.author_id
                cw = body.get("content_warnings") or body.get("content_warning_tags") or body.get("cw_tags") or []
                is_sens = bool(body.get("is_sensitive", False))
                m_obj = MediaAttachment(
                    id=mid, url=url, media_type=mtype, alt_text=alt_text,
                    audio_transcript=transcript, captions_url=captions_url,
                    description=desc, discussion_id=disc_id, uploader_id=uploader,
                    content_warnings=cw, is_sensitive=is_sens
                )
                created = db.create_media(m_obj)
                self._send_json(created.to_dict() if hasattr(created, "to_dict") else created.__dict__, 201)

        # POST /discussions/<id>/visibility or /discussions/<id>/privacy
        elif len(path_parts) >= 2 and path_parts[0] == "discussions" and path_parts[-1] in ("visibility", "privacy"):
            disc_id = path_parts[1]
            vis = body.get("visibility") or body.get("setting")
            if not vis:
                return self._send_error("visibility setting required", 400)
            try:
                success = db.set_discussion_visibility(disc_id, vis)
                if success:
                    disc = db.get_discussion(disc_id)
                    self._send_json({"status": "updated", "discussion_id": disc_id, "visibility": disc.visibility if disc else vis}, 200)
                else:
                    self._send_error("Discussion not found", 404)
            except ValueError as e:
                self._send_error(str(e), 400)

        # POST /users/<id>/notification_preferences or /users/<id>/notifications/preferences
        elif (len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] in ("notification_preferences", "notification-preferences", "notif_preferences")) or (len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] == "notifications" and path_parts[3] in ("preferences", "prefs")):
            user_id = path_parts[1]
            prefs = db.update_notification_preferences(user_id, **body)
            self._send_json(prefs.to_dict(), 200)

        # POST /users/<id>/push_subscriptions or /users/<id>/notifications/push_subscriptions
        elif (len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] in ("push_subscriptions", "push-subscriptions", "push_devices", "push")) or (len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] == "notifications" and path_parts[3] in ("push_subscriptions", "push-subscriptions", "push")):
            user_id = path_parts[1]
            sub = db.register_push_subscription(body, user_id=user_id)
            self._send_json(sub.to_dict(), 201)

        # POST /users/<id>/notifications/dispatch or /users/<id>/dispatch
        elif (len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] == "notifications" and path_parts[3] in ("dispatch", "send")) or (len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] in ("dispatch", "send_notification")):
            user_id = path_parts[1]
            notif = db.dispatch_notification(
                user_id=user_id,
                type=body.get("type", "announcement"),
                actor_id=body.get("actor_id", ""),
                target_id=body.get("target_id", ""),
                content=body.get("content", ""),
                title=body.get("title"),
                metadata=body.get("metadata", {}),
                weight=float(body.get("weight", 0.0))
            )
            if notif:
                self._send_json(notif.to_dict(), 201)
            else:
                self._send_json({"status": "suppressed", "user_id": user_id}, 200)

        # POST /users/<id>/notifications/read_all or read
        elif len(path_parts) >= 3 and path_parts[0] == "users" and path_parts[2] == "notifications":
            user_id = path_parts[1]
            action = path_parts[3] if len(path_parts) > 3 else "read_all"
            if action in ("read_all", "readall"):
                updated_count = db.mark_all_notifications_as_read(user_id)
                self._send_json({"status": "all_read", "user_id": user_id, "updated_count": updated_count}, 200)
            else:
                updated_count = db.mark_all_notifications_as_read(user_id)
                self._send_json({"status": "all_read", "user_id": user_id, "updated_count": updated_count}, 200)

        # POST /notifications/dispatch
        elif len(path_parts) == 2 and path_parts[0] == "notifications" and path_parts[1] in ("dispatch", "send"):
            user_id = body.get("user_id")
            if not user_id:
                return self._send_error("user_id required", 400)
            notif = db.dispatch_notification(
                user_id=user_id,
                type=body.get("type", "announcement"),
                actor_id=body.get("actor_id", ""),
                target_id=body.get("target_id", ""),
                content=body.get("content", ""),
                title=body.get("title"),
                metadata=body.get("metadata", {}),
                weight=float(body.get("weight", 0.0))
            )
            if notif:
                self._send_json(notif.to_dict(), 201)
            else:
                self._send_json({"status": "suppressed", "user_id": user_id}, 200)

        # POST /notifications/preferences
        elif len(path_parts) == 2 and path_parts[0] == "notifications" and path_parts[1] in ("preferences", "prefs"):
            user_id = body.get("user_id")
            if not user_id:
                return self._send_error("user_id required", 400)
            prefs = db.update_notification_preferences(user_id, **body)
            self._send_json(prefs.to_dict(), 200)

        # POST /push_subscriptions or /push_subscriptions/register
        elif path_parts[0] in ("push_subscriptions", "push-subscriptions", "push_devices", "push-devices", "push"):
            if len(path_parts) == 1 or path_parts[1] in ("register", "create", "new"):
                sub = db.register_push_subscription(body)
                self._send_json(sub.to_dict(), 201)
            elif len(path_parts) == 3 and path_parts[2] in ("unregister", "delete", "remove", "deactivate"):
                success = db.unregister_push_subscription(path_parts[1])
                self._send_json({"status": "unregistered", "id": path_parts[1], "success": success}, 200)
            else:
                self._send_error("Not found", 404)

        # POST /notifications/<id>/read or /notifications/<user_id>/read_all
        elif len(path_parts) >= 2 and path_parts[0] == "notifications":
            target = path_parts[1]
            action = path_parts[2] if len(path_parts) > 2 else "read"
            if action in ("read_all", "readall"):
                updated_count = db.mark_all_notifications_as_read(target)
                self._send_json({"status": "all_read", "user_id": target, "updated_count": updated_count}, 200)
            else:
                success = db.mark_notification_as_read(target)
                if success:
                    self._send_json({"status": "read", "id": target}, 200)
                else:
                    self._send_error("Notification not found", 404)

        # POST /discussions/<id>/endorse
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("endorse", "endorsement", "endorsements"):
            disc_id = path_parts[1]
            actor_id = body.get("actor_id") or body.get("user_id") or body.get("endorser_id")
            weight = body.get("weight")
            domain = body.get("domain")
            val_cat = body.get("value_category") or body.get("category")
            comment = body.get("comment")
            success = db.endorse_discussion(disc_id, actor_id=actor_id, weight=weight, domain=domain, value_category=val_cat, comment=comment)
            if success:
                disc = db.get_discussion(disc_id)
                self._send_json(disc.to_dict() if hasattr(disc, "to_dict") else (disc.__dict__ if disc else {"status": "endorsed", "id": disc_id}), 200)
            else:
                self._send_error("Discussion not found", 404)

        # POST /discussions/<id>/replies
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("replies", "reply"):
            parent_id = path_parts[1]
            author = body.get("author_id")
            content = body.get("content")
            if not author or not content:
                return self._send_error("author_id and content required")
            parent = db.get_discussion(parent_id)
            if not parent:
                return self._send_error("Parent discussion not found", 404)
            if parent.community_id and db.is_user_banned(parent.community_id, author):
                return self._send_error("User is banned from this community", 403)
            did = body.get("id", str(uuid.uuid4()))
            tags = body.get("tags", [])
            cw = body.get("content_warnings", body.get("content_warning_tags", body.get("cw_tags", [])))
            alt = body.get("alt_text")
            transcript = body.get("audio_transcript", body.get("transcript"))
            media = body.get("media", body.get("media_attachments", []))
            d = Discussion(
                id=did, author_id=author, content=content,
                parent_id=parent_id, community_id=parent.community_id, channel_id=parent.channel_id,
                course_id=parent.course_id, study_group_id=parent.study_group_id,
                tags=tags, visibility=parent.visibility, content_warnings=cw,
                alt_text=alt, audio_transcript=transcript, media=media
            )
            try:
                db.create_discussion(d)
            except PermissionError as e:
                return self._send_error(str(e), 403)
            self._send_json(d.to_dict() if hasattr(d, "to_dict") else d.__dict__, 201)

        # POST /discussions/<id>/interact or /discussions/<id>/interactions
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("interact", "interactions", "interaction"):
            disc_id = path_parts[1]
            user_id = body.get("user_id") or body.get("actor_id") or body.get("author_id")
            if not user_id:
                return self._send_error("user_id required", 400)
            interaction_type = body.get("interaction_type") or body.get("type") or "view"
            metadata = body.get("metadata")
            try:
                interaction = db.interact_with_discussion(
                    disc_id, user_id=user_id, interaction_type=interaction_type, metadata=metadata
                )
                self._send_json(interaction.to_dict() if hasattr(interaction, "to_dict") else interaction.__dict__, 201)
            except ValueError as e:
                self._send_error(str(e), 400)
            except PermissionError as e:
                self._send_error(str(e), 403)

        # POST /discussions/<id>/report or /discussions/<id>/reports
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("report", "reports"):
            disc_id = path_parts[1]
            reporter_id = body.get("reporter_id") or body.get("user_id")
            reason = body.get("reason")
            details = body.get("details") or body.get("notes") or ""
            category = body.get("category", "other")
            report_id = body.get("id") or body.get("report_id")
            if not reporter_id or not reason:
                return self._send_error("reporter_id and reason required", 400)
            try:
                rep = db.report_discussion(
                    discussion_id=disc_id,
                    reporter_id=reporter_id,
                    reason=reason,
                    category=category,
                    details=details,
                    report_id=report_id
                )
                self._send_json(rep.to_dict() if hasattr(rep, "to_dict") else rep.__dict__, 201)
            except ValueError as e:
                self._send_error(str(e), 400)
            except PermissionError as e:
                self._send_error(str(e), 403)

        # POST /discussions/<id>/moderate or /discussions/<id>/hide or /discussions/<id>/unhide
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("moderate", "hide", "unhide"):
            disc_id = path_parts[1]
            action = path_parts[2]
            disc = db.get_discussion(disc_id)
            if not disc:
                return self._send_error("Discussion not found", 404)
            actor_id = body.get("moderator_id") or body.get("actor_id") or body.get("user_id")
            reason = body.get("reason", "")
            notes = body.get("notes", "")
            if action == "unhide" or body.get("action") in ("unhide", "restore", "approve"):
                mod_action = body.get("action", "unhide" if action == "unhide" else "approve")
                db.moderate_discussion(disc_id, moderator_id=actor_id, action=mod_action, reason=reason, notes=notes)
                updated = db.get_discussion(disc_id)
                self._send_json(updated.to_dict() if (updated and hasattr(updated, "to_dict")) else (updated.__dict__ if updated else {"status": "unhidden", "id": disc_id}), 200)
            else:
                mod_action = body.get("action", "hide" if action == "hide" else "moderate")
                db.moderate_discussion(disc_id, moderator_id=actor_id, action=mod_action, reason=reason, notes=notes)
                updated = db.get_discussion(disc_id)
                self._send_json(updated.to_dict() if (updated and hasattr(updated, "to_dict")) else (updated.__dict__ if updated else {"status": "hidden", "id": disc_id}), 200)

        # POST /discussions/<id>/appeal or /discussions/<id>/appeals
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("appeal", "appeals"):
            disc_id = path_parts[1]
            appellant_id = body.get("appellant_id") or body.get("user_id")
            reason = body.get("reason")
            notes = body.get("notes", "")
            report_id = body.get("report_id")
            appeal_id = body.get("id") or body.get("appeal_id")
            if not appellant_id or not reason:
                return self._send_error("appellant_id and reason required", 400)
            try:
                appeal = db.appeal_discussion(
                    discussion_id=disc_id,
                    appellant_id=appellant_id,
                    reason=reason,
                    notes=notes,
                    report_id=report_id,
                    appeal_id=appeal_id
                )
                self._send_json(appeal.to_dict() if hasattr(appeal, "to_dict") else appeal.__dict__, 201)
            except ValueError as e:
                self._send_error(str(e), 400)
            except PermissionError as e:
                self._send_error(str(e), 403)

        # POST /discussions/<id>/remove or /discussions/<id>/delete
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("remove", "delete"):
            disc_id = path_parts[1]
            actor_id = body.get("actor_id") or body.get("deleted_by") or body.get("user_id")
            reason = body.get("reason") or body.get("removal_reason", "")
            hard_delete = bool(body.get("hard_delete", False))
            success = db.remove_discussion(disc_id, actor_id=actor_id, reason=reason, hard_delete=hard_delete)
            if success:
                self._send_json({"status": "removed", "id": disc_id, "discussion_id": disc_id, "success": True}, 200)
            else:
                self._send_error("Discussion not found", 404)

        # POST /discussions/<id>/restore or /discussions/<id>/unremove
        elif len(path_parts) == 3 and path_parts[0] == "discussions" and path_parts[2] in ("restore", "unremove"):
            disc_id = path_parts[1]
            actor_id = body.get("actor_id") or body.get("restored_by") or body.get("user_id")
            reason = body.get("reason", "")
            success = db.restore_discussion(disc_id, actor_id=actor_id, reason=reason)
            if success:
                self._send_json({"status": "restored", "id": disc_id, "discussion_id": disc_id, "success": True}, 200)
            else:
                self._send_error("Discussion not found", 404)

        # POST /endorsements or /endorse
        elif parsed.path in ("/endorsements", "/endorse"):
            target_type = body.get("target_type") or body.get("type", "discussion")
            target_id = body.get("target_id") or body.get("discussion_id") or body.get("resource_id") or body.get("id")
            if not target_id:
                return self._send_error("target_id or discussion_id required")
            actor_id = body.get("actor_id") or body.get("user_id") or body.get("endorser_id")
            weight = body.get("weight")
            domain = body.get("domain")
            val_cat = body.get("value_category") or body.get("category")
            comment = body.get("comment")

            if target_type in ("resource", "course_resource") or body.get("resource_id"):
                success = db.endorse_resource(target_id, actor_id=actor_id, weight=weight, domain=domain, value_category=val_cat, comment=comment)
                if success:
                    res = db.get_course_resource(target_id)
                    self._send_json(res.to_dict() if res else {"status": "endorsed", "resource_id": target_id}, 200)
                else:
                    self._send_error("Resource not found", 404)
            else:
                success = db.endorse_discussion(target_id, actor_id=actor_id, weight=weight, domain=domain, value_category=val_cat, comment=comment)
                if success:
                    disc = db.get_discussion(target_id)
                    self._send_json(disc.to_dict() if hasattr(disc, "to_dict") else (disc.__dict__ if disc else {"status": "endorsed", "id": target_id}), 200)
                else:
                    self._send_error("Discussion not found", 404)

        # POST /reports or /moderation/reports
        elif parsed.path in ("/reports", "/moderation/reports"):
            reporter_id = body.get("reporter_id") or body.get("user_id")
            target_type = body.get("target_type", "discussion")
            target_id = body.get("target_id") or body.get("discussion_id")
            reason = body.get("reason")
            details = body.get("details", "")
            category = body.get("category", "other")
            report_id = body.get("id") or body.get("report_id")
            if not reporter_id or not target_type or not target_id or not reason:
                return self._send_error("reporter_id, target_type, target_id, and reason required")
            report = db.report_content(
                reporter_id=reporter_id,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                category=category,
                details=details,
                report_id=report_id
            )
            self._send_json(report.to_dict() if hasattr(report, "to_dict") else report.__dict__, 201)

        # POST /reports/<id>/resolve or /moderation/reports/<id>/resolve
        elif (len(path_parts) == 3 and path_parts[0] == "reports" and path_parts[2] in ("resolve", "action")) or \
             (len(path_parts) == 4 and path_parts[0] == "moderation" and path_parts[1] == "reports" and path_parts[3] in ("resolve", "action")):
            report_id = path_parts[1] if path_parts[0] == "reports" else path_parts[2]
            report = db.get_moderation_report(report_id)
            if not report:
                return self._send_error("Report not found", 404)
            status = body.get("status", "resolved")
            action_taken = body.get("action_taken") or body.get("action")
            resolved_by = body.get("resolved_by") or body.get("moderator_id") or body.get("user_id")
            notes = body.get("notes", "")
            db.resolve_moderation_report(report_id, status=status, action_taken=action_taken, resolved_by=resolved_by, notes=notes)
            self._send_json({"status": status, "report_id": report_id}, 200)

        # POST /appeals or /moderation/appeals
        elif parsed.path in ("/appeals", "/moderation/appeals"):
            appellant_id = body.get("appellant_id") or body.get("user_id")
            target_type = body.get("target_type", "discussion")
            target_id = body.get("target_id") or body.get("discussion_id")
            reason = body.get("reason") or body.get("appeal_reason")
            report_id = body.get("report_id")
            notes = body.get("notes", "")
            appeal_id = body.get("id") or body.get("appeal_id")
            if not appellant_id or not target_id or not reason:
                return self._send_error("appellant_id, target_id, and reason required")
            appeal = db.appeal_content(
                target_type=target_type,
                target_id=target_id,
                appellant_id=appellant_id,
                reason=reason,
                notes=notes,
                report_id=report_id,
                appeal_id=appeal_id
            )
            self._send_json(appeal.to_dict() if hasattr(appeal, "to_dict") else appeal.__dict__, 201)

        # POST /appeals/<id>/review or /moderation/appeals/<id>/review or /appeals/<id>/resolve or /moderation/appeals/<id>/resolve
        elif (len(path_parts) == 3 and path_parts[0] == "appeals" and path_parts[2] in ("review", "resolve", "decision")) or \
             (len(path_parts) == 4 and path_parts[0] == "moderation" and path_parts[1] == "appeals" and path_parts[3] in ("review", "resolve", "decision")):
            appeal_id = path_parts[1] if path_parts[0] == "appeals" else path_parts[2]
            appeal = db.get_moderation_appeal(appeal_id)
            if not appeal:
                return self._send_error("Appeal not found", 404)
            reviewer_id = body.get("reviewer_id") or body.get("moderator_id") or body.get("user_id") or "moderator"
            decision = body.get("decision") or body.get("status") or "approved"
            notes = body.get("notes") or body.get("review_notes") or body.get("reason") or ""
            action_taken = body.get("action_taken") or body.get("action")
            success = db.review_content_appeal(
                appeal_id, status=decision, reviewed_by=reviewer_id, notes=notes, action_taken=action_taken
            )
            if success:
                updated_appeal = db.get_moderation_appeal(appeal_id)
                self._send_json(updated_appeal.to_dict() if hasattr(updated_appeal, "to_dict") else updated_appeal.__dict__, 200)
            else:
                self._send_error("Failed to review appeal", 400)

        # POST /messages or /direct_messages or /dms
        elif parsed.path in ("/messages", "/direct_messages", "/dms"):
            sender_id = body.get("sender_id") or body.get("author_id") or body.get("from_id")
            recipient_id = body.get("recipient_id") or body.get("to_id")
            content = body.get("content") or body.get("message")
            if not sender_id or not recipient_id or not content:
                return self._send_error("sender_id, recipient_id, and content required")
            mid = body.get("id", str(uuid.uuid4()))
            state = body.get("delivery_state") or body.get("status", "sent")
            dm = DirectMessage(id=mid, sender_id=sender_id, recipient_id=recipient_id, content=content, delivery_state=state, status=state)
            try:
                db.create_direct_message(dm)
            except PermissionError as e:
                return self._send_error(str(e), 403)
            self._send_json(dm.__dict__, 201)

        # POST /messages/<id>/... or /direct_messages/<id>/... or /dms/<id>/...
        elif len(path_parts) >= 3 and path_parts[0] in ("messages", "direct_messages", "dms"):
            msg_id = path_parts[1]
            action = path_parts[2]
            if action in ("read",):
                state = "read"
            elif action in ("deliver", "delivered"):
                state = "delivered"
            elif action in ("status", "delivery_state", "state"):
                state = body.get("delivery_state") or body.get("status", "delivered")
            else:
                state = action
            success = db.update_message_delivery_state(msg_id, state)
            if success:
                msg = db.get_direct_message(msg_id)
                self._send_json(msg.__dict__ if msg else {"status": state, "delivery_state": state, "id": msg_id}, 200)
            else:
                self._send_error("Message not found", 404)

        # POST /conversations/<user1>/<user2>/read or /users/<user1>/conversations/<user2>/read
        elif (len(path_parts) == 4 and path_parts[0] == "conversations" and path_parts[3] == "read") or \
             (len(path_parts) == 5 and path_parts[0] == "users" and path_parts[2] == "conversations" and path_parts[4] == "read"):
            if path_parts[0] == "conversations":
                u1, u2 = path_parts[1], path_parts[2]
            else:
                u1, u2 = path_parts[1], path_parts[3]
            updated = db.mark_conversation_as_read(u1, u2)
            self._send_json({"status": "read", "user_id": u1, "other_user_id": u2, "updated_count": updated}, 200)

        # POST /users/<id>/block or /users/<id>/blocks
        elif len(path_parts) in (3, 4) and path_parts[0] == "users" and path_parts[2] in ("block", "blocks"):
            blocker_id = path_parts[1]
            if len(path_parts) == 4:
                blocked_id = path_parts[3]
            else:
                blocked_id = body.get("blocked_id") or body.get("target_id") or body.get("user_id")
            if not blocked_id:
                return self._send_error("blocked_id required")
            reason = body.get("reason", "")
            db.block_user(blocker_id, blocked_id, reason=reason)
            self._send_json({"status": "blocked", "blocker_id": blocker_id, "blocked_id": blocked_id}, 200)

        # POST /users/<id>/unblock or /users/<id>/blocks/<blocked_id>/unblock
        elif (len(path_parts) == 3 and path_parts[0] == "users" and path_parts[2] == "unblock") or \
             (len(path_parts) == 5 and path_parts[0] == "users" and path_parts[2] == "blocks" and path_parts[4] == "unblock"):
            blocker_id = path_parts[1]
            if len(path_parts) == 5:
                blocked_id = path_parts[3]
            else:
                blocked_id = body.get("blocked_id") or body.get("target_id") or body.get("user_id")
            if not blocked_id:
                return self._send_error("blocked_id required")
            db.unblock_user(blocker_id, blocked_id)
            self._send_json({"status": "unblocked", "blocker_id": blocker_id, "blocked_id": blocked_id}, 200)

        # POST /blocks or /block
        elif parsed.path in ("/blocks", "/block"):
            blocker_id = body.get("blocker_id") or body.get("user_id")
            blocked_id = body.get("blocked_id") or body.get("target_id")
            if not blocker_id or not blocked_id:
                return self._send_error("blocker_id and blocked_id required")
            reason = body.get("reason", "")
            db.block_user(blocker_id, blocked_id, reason=reason)
            self._send_json({"status": "blocked", "blocker_id": blocker_id, "blocked_id": blocked_id}, 200)

        # POST /blocks/unblock or /unblock
        elif parsed.path in ("/blocks/unblock", "/unblock"):
            blocker_id = body.get("blocker_id") or body.get("user_id")
            blocked_id = body.get("blocked_id") or body.get("target_id")
            if not blocker_id or not blocked_id:
                return self._send_error("blocker_id and blocked_id required")
            db.unblock_user(blocker_id, blocked_id)
            self._send_json({"status": "unblocked", "blocker_id": blocker_id, "blocked_id": blocked_id}, 200)

        # POST /join_requests or /join_request
        elif path_parts[0] in ("join_requests", "join_request"):
            if len(path_parts) == 1:
                comm_id = body.get("community_id")
                user_id = body.get("user_id")
                message = body.get("message", "")
                if not comm_id or not user_id:
                    return self._send_error("community_id and user_id required")
                try:
                    req = db.create_join_request(comm_id, user_id, message=message)
                    self._send_json(req.to_dict() if hasattr(req, "to_dict") else req.__dict__, 201)
                except PermissionError as e:
                    return self._send_error(str(e), 403)
                except ValueError as e:
                    return self._send_error(str(e), 400)
            elif len(path_parts) == 3 and path_parts[2] == "approve":
                req_id = path_parts[1]
                reviewer_id = body.get("reviewer_id") or body.get("actor_id")
                role = body.get("role", "member")
                try:
                    success = db.approve_join_request(req_id, reviewer_id=reviewer_id, role=role)
                    if success:
                        self._send_json({"status": "approved", "request_id": req_id}, 200)
                    else:
                        self._send_error("Join request not found", 404)
                except PermissionError as e:
                    return self._send_error(str(e), 403)
                except Exception as e:
                    return self._send_error(str(e), 400)
            elif len(path_parts) == 3 and path_parts[2] == "reject":
                req_id = path_parts[1]
                reviewer_id = body.get("reviewer_id") or body.get("actor_id")
                reason = body.get("reason")
                try:
                    success = db.reject_join_request(req_id, reviewer_id=reviewer_id, reason=reason)
                    if success:
                        self._send_json({"status": "rejected", "request_id": req_id}, 200)
                    else:
                        self._send_error("Join request not found", 404)
                except PermissionError as e:
                    return self._send_error(str(e), 403)
                except Exception as e:
                    return self._send_error(str(e), 400)
            else:
                self._send_error("Not found", 404)

        # POST /invites or /invite
        elif path_parts[0] in ("invites", "invite"):
            if len(path_parts) == 1:
                comm_id = body.get("community_id")
                created_by = body.get("created_by") or body.get("user_id")
                role = body.get("role", "member")
                max_uses = body.get("max_uses")
                expires_at = body.get("expires_at")
                token = body.get("token")
                if not comm_id or not created_by:
                    return self._send_error("community_id and created_by required")
                try:
                    inv = db.create_invite(comm_id, created_by=created_by, role=role, max_uses=max_uses, expires_at=expires_at, token=token)
                    self._send_json(inv.to_dict() if hasattr(inv, "to_dict") else inv.__dict__, 201)
                except PermissionError as e:
                    return self._send_error(str(e), 403)
                except ValueError as e:
                    return self._send_error(str(e), 400)
            elif len(path_parts) == 2 and path_parts[1] == "use":
                token = body.get("token")
                user_id = body.get("user_id")
                if not token or not user_id:
                    return self._send_error("token and user_id required")
                success = db.use_invite(token, user_id)
                if success:
                    self._send_json({"status": "joined", "token": token, "user_id": user_id}, 200)
                else:
                    self._send_error("Invalid or expired invite token", 400)
            elif len(path_parts) == 3 and path_parts[2] in ("use", "join"):
                token = path_parts[1]
                user_id = body.get("user_id")
                if not user_id:
                    return self._send_error("user_id required")
                success = db.use_invite(token, user_id)
                if success:
                    self._send_json({"status": "joined", "token": token, "user_id": user_id}, 200)
                else:
                    self._send_error("Invalid or expired invite token", 400)
            elif len(path_parts) == 3 and path_parts[2] == "revoke":
                token = path_parts[1]
                actor_id = body.get("actor_id")
                try:
                    success = db.revoke_invite(token, actor_id=actor_id)
                    if success:
                        self._send_json({"status": "revoked", "token": token}, 200)
                    else:
                        self._send_error("Invite not found", 404)
                except PermissionError as e:
                    return self._send_error(str(e), 403)
            else:
                self._send_error("Not found", 404)

        # POST /feed or /feed/<user_id> or /users/<user_id>/feed
        elif parsed.path.startswith("/feed") or (len(path_parts) >= 3 and path_parts[0] == "users" and path_parts[2] == "feed"):
            user_id = body.get("user_id") or (path_parts[1] if len(path_parts) >= 2 else None)
            if not user_id:
                return self._send_error("user_id required")
            
            mode = body.get("mode") or body.get("type") or (path_parts[2] if len(path_parts) >= 3 and path_parts[0] == "feed" else "chronological")
            comm_id = body.get("community_id") or body.get("community")
            channel_id = body.get("channel_id") or body.get("channel")
            interests = body.get("interests") or body.get("topic_interests")
            if isinstance(interests, str):
                interests = [i.strip() for i in interests.split(",") if i.strip()]
            limit = body.get("limit")
            offset = body.get("offset")
            inc_hidden = bool(body.get("include_hidden", False))

            feed = db.get_feed(
                user_id=user_id,
                mode=mode,
                community_id=comm_id,
                channel_id=channel_id,
                interests=interests,
                limit=limit,
                offset=offset,
                include_hidden=inc_hidden
            )
            self._send_json([item.to_dict() if hasattr(item, "to_dict") else item.__dict__ for item in feed], 200)

        # POST /courses or /academic_spaces...
        elif path_parts[0] in ("courses", "academic_spaces", "course_spaces", "academic"):
            course_sub_parts = path_parts[1:] if path_parts[0] != "academic" else (path_parts[2:] if len(path_parts) >= 2 and path_parts[1] == "courses" else path_parts[1:])
            if len(course_sub_parts) == 0:
                code = body.get("code") or body.get("course_code")
                title = body.get("title") or body.get("name")
                if not code or not title:
                    return self._send_error("code and title required")
                cid = body.get("id", str(uuid.uuid4()))
                inst = body.get("institution") or body.get("university") or body.get("school", "")
                dept = body.get("department", "")
                term = body.get("term") or body.get("semester", "")
                desc = body.get("description", "")
                instructor = body.get("instructor", "")
                creator_id = body.get("creator_id") or body.get("created_by", "")
                course = Course(
                    id=cid, code=code, title=title, department=dept, institution=inst,
                    term=term, description=desc, instructor=instructor, creator_id=creator_id
                )
                db.create_course(course)
                self._send_json(course.to_dict() if hasattr(course, "to_dict") else course.__dict__, 201)
            elif len(course_sub_parts) == 1:
                # Update or get course
                course = db.update_course(course_sub_parts[0], **body)
                if course:
                    self._send_json(course.to_dict() if hasattr(course, "to_dict") else course.__dict__, 200)
                else:
                    self._send_error("Course not found", 404)
            elif len(course_sub_parts) == 2:
                cid = course_sub_parts[0]
                action = course_sub_parts[1]
                if action in ("enroll", "enrollments", "join"):
                    uid = body.get("user_id")
                    if not uid:
                        return self._send_error("user_id required")
                    role = body.get("role", "student")
                    is_ver = body.get("is_verified", body.get("verified"))
                    inst = body.get("institution")
                    enr = db.enroll_in_course(cid, uid, role=role, is_verified=is_ver, institution=inst)
                    self._send_json(enr.to_dict() if hasattr(enr, "to_dict") else enr.__dict__, 201)
                elif action in ("unenroll", "leave"):
                    uid = body.get("user_id")
                    if not uid:
                        return self._send_error("user_id required")
                    success = db.unenroll_from_course(cid, uid)
                    self._send_json({"status": "unenrolled", "course_id": cid, "user_id": uid, "success": success}, 200)
                elif action in ("discussions", "posts"):
                    author = body.get("author_id")
                    content = body.get("content")
                    if not author or not content:
                        return self._send_error("author_id and content required")
                    did = body.get("id", str(uuid.uuid4()))
                    d = Discussion(
                        id=did, author_id=author, content=content,
                        course_id=cid, parent_id=body.get("parent_id"),
                        tags=body.get("tags", []), visibility=body.get("visibility", "public")
                    )
                    db.create_course_discussion(d, course_id=cid)
                    self._send_json(d.to_dict() if hasattr(d, "to_dict") else d.__dict__, 201)
                elif action in ("resources", "materials"):
                    title = body.get("title")
                    uploader = body.get("uploader_id") or body.get("author_id") or body.get("user_id")
                    if not title or not uploader:
                        return self._send_error("title and uploader_id required")
                    rid = body.get("id", str(uuid.uuid4()))
                    res = CourseResource(
                        id=rid, course_id=cid, uploader_id=uploader, title=title,
                        description=body.get("description", ""),
                        resource_type=body.get("resource_type") or body.get("type", "syllabus"),
                        url=body.get("url") or body.get("file_url", ""),
                        content=body.get("content", ""),
                        study_group_id=body.get("study_group_id"),
                        tags=body.get("tags", [])
                    )
                    db.create_course_resource(res)
                    self._send_json(res.to_dict() if hasattr(res, "to_dict") else res.__dict__, 201)
                elif action in ("syllabus",):
                    uploader = body.get("uploader_id") or body.get("author_id") or body.get("user_id", "")
                    rid = body.get("id", str(uuid.uuid4()))
                    res = CourseResource(
                        id=rid, course_id=cid, uploader_id=uploader,
                        title=body.get("title", "Course Syllabus"),
                        description=body.get("description", ""),
                        resource_type="syllabus",
                        url=body.get("url") or body.get("file_url", ""),
                        content=body.get("content", ""),
                        tags=body.get("tags", [])
                    )
                    db.create_course_resource(res)
                    self._send_json(res.to_dict() if hasattr(res, "to_dict") else res.__dict__, 201)
                elif action in ("study_groups", "study-groups"):
                    name = body.get("name")
                    creator = body.get("creator_id") or body.get("user_id")
                    if not name or not creator:
                        return self._send_error("name and creator_id required")
                    sgid = body.get("id", str(uuid.uuid4()))
                    sg = StudyGroup(
                        id=sgid, name=name, creator_id=creator, course_id=cid,
                        description=body.get("description", ""),
                        institution=body.get("institution", ""),
                        is_private=bool(body.get("is_private", False)),
                        verified_only=bool(body.get("verified_only", True)),
                        max_members=body.get("max_members"),
                        meeting_schedule=body.get("meeting_schedule", "")
                    )
                    db.create_study_group(sg)
                    self._send_json(sg.to_dict() if hasattr(sg, "to_dict") else sg.__dict__, 201)
                elif action in ("verify_classmate", "verify"):
                    uid = body.get("user_id")
                    if not uid:
                        return self._send_error("user_id required")
                    is_ver = bool(body.get("is_verified", body.get("verified", True)))
                    db.verify_classmate(cid, uid, is_verified=is_ver)
                    self._send_json({"status": "verified", "course_id": cid, "user_id": uid, "is_verified": is_ver, "verified": is_ver}, 200)
                else:
                    self._send_error("Not found", 404)
            else:
                self._send_error("Not found", 404)

        # POST /resources or /course_resources...
        elif path_parts[0] in ("resources", "course_resources"):
            if len(path_parts) == 1:
                cid = body.get("course_id", "")
                title = body.get("title")
                uploader = body.get("uploader_id") or body.get("author_id") or body.get("user_id")
                if not title or not uploader:
                    return self._send_error("title and uploader_id required")
                rid = body.get("id", str(uuid.uuid4()))
                res = CourseResource(
                    id=rid, course_id=cid, uploader_id=uploader, title=title,
                    description=body.get("description", ""),
                    resource_type=body.get("resource_type") or body.get("type", "syllabus"),
                    url=body.get("url") or body.get("file_url", ""),
                    content=body.get("content", ""),
                    study_group_id=body.get("study_group_id"),
                    tags=body.get("tags", [])
                )
                db.create_course_resource(res)
                self._send_json(res.to_dict() if hasattr(res, "to_dict") else res.__dict__, 201)
            elif len(path_parts) == 3 and path_parts[2] in ("endorse", "endorsement", "endorsements", "upvote"):
                rid = path_parts[1]
                actor = body.get("actor_id") or body.get("user_id")
                weight = body.get("weight")
                domain = body.get("domain")
                val_cat = body.get("value_category") or body.get("category")
                comment = body.get("comment")
                success = db.endorse_resource(rid, actor_id=actor, weight=weight, domain=domain, value_category=val_cat, comment=comment)
                if success:
                    res = db.get_course_resource(rid)
                    self._send_json(res.to_dict() if res else {"status": "endorsed", "resource_id": rid}, 200)
                else:
                    self._send_error("Resource not found", 404)
            else:
                self._send_error("Not found", 404)

        # POST /study_groups or /study-groups or /academic_groups...
        elif path_parts[0] in ("study_groups", "study-groups", "academic_groups"):
            if len(path_parts) == 1:
                name = body.get("name")
                creator = body.get("creator_id") or body.get("created_by") or body.get("user_id")
                if not name or not creator:
                    return self._send_error("name and creator_id required")
                sgid = body.get("id", str(uuid.uuid4()))
                sg = StudyGroup(
                    id=sgid, name=name, creator_id=creator, course_id=body.get("course_id"),
                    description=body.get("description", ""),
                    institution=body.get("institution", ""),
                    is_private=bool(body.get("is_private", False)),
                    verified_only=bool(body.get("verified_only", True)),
                    max_members=body.get("max_members"),
                    meeting_schedule=body.get("meeting_schedule", "")
                )
                db.create_study_group(sg)
                self._send_json(sg.to_dict() if hasattr(sg, "to_dict") else sg.__dict__, 201)
            elif len(path_parts) == 3:
                sg_id = path_parts[1]
                action = path_parts[2]
                if action == "join":
                    uid = body.get("user_id")
                    if not uid:
                        return self._send_error("user_id required")
                    role = body.get("role", "member")
                    try:
                        joined = db.join_study_group(sg_id, uid, role=role)
                        if joined:
                            self._send_json({"status": "joined", "study_group_id": sg_id, "user_id": uid}, 200)
                        else:
                            self._send_error("Failed to join study group (capacity reached or not found)", 400)
                    except PermissionError as e:
                        return self._send_error(str(e), 403)
                    except ValueError as e:
                        return self._send_error(str(e), 400)
                elif action == "leave":
                    uid = body.get("user_id")
                    if not uid:
                        return self._send_error("user_id required")
                    success = db.leave_study_group(sg_id, uid)
                    self._send_json({"status": "left", "study_group_id": sg_id, "user_id": uid, "success": success}, 200)
                elif action in ("discussions", "posts"):
                    author = body.get("author_id")
                    content = body.get("content")
                    if not author or not content:
                        return self._send_error("author_id and content required")
                    did = body.get("id", str(uuid.uuid4()))
                    d = Discussion(
                        id=did, author_id=author, content=content,
                        study_group_id=sg_id, parent_id=body.get("parent_id"),
                        tags=body.get("tags", []), visibility=body.get("visibility", "public")
                    )
                    db.create_discussion(d)
                    self._send_json(d.to_dict() if hasattr(d, "to_dict") else d.__dict__, 201)
                elif action in ("resources", "materials"):
                    title = body.get("title")
                    uploader = body.get("uploader_id") or body.get("user_id")
                    if not title or not uploader:
                        return self._send_error("title and uploader_id required")
                    rid = body.get("id", str(uuid.uuid4()))
                    res = CourseResource(
                        id=rid, course_id=body.get("course_id", ""), uploader_id=uploader, title=title,
                        description=body.get("description", ""),
                        resource_type=body.get("resource_type") or body.get("type", "notes"),
                        url=body.get("url") or body.get("file_url", ""),
                        content=body.get("content", ""),
                        study_group_id=sg_id,
                        tags=body.get("tags", [])
                    )
                    db.create_course_resource(res)
                    self._send_json(res.to_dict() if hasattr(res, "to_dict") else res.__dict__, 201)
                elif action == "members":
                    uid = body.get("user_id")
                    role = body.get("role", "member")
                    if not uid:
                        return self._send_error("user_id required")
                    try:
                        joined = db.join_study_group(sg_id, uid, role=role)
                        self._send_json({"status": "member_added", "study_group_id": sg_id, "user_id": uid}, 201)
                    except PermissionError as e:
                        return self._send_error(str(e), 403)
                else:
                    self._send_error("Not found", 404)
            else:
                self._send_error("Not found", 404)

        # POST /accessibility or /accessibility_settings
        elif path_parts[0] in ("accessibility", "accessibility_settings", "accessibility-settings"):
            user_id = body.get("user_id") or (path_parts[1] if len(path_parts) >= 2 else None)
            if not user_id:
                return self._send_error("user_id required", 400)
            body["user_id"] = user_id
            settings = db.set_accessibility_settings(body)
            self._send_json(settings.to_dict() if hasattr(settings, "to_dict") else settings.__dict__, 200)

        # POST /content_filtering or /content_filters or /filter_preferences
        elif path_parts[0] in ("content_filtering", "content_filters", "filter_preferences", "filtering_preferences", "content_filtering_preferences", "content-filtering"):
            user_id = body.get("user_id") or (path_parts[1] if len(path_parts) >= 2 else None)
            if not user_id:
                return self._send_error("user_id required", 400)
            body["user_id"] = user_id
            prefs = db.set_content_filter_preferences(body)
            self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)

        # POST /media or /media_attachments or /media_metadata
        elif path_parts[0] in ("media", "media_attachments", "media_metadata"):
            if len(path_parts) == 1:
                mid = body.get("id", str(uuid.uuid4()))
                url = body.get("url", "")
                mtype = body.get("media_type") or body.get("type", "image")
                alt_text = body.get("alt_text")
                transcript = body.get("audio_transcript") or body.get("transcript")
                captions_url = body.get("captions_url")
                desc = body.get("description", "")
                disc_id = body.get("discussion_id")
                uploader = body.get("uploader_id") or body.get("user_id") or body.get("author_id")
                cw = body.get("content_warnings") or body.get("content_warning_tags") or body.get("cw_tags") or []
                is_sens = bool(body.get("is_sensitive", False))
                m_obj = MediaAttachment(
                    id=mid, url=url, media_type=mtype, alt_text=alt_text,
                    audio_transcript=transcript, captions_url=captions_url,
                    description=desc, discussion_id=disc_id, uploader_id=uploader,
                    content_warnings=cw, is_sensitive=is_sens
                )
                created = db.create_media(m_obj)
                self._send_json(created.to_dict() if hasattr(created, "to_dict") else created.__dict__, 201)
            elif len(path_parts) == 2 or (len(path_parts) == 3 and path_parts[2] in ("accessibility", "metadata", "update")):
                mid = path_parts[1]
                updated = db.update_media_accessibility(mid, **body)
                if updated:
                    self._send_json(updated.to_dict() if hasattr(updated, "to_dict") else updated.__dict__, 200)
                else:
                    self._send_error("Media not found", 404)
            else:
                self._send_error("Not found", 404)

        # POST /discussions/<id>/dossier
        elif len(path_parts) >= 2 and path_parts[0] == "discussions" and path_parts[-1] in ("dossier", "dossiers", "export"):
            disc_id = path_parts[1]
            fmt = body.get("format", "markdown")
            dossier = db.generate_discussion_dossier(disc_id, format=fmt, options=body)
            if dossier:
                self._send_json(dossier.to_dict(), 200)
            else:
                self._send_error("Discussion not found", 404)

        # POST /communities/<id>/dossier
        elif len(path_parts) >= 2 and path_parts[0] == "communities" and path_parts[-1] in ("dossier", "dossiers", "digest", "export"):
            comm_id = path_parts[1]
            fmt = body.get("format", "markdown")
            dossier = db.generate_community_dossier(comm_id, format=fmt, options=body)
            if dossier:
                self._send_json(dossier.to_dict(), 200)
            else:
                self._send_error("Community not found", 404)

        # POST /content/transform or /transform
        elif path_parts[0] in ("content", "transform") and (len(path_parts) == 1 or path_parts[-1] in ("transform", "dossier")):
            content = body.get("content", "")
            target_fmt = body.get("target_format", body.get("format", "markdown"))
            res = db.transform_content(content, target_format=target_fmt, options=body.get("options"))
            self._send_json(res, 200)

        else:
            self._send_error("Not found", 404)


    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path_parts = [p for p in parsed.path.strip('/').split('/') if p]

        if not path_parts:
            self._send_error("Not found", 404)
            return

        # DELETE /blocks/<blocker_id>/<blocked_id> or /blocklist/<blocker_id>/<blocked_id>
        if len(path_parts) == 3 and path_parts[0] in ("blocks", "blocklist"):
            blocker_id, blocked_id = path_parts[1], path_parts[2]
            success = db.unblock_user(blocker_id, blocked_id)
            self._send_json({"status": "unblocked", "blocker_id": blocker_id, "blocked_id": blocked_id, "success": success}, 200)

        # DELETE /users/<blocker_id>/blocks/<blocked_id> or /users/<blocker_id>/blocklist/<blocked_id>
        elif len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] in ("blocks", "blocklist"):
            blocker_id, blocked_id = path_parts[1], path_parts[3]
            success = db.unblock_user(blocker_id, blocked_id)
            self._send_json({"status": "unblocked", "blocker_id": blocker_id, "blocked_id": blocked_id, "success": success}, 200)

        # DELETE /invites/<token> or /communities/<id>/invites/<token>
        elif len(path_parts) == 2 and path_parts[0] in ("invites", "invite"):
            token = path_parts[1]
            success = db.revoke_invite(token)
            self._send_json({"status": "revoked", "token": token, "success": success}, 200)

        elif len(path_parts) == 4 and path_parts[0] == "communities" and path_parts[2] in ("invites", "invite"):
            token = path_parts[3]
            success = db.revoke_invite(token)
            self._send_json({"status": "revoked", "token": token, "success": success}, 200)

        # DELETE /join_requests/<id> or /communities/<id>/join_requests/<id>
        elif len(path_parts) == 2 and path_parts[0] in ("join_requests", "join_request"):
            req_id = path_parts[1]
            success = db.reject_join_request(req_id)
            self._send_json({"status": "rejected", "request_id": req_id, "success": success}, 200)

        elif len(path_parts) == 4 and path_parts[0] == "communities" and path_parts[2] in ("join_requests", "join_request"):
            req_id = path_parts[3]
            success = db.reject_join_request(req_id)
            self._send_json({"status": "rejected", "request_id": req_id, "success": success}, 200)

        # DELETE /users/<id> or /users/<id>/deactivate
        elif len(path_parts) in (2, 3) and path_parts[0] == "users":
            if len(path_parts) == 2 or path_parts[2] in ("deactivate", "delete"):
                user_id = path_parts[1]
                success = db.deactivate_user(user_id)
                if success:
                    self._send_json({"status": "deactivated", "user_id": user_id, "is_active": False}, 200)
                else:
                    self._send_error("User not found", 404)
            else:
                self._send_error("Not found", 404)

        # DELETE /courses/<id> or /courses/<id>/enrollments/<user_id>
        elif path_parts[0] in ("courses", "academic_spaces", "course_spaces"):
            if len(path_parts) == 2:
                cid = path_parts[1]
                success = db.delete_course(cid)
                self._send_json({"status": "deleted", "course_id": cid, "success": success}, 200)
            elif len(path_parts) == 4 and path_parts[2] in ("enrollments", "members", "students"):
                cid = path_parts[1]
                uid = path_parts[3]
                success = db.unenroll_from_course(cid, uid)
                self._send_json({"status": "unenrolled", "course_id": cid, "user_id": uid, "success": success}, 200)
            else:
                self._send_error("Not found", 404)

        # DELETE /resources/<id> or /course_resources/<id>
        elif path_parts[0] in ("resources", "course_resources"):
            if len(path_parts) == 2:
                rid = path_parts[1]
                success = db.delete_course_resource(rid)
                self._send_json({"status": "deleted", "resource_id": rid, "success": success}, 200)
            else:
                self._send_error("Not found", 404)

        # DELETE /study_groups/<id> or /study_groups/<id>/members/<user_id>
        elif path_parts[0] in ("study_groups", "study-groups", "academic_groups"):
            if len(path_parts) == 4 and path_parts[2] in ("members", "users"):
                sg_id = path_parts[1]
                uid = path_parts[3]
                success = db.leave_study_group(sg_id, uid)
                self._send_json({"status": "member_removed", "study_group_id": sg_id, "user_id": uid, "success": success}, 200)
            elif len(path_parts) == 2:
                sg_id = path_parts[1]
                success = db.delete_study_group(sg_id)
                self._send_json({"status": "deleted", "study_group_id": sg_id, "success": success}, 200)
            else:
                self._send_error("Not found", 404)

        # DELETE /discussions/<id>
        elif path_parts[0] == "discussions" and len(path_parts) == 2:
            disc_id = path_parts[1]
            success = db.remove_discussion(disc_id)
            if success:
                self._send_json({"status": "deleted", "discussion_id": disc_id, "success": True}, 200)
            else:
                self._send_error("Discussion not found", 404)

        # DELETE /media/<id> or /media_attachments/<id>
        elif path_parts[0] in ("media", "media_attachments", "media_metadata") and len(path_parts) == 2:
            mid = path_parts[1]
            success = db.delete_media(mid)
            self._send_json({"status": "deleted", "media_id": mid, "id": mid, "success": success}, 200)

        # DELETE /users/<id>/mute_keywords/<keyword>
        elif len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] in ("mute_keywords", "muted_keywords", "mute-keywords"):
            user_id = path_parts[1]
            kw = urllib.parse.unquote(path_parts[3])
            prefs = db.remove_mute_keyword(user_id, kw)
            self._send_json({"status": "removed", "user_id": user_id, "keyword": kw, "preferences": prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__}, 200)

        # DELETE /users/<id>/content_warnings/<tag>
        elif len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] in ("content_warnings", "content_warning_tags", "content-warnings", "cw_tags"):
            user_id = path_parts[1]
            tag = urllib.parse.unquote(path_parts[3])
            prefs = db.remove_content_warning_tag(user_id, tag)
            self._send_json({"status": "removed", "user_id": user_id, "tag": tag, "preferences": prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__}, 200)

        # DELETE /push_subscriptions/<id> or /push_devices/<id>
        elif path_parts[0] in ("push_subscriptions", "push-subscriptions", "push_devices", "push-devices", "push") and len(path_parts) == 2:
            sub_id = path_parts[1]
            success = db.unregister_push_subscription(sub_id)
            self._send_json({"status": "unregistered", "id": sub_id, "success": success}, 200)

        # DELETE /users/<user_id>/push_subscriptions/<id>
        elif len(path_parts) == 4 and path_parts[0] == "users" and path_parts[2] in ("push_subscriptions", "push-subscriptions", "push_devices", "push"):
            user_id = path_parts[1]
            sub_id = path_parts[3]
            success = db.unregister_push_subscription(sub_id, user_id=user_id)
            self._send_json({"status": "unregistered", "id": sub_id, "user_id": user_id, "success": success}, 200)

        else:
            self._send_error("Not found", 404)

    def do_PUT(self):
        self._handle_put_or_patch()

    def do_PATCH(self):
        self._handle_put_or_patch()

    def _handle_put_or_patch(self):
        parsed = urllib.parse.urlparse(self.path)
        path_parts = [p for p in parsed.path.strip('/').split('/') if p]
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            body = json.loads(post_data.decode('utf-8')) if post_data else {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return

        if not path_parts:
            self._send_error("Not found", 404)
            return

        if path_parts[0] in ("users", "profiles"):
            if len(path_parts) == 2:
                self._handle_profile_update(path_parts[1], body)
            elif len(path_parts) == 3 and path_parts[2] in ("profile", "update", "edit"):
                self._handle_profile_update(path_parts[1], body)
            elif len(path_parts) == 3 and path_parts[2] in ("visibility", "privacy", "privacy_controls", "privacy_settings"):
                vis = body.get("visibility") or body.get("profile_visibility")
                dm_priv = body.get("dm_privacy") or body.get("allow_dms_from") or body.get("direct_message_privacy")
                is_disc = body.get("is_publicly_discoverable")
                is_act = body.get("is_active")
                if path_parts[2] == "visibility" and not vis:
                    vis = body.get("setting")
                if not vis and not dm_priv and is_disc is None and is_act is None:
                    return self._send_error("visibility or privacy settings required", 400)
                try:
                    user = db.update_user_profile(
                        path_parts[1],
                        visibility=vis,
                        dm_privacy=dm_priv,
                        is_publicly_discoverable=is_disc,
                        is_active=is_act
                    )
                    if user:
                        self._send_json({
                            "status": "updated",
                            "user_id": path_parts[1],
                            "visibility": user.visibility,
                            "profile_visibility": user.visibility,
                            "dm_privacy": user.dm_privacy,
                            "allow_dms_from": user.dm_privacy,
                            "direct_message_privacy": user.dm_privacy,
                            "is_active": user.is_active,
                            "is_deactivated": user.is_deactivated,
                            "is_publicly_discoverable": user.is_publicly_discoverable
                        }, 200)
                    else:
                        self._send_error("User not found", 404)
                except ValueError as e:
                    self._send_error(str(e), 400)
            elif len(path_parts) == 3 and path_parts[2] in ("dm_privacy", "direct_message_privacy", "allow_dms_from"):
                dm_priv = body.get("dm_privacy") or body.get("allow_dms_from") or body.get("direct_message_privacy") or body.get("setting")
                if not dm_priv:
                    return self._send_error("dm_privacy setting required", 400)
                try:
                    user = db.set_dm_privacy(path_parts[1], dm_priv)
                    if user:
                        self._send_json({
                            "status": "updated",
                            "user_id": path_parts[1],
                            "dm_privacy": user.dm_privacy,
                            "allow_dms_from": user.dm_privacy,
                            "direct_message_privacy": user.dm_privacy
                        }, 200)
                    else:
                        self._send_error("User not found", 404)
                except ValueError as e:
                    self._send_error(str(e), 400)
            elif len(path_parts) == 3 and path_parts[2] in ("deactivate", "deactivate_account"):
                success = db.deactivate_user(path_parts[1])
                if success:
                    self._send_json({"status": "deactivated", "user_id": path_parts[1], "is_active": False}, 200)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("reactivate", "reactivate_account"):
                success = db.reactivate_user(path_parts[1])
                if success:
                    self._send_json({"status": "reactivated", "user_id": path_parts[1], "is_active": True}, 200)
                else:
                    self._send_error("User not found", 404)
            elif len(path_parts) == 3 and path_parts[2] in ("accessibility", "accessibility_settings", "accessibility-settings"):
                settings = db.update_accessibility_settings(path_parts[1], **body)
                self._send_json(settings.to_dict() if hasattr(settings, "to_dict") else settings.__dict__, 200)
            elif len(path_parts) == 3 and path_parts[2] in ("content_filtering", "content_filters", "filter_preferences", "filtering_preferences", "content_filtering_preferences", "content-filtering"):
                prefs = db.update_content_filter_preferences(path_parts[1], **body)
                self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)
            elif (len(path_parts) == 3 and path_parts[2] in ("notification_preferences", "notification-preferences", "notif_preferences")) or (len(path_parts) == 4 and path_parts[2] == "notifications" and path_parts[3] in ("preferences", "prefs")):
                prefs = db.update_notification_preferences(path_parts[1], **body)
                self._send_json(prefs.to_dict(), 200)
            else:
                self._send_error("Not found", 404)
        elif path_parts[0] == "discussions" and len(path_parts) == 3 and path_parts[2] in ("visibility", "privacy"):
            disc_id = path_parts[1]
            vis = body.get("visibility") or body.get("setting")
            if not vis:
                return self._send_error("visibility setting required", 400)
            try:
                success = db.set_discussion_visibility(disc_id, vis)
                if success:
                    self._send_json({"status": "updated", "discussion_id": disc_id, "visibility": vis}, 200)
                else:
                    self._send_error("Discussion not found", 404)
            except ValueError as e:
                self._send_error(str(e), 400)
        elif path_parts[0] in ("courses", "academic_spaces", "course_spaces") and len(path_parts) == 2:
            course = db.update_course(path_parts[1], **body)
            if course:
                self._send_json(course.to_dict() if hasattr(course, "to_dict") else course.__dict__, 200)
            else:
                self._send_error("Course not found", 404)
        elif path_parts[0] in ("study_groups", "study-groups", "academic_groups") and len(path_parts) == 2:
            sg = db.update_study_group(path_parts[1], **body) or db.get_study_group(path_parts[1])
            if sg:
                self._send_json(sg.to_dict() if hasattr(sg, "to_dict") else sg.__dict__, 200)
            else:
                self._send_error("Study group not found", 404)
        elif path_parts[0] in ("accessibility", "accessibility_settings", "accessibility-settings") and len(path_parts) == 2:
            settings = db.update_accessibility_settings(path_parts[1], **body)
            self._send_json(settings.to_dict() if hasattr(settings, "to_dict") else settings.__dict__, 200)
        elif path_parts[0] in ("content_filtering", "content_filters", "filter_preferences", "filtering_preferences", "content_filtering_preferences", "content-filtering") and len(path_parts) == 2:
            prefs = db.update_content_filter_preferences(path_parts[1], **body)
            self._send_json(prefs.to_dict() if hasattr(prefs, "to_dict") else prefs.__dict__, 200)
        elif path_parts[0] in ("media", "media_attachments", "media_metadata") and len(path_parts) >= 2:
            updated = db.update_media(path_parts[1], **body)
            if updated:
                self._send_json(updated.to_dict() if hasattr(updated, "to_dict") else updated.__dict__, 200)
            else:
                self._send_error("Media not found", 404)
        else:
            self._send_error("Not found", 404)

def run(server_class=HTTPServer, handler_class=SocialAPIHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting API server on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()

