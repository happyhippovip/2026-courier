import sqlite3
import json
import re
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import (
    User, Connection, Discussion, Community, CommunityMember, Channel,
    ModerationReport, ContentReport, ModerationAppeal, ContentAppeal,
    CommunityBan, Notification, UserBlock, DirectMessage, FeedItem,
    TopicSubscription, TopicTrend, CommunityJoinRequest, CommunityInvite,
    CommunityInviteToken, CommunityRole, COMMUNITY_ROLES,
    REPORT_REASON_CATEGORIES, REPORT_CATEGORIES, REPORT_REASONS,
    ReportCategory, ReportReason, ReportStatus, AppealStatus,
    Visibility, VISIBILITY_SETTINGS, UserVisibility, VisibilitySetting,
    DMPrivacy, DM_PRIVACY_SETTINGS, DirectMessagePrivacy, PrivacySettings, UserPrivacySettings,
    Course, CourseEnrollment, CourseResource, StudyGroup, StudyGroupMember,
    AcademicSpace, CourseSpace, ClassmateVerification, CourseMember,
    StudyResource, Syllabus, AcademicStudyGroup,
    MediaAttachment, Media, MediaMetadata, MediaAccessibility,
    ContentFilterPreferences, UserContentFilter, UserContentFilterPreferences, ContentFilteringPreferences,
    UserAccessibilitySettings, AccessibilitySettings, UserSettingsAccessibility,
    ContentLifecycleState, ContentStatus, ContentState, ContentLifecycleAction, ContentLifecycleEvent, ContentInteraction
)
from .feed import FeedService, FeedMode

ROLE_LEVELS: Dict[str, int] = {
    "owner": 40,
    "admin": 30,
    "moderator": 20,
    "member": 10
}


class SocialDatabase:
    def __init__(self, db_path: str = "social.db"):
        self.db_path = db_path
        # For :memory:, we must keep a single connection open
        self._memory_conn = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
        self._init_db()

    def get_connection(self):
        if self._memory_conn:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self.get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_publicly_discoverable BOOLEAN NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    bio TEXT NOT NULL DEFAULT '',
                    avatar_url TEXT,
                    school TEXT NOT NULL DEFAULT '',
                    university TEXT NOT NULL DEFAULT '',
                    class_year TEXT NOT NULL DEFAULT '',
                    interests TEXT NOT NULL DEFAULT '[]',
                    visibility TEXT NOT NULL DEFAULT 'public',
                    dm_privacy TEXT NOT NULL DEFAULT 'everyone'
                );

                CREATE TABLE IF NOT EXISTS connections (
                    follower_id TEXT NOT NULL,
                    followed_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (follower_id, followed_id)
                );

                CREATE TABLE IF NOT EXISTS communities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    creator_id TEXT NOT NULL,
                    is_private BOOLEAN NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS community_members (
                    community_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    joined_at TEXT NOT NULL,
                    PRIMARY KEY (community_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS community_join_requests (
                    id TEXT PRIMARY KEY,
                    community_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    message TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS community_invites (
                    id TEXT PRIMARY KEY,
                    community_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    created_by TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    max_uses INTEGER,
                    uses_count INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS channels (
                    id TEXT PRIMARY KEY,
                    community_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS discussions (
                    id TEXT PRIMARY KEY,
                    author_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    value_endorsements INTEGER NOT NULL DEFAULT 0,
                    parent_id TEXT,
                    community_id TEXT,
                    channel_id TEXT,
                    is_hidden BOOLEAN NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '[]',
                    visibility TEXT NOT NULL DEFAULT 'public',
                    status TEXT NOT NULL DEFAULT 'active',
                    moderation_status TEXT NOT NULL DEFAULT 'none',
                    moderated_by TEXT,
                    moderated_at TEXT,
                    moderation_action TEXT,
                    moderation_reason TEXT,
                    deleted_at TEXT,
                    deleted_by TEXT,
                    removal_reason TEXT,
                    report_count INTEGER NOT NULL DEFAULT 0,
                    last_interacted_at TEXT,
                    interaction_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS content_lifecycle_events (
                    id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL DEFAULT 'discussion',
                    target_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    previous_state TEXT,
                    new_state TEXT,
                    reason TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS content_interactions (
                    id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL DEFAULT 'discussion',
                    target_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    interaction_type TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS moderation_reports (
                    id TEXT PRIMARY KEY,
                    reporter_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'other',
                    status TEXT NOT NULL DEFAULT 'pending',
                    report_count INTEGER NOT NULL DEFAULT 1,
                    reporter_ids TEXT NOT NULL DEFAULT '[]',
                    reasons TEXT NOT NULL DEFAULT '[]',
                    details TEXT NOT NULL DEFAULT '',
                    action_taken TEXT,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS moderation_appeals (
                    id TEXT PRIMARY KEY,
                    report_id TEXT,
                    target_type TEXT NOT NULL DEFAULT '',
                    target_id TEXT NOT NULL DEFAULT '',
                    appellant_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    action_taken TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS community_bans (
                    community_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    banned_by TEXT,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (community_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    is_read BOOLEAN NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS direct_messages (
                    id TEXT PRIMARY KEY,
                    sender_id TEXT NOT NULL,
                    recipient_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    delivery_state TEXT NOT NULL DEFAULT 'sent',
                    created_at TEXT NOT NULL,
                    read_at TEXT
                );

                CREATE TABLE IF NOT EXISTS user_blocks (
                    blocker_id TEXT NOT NULL,
                    blocked_id TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (blocker_id, blocked_id)
                );

                CREATE TABLE IF NOT EXISTS topic_subscriptions (
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, topic)
                );

                CREATE TABLE IF NOT EXISTS discussion_tags (
                    discussion_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (discussion_id, tag)
                );

                CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    department TEXT NOT NULL DEFAULT '',
                    institution TEXT NOT NULL DEFAULT '',
                    term TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    instructor TEXT NOT NULL DEFAULT '',
                    creator_id TEXT NOT NULL DEFAULT '',
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS course_enrollments (
                    id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'student',
                    is_verified BOOLEAN NOT NULL DEFAULT 1,
                    institution TEXT NOT NULL DEFAULT '',
                    term TEXT NOT NULL DEFAULT '',
                    verification_source TEXT NOT NULL DEFAULT 'institution_match',
                    enrolled_at TEXT NOT NULL,
                    UNIQUE(course_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS course_resources (
                    id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    study_group_id TEXT,
                    uploader_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    resource_type TEXT NOT NULL DEFAULT 'syllabus',
                    url TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    is_official BOOLEAN NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '[]',
                    endorsements_count INTEGER NOT NULL DEFAULT 0,
                    upvotes_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS study_groups (
                    id TEXT PRIMARY KEY,
                    course_id TEXT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    creator_id TEXT NOT NULL,
                    institution TEXT NOT NULL DEFAULT '',
                    is_private BOOLEAN NOT NULL DEFAULT 0,
                    verified_only BOOLEAN NOT NULL DEFAULT 1,
                    max_members INTEGER,
                    meeting_schedule TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS study_group_members (
                    study_group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    is_verified_classmate BOOLEAN NOT NULL DEFAULT 1,
                    joined_at TEXT NOT NULL,
                    PRIMARY KEY (study_group_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS media_attachments (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT 'image',
                    alt_text TEXT,
                    audio_transcript TEXT,
                    captions_url TEXT,
                    description TEXT NOT NULL DEFAULT '',
                    discussion_id TEXT,
                    uploader_id TEXT,
                    content_warnings TEXT NOT NULL DEFAULT '[]',
                    is_sensitive BOOLEAN NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_content_filter_preferences (
                    user_id TEXT PRIMARY KEY,
                    mute_keywords TEXT NOT NULL DEFAULT '[]',
                    content_warning_tags TEXT NOT NULL DEFAULT '[]',
                    hide_sensitive_media BOOLEAN NOT NULL DEFAULT 0,
                    filter_level TEXT NOT NULL DEFAULT 'hide',
                    filter_notifications BOOLEAN NOT NULL DEFAULT 0,
                    filter_direct_messages BOOLEAN NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_accessibility_settings (
                    user_id TEXT PRIMARY KEY,
                    high_contrast BOOLEAN NOT NULL DEFAULT 0,
                    reduce_motion BOOLEAN NOT NULL DEFAULT 0,
                    screen_reader_optimized BOOLEAN NOT NULL DEFAULT 0,
                    font_size TEXT NOT NULL DEFAULT 'medium',
                    closed_captions_enabled BOOLEAN NOT NULL DEFAULT 0,
                    audio_transcripts_enabled BOOLEAN NOT NULL DEFAULT 1,
                    alt_text_required_on_post BOOLEAN NOT NULL DEFAULT 0,
                    autoplay_media BOOLEAN NOT NULL DEFAULT 0,
                    dyslexia_font BOOLEAN NOT NULL DEFAULT 0,
                    color_blind_mode TEXT NOT NULL DEFAULT 'none',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_discussion_tags_tag ON discussion_tags (tag);
                CREATE INDEX IF NOT EXISTS idx_lifecycle_events_target ON content_lifecycle_events (target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_lifecycle_events_actor ON content_lifecycle_events (actor_id);
                CREATE INDEX IF NOT EXISTS idx_content_interactions_target ON content_interactions (target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_content_interactions_user ON content_interactions (user_id);
                CREATE INDEX IF NOT EXISTS idx_topic_subscriptions_user ON topic_subscriptions (user_id);
                CREATE INDEX IF NOT EXISTS idx_topic_subscriptions_topic ON topic_subscriptions (topic);
                CREATE INDEX IF NOT EXISTS idx_join_requests_comm ON community_join_requests (community_id);
                CREATE INDEX IF NOT EXISTS idx_join_requests_user ON community_join_requests (user_id);
                CREATE INDEX IF NOT EXISTS idx_invites_comm ON community_invites (community_id);
                CREATE INDEX IF NOT EXISTS idx_invites_token ON community_invites (token);
                CREATE INDEX IF NOT EXISTS idx_reports_target ON moderation_reports (target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_reports_status ON moderation_reports (status);
                CREATE INDEX IF NOT EXISTS idx_appeals_target ON moderation_appeals (target_type, target_id);
                CREATE INDEX IF NOT EXISTS idx_appeals_appellant ON moderation_appeals (appellant_id);
                CREATE INDEX IF NOT EXISTS idx_appeals_status ON moderation_appeals (status);
                CREATE INDEX IF NOT EXISTS idx_courses_code ON courses (code);
                CREATE INDEX IF NOT EXISTS idx_courses_institution ON courses (institution);
                CREATE INDEX IF NOT EXISTS idx_enrollments_course ON course_enrollments (course_id);
                CREATE INDEX IF NOT EXISTS idx_enrollments_user ON course_enrollments (user_id);
                CREATE INDEX IF NOT EXISTS idx_resources_course ON course_resources (course_id);
                CREATE INDEX IF NOT EXISTS idx_resources_group ON course_resources (study_group_id);
                CREATE INDEX IF NOT EXISTS idx_study_groups_course ON study_groups (course_id);
                CREATE INDEX IF NOT EXISTS idx_study_group_members_group ON study_group_members (study_group_id);
                CREATE INDEX IF NOT EXISTS idx_study_group_members_user ON study_group_members (user_id);
                CREATE INDEX IF NOT EXISTS idx_media_discussion ON media_attachments (discussion_id);
                CREATE INDEX IF NOT EXISTS idx_media_uploader ON media_attachments (uploader_id);
            """)

            try:
                cursor = conn.execute("PRAGMA table_info(discussions)")
                columns = [row["name"] for row in cursor.fetchall()]
                if "community_id" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN community_id TEXT")
                if "channel_id" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN channel_id TEXT")
                if "course_id" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN course_id TEXT")
                if "study_group_id" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN study_group_id TEXT")
                if "is_hidden" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT 0")
                if "tags" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
                if "visibility" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'")
                if "content_warnings" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN content_warnings TEXT NOT NULL DEFAULT '[]'")
                if "alt_text" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN alt_text TEXT")
                if "audio_transcript" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN audio_transcript TEXT")
                if "status" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
                if "moderation_status" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN moderation_status TEXT NOT NULL DEFAULT 'none'")
                if "moderated_by" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN moderated_by TEXT")
                if "moderated_at" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN moderated_at TEXT")
                if "moderation_action" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN moderation_action TEXT")
                if "moderation_reason" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN moderation_reason TEXT")
                if "deleted_at" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN deleted_at TEXT")
                if "deleted_by" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN deleted_by TEXT")
                if "removal_reason" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN removal_reason TEXT")
                if "report_count" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN report_count INTEGER NOT NULL DEFAULT 0")
                if "last_interacted_at" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN last_interacted_at TEXT")
                if "interaction_count" not in columns:
                    conn.execute("ALTER TABLE discussions ADD COLUMN interaction_count INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass

            try:
                cursor = conn.execute("PRAGMA table_info(course_resources)")
                cres_cols = [row["name"] for row in cursor.fetchall()]
                if "upvotes_count" not in cres_cols and len(cres_cols) > 0:
                    conn.execute("ALTER TABLE course_resources ADD COLUMN upvotes_count INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass

            try:
                cursor = conn.execute("PRAGMA table_info(direct_messages)")
                dm_cols = [row["name"] for row in cursor.fetchall()]
                if "delivery_state" not in dm_cols and len(dm_cols) > 0:
                    conn.execute("ALTER TABLE direct_messages ADD COLUMN delivery_state TEXT NOT NULL DEFAULT 'sent'")
                if "read_at" not in dm_cols and len(dm_cols) > 0:
                    conn.execute("ALTER TABLE direct_messages ADD COLUMN read_at TEXT")
            except Exception:
                pass

            try:
                cursor = conn.execute("PRAGMA table_info(moderation_reports)")
                mod_cols = [row["name"] for row in cursor.fetchall()]
                if "category" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN category TEXT NOT NULL DEFAULT 'other'")
                if "report_count" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN report_count INTEGER NOT NULL DEFAULT 1")
                if "reporter_ids" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN reporter_ids TEXT NOT NULL DEFAULT '[]'")
                if "reasons" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN reasons TEXT NOT NULL DEFAULT '[]'")
                if "details" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN details TEXT NOT NULL DEFAULT ''")
                if "action_taken" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN action_taken TEXT")
                if "resolved_by" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN resolved_by TEXT")
                if "resolved_at" not in mod_cols and len(mod_cols) > 0:
                    conn.execute("ALTER TABLE moderation_reports ADD COLUMN resolved_at TEXT")
            except Exception:
                pass

            try:
                cursor = conn.execute("PRAGMA table_info(users)")
                user_cols = [row["name"] for row in cursor.fetchall()]
                if "bio" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")
                if "avatar_url" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
                if "school" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN school TEXT NOT NULL DEFAULT ''")
                if "university" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN university TEXT NOT NULL DEFAULT ''")
                if "class_year" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN class_year TEXT NOT NULL DEFAULT ''")
                if "interests" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN interests TEXT NOT NULL DEFAULT '[]'")
                if "visibility" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'")
                if "dm_privacy" not in user_cols and len(user_cols) > 0:
                    conn.execute("ALTER TABLE users ADD COLUMN dm_privacy TEXT NOT NULL DEFAULT 'everyone'")
            except Exception:
                pass

            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_discussions_status ON discussions (status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_discussions_moderation ON discussions (moderation_status)")
            except Exception:
                pass

            conn.commit()
        finally:
            if not self._memory_conn:
                conn.close()

    # --- Users ---
    def _row_to_user(self, r) -> User:
        interests_val = r["interests"] if "interests" in r.keys() and r["interests"] else "[]"
        if isinstance(interests_val, str):
            try:
                interests_list = json.loads(interests_val)
            except Exception:
                interests_list = [i.strip() for i in interests_val.split(",") if i.strip()]
        elif isinstance(interests_val, list):
            interests_list = interests_val
        else:
            interests_list = []

        vis_val = r["visibility"] if "visibility" in r.keys() and r["visibility"] else "public"
        dm_val = r["dm_privacy"] if "dm_privacy" in r.keys() and r["dm_privacy"] else "everyone"

        return User(
            id=r["id"],
            username=r["username"],
            is_active=bool(r["is_active"]),
            is_publicly_discoverable=bool(r["is_publicly_discoverable"]),
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
            bio=r["bio"] if "bio" in r.keys() and r["bio"] is not None else "",
            avatar_url=r["avatar_url"] if "avatar_url" in r.keys() else None,
            school=r["school"] if "school" in r.keys() and r["school"] is not None else "",
            university=r["university"] if "university" in r.keys() and r["university"] is not None else "",
            class_year=r["class_year"] if "class_year" in r.keys() and r["class_year"] is not None else "",
            interests=interests_list,
            visibility=vis_val,
            dm_privacy=dm_val
        )

    def create_user(self, user: User) -> None:
        conn = self.get_connection()
        try:
            interests_val = getattr(user, "interests", [])
            if isinstance(interests_val, (list, tuple)):
                interests_json = json.dumps(list(interests_val))
            elif isinstance(interests_val, str):
                interests_json = interests_val
            else:
                interests_json = "[]"

            vis_val = getattr(user, "visibility", "public") or "public"
            dm_val = getattr(user, "dm_privacy", "everyone") or "everyone"

            conn.execute(
                """INSERT INTO users (
                    id, username, is_active, is_publicly_discoverable, created_at,
                    bio, avatar_url, school, university, class_year, interests, visibility, dm_privacy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user.id, user.username, user.is_active, user.is_publicly_discoverable, user.created_at.isoformat(),
                    getattr(user, "bio", "") or "",
                    getattr(user, "avatar_url", None),
                    getattr(user, "school", "") or "",
                    getattr(user, "university", "") or "",
                    getattr(user, "class_year", "") or "",
                    interests_json,
                    vis_val,
                    dm_val
                )
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

    def get_user(self, user_id: str) -> Optional[User]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return self._row_to_user(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_user_by_username(self, username: str) -> Optional[User]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if row:
                return self._row_to_user(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def update_user_profile(
        self,
        user_id: str,
        bio: Optional[str] = None,
        avatar_url: Optional[str] = None,
        school: Optional[str] = None,
        university: Optional[str] = None,
        class_year: Optional[str] = None,
        interests: Optional[List[str]] = None,
        is_publicly_discoverable: Optional[bool] = None,
        is_active: Optional[bool] = None,
        username: Optional[str] = None,
        visibility: Optional[str] = None,
        dm_privacy: Optional[str] = None,
        **kwargs
    ) -> Optional[User]:
        if "topic_interests" in kwargs and interests is None:
            interests = kwargs["topic_interests"]
        if "class_affiliation" in kwargs and class_year is None:
            class_year = kwargs["class_affiliation"]
        if "class_name" in kwargs and class_year is None:
            class_year = kwargs["class_name"]
        if "profile_visibility" in kwargs and visibility is None:
            visibility = kwargs["profile_visibility"]
        if "dm_privacy" in kwargs and dm_privacy is None:
            dm_privacy = kwargs["dm_privacy"]
        if "allow_dms_from" in kwargs and dm_privacy is None:
            dm_privacy = kwargs["allow_dms_from"]
        if "direct_message_privacy" in kwargs and dm_privacy is None:
            dm_privacy = kwargs["direct_message_privacy"]
        if "privacy_settings" in kwargs and isinstance(kwargs["privacy_settings"], dict):
            ps = kwargs["privacy_settings"]
            if visibility is None and "visibility" in ps:
                visibility = ps["visibility"]
            if visibility is None and "profile_visibility" in ps:
                visibility = ps["profile_visibility"]
            if dm_privacy is None and "dm_privacy" in ps:
                dm_privacy = ps["dm_privacy"]
            if dm_privacy is None and "allow_dms_from" in ps:
                dm_privacy = ps["allow_dms_from"]
            if dm_privacy is None and "direct_message_privacy" in ps:
                dm_privacy = ps["direct_message_privacy"]
            if is_publicly_discoverable is None and "is_publicly_discoverable" in ps:
                is_publicly_discoverable = ps["is_publicly_discoverable"]
            if is_active is None and "is_active" in ps:
                is_active = ps["is_active"]
        if "affiliations" in kwargs and isinstance(kwargs["affiliations"], dict):
            aff = kwargs["affiliations"]
            if school is None and "school" in aff:
                school = aff["school"]
            if university is None and "university" in aff:
                university = aff["university"]
            if class_year is None and "class_year" in aff:
                class_year = aff["class_year"]
            elif class_year is None and "class" in aff:
                class_year = aff["class"]

        user = self.get_user(user_id)
        if not user:
            return None

        updates = []
        params = []

        if bio is not None:
            updates.append("bio = ?")
            params.append(bio)
        if avatar_url is not None:
            updates.append("avatar_url = ?")
            params.append(avatar_url)
        if school is not None:
            updates.append("school = ?")
            params.append(school)
        if university is not None:
            updates.append("university = ?")
            params.append(university)
        if class_year is not None:
            updates.append("class_year = ?")
            params.append(class_year)
        if interests is not None:
            updates.append("interests = ?")
            if isinstance(interests, (list, tuple)):
                params.append(json.dumps(list(interests)))
            elif isinstance(interests, str):
                params.append(interests)
            else:
                params.append("[]")
        if is_publicly_discoverable is not None:
            updates.append("is_publicly_discoverable = ?")
            params.append(1 if is_publicly_discoverable else 0)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if username is not None:
            updates.append("username = ?")
            params.append(username)
        if visibility is not None:
            norm_vis = visibility.strip().lower().replace("-", "_")
            if norm_vis in ("connections",):
                norm_vis = "connections_only"
            if norm_vis not in ("public", "connections_only", "private"):
                raise ValueError(f"Invalid visibility setting: {visibility}. Must be public, connections_only, or private")
            updates.append("visibility = ?")
            params.append(norm_vis)
        if dm_privacy is not None:
            norm_dm = dm_privacy.strip().lower().replace("-", "_")
            if norm_dm in ("all", "public"):
                norm_dm = "everyone"
            elif norm_dm in ("connections",):
                norm_dm = "connections_only"
            elif norm_dm in ("none", "disabled"):
                norm_dm = "nobody"
            if norm_dm not in ("everyone", "connections_only", "nobody"):
                raise ValueError(f"Invalid dm_privacy setting: {dm_privacy}. Must be everyone, connections_only, or nobody")
            updates.append("dm_privacy = ?")
            params.append(norm_dm)

        if not updates:
            return user

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        conn = self.get_connection()
        try:
            conn.execute(query, tuple(params))
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        return self.get_user(user_id)

    def update_profile(self, user_id: str, **kwargs) -> Optional[User]:
        return self.update_user_profile(user_id, **kwargs)

    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        return self.update_user_profile(user_id, **kwargs)

    def deactivate_user(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        conn = self.get_connection()
        try:
            cursor = conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def reactivate_user(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        conn = self.get_connection()
        try:
            cursor = conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def deactivate_account(self, user_id: str) -> bool:
        return self.deactivate_user(user_id)

    def reactivate_account(self, user_id: str) -> bool:
        return self.reactivate_user(user_id)

    def is_user_active(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        return bool(user and user.is_active)

    def is_account_active(self, user_id: str) -> bool:
        return self.is_user_active(user_id)

    def set_user_visibility(self, user_id: str, visibility: str) -> Optional[User]:
        norm_vis = (visibility or "public").strip().lower().replace("-", "_")
        if norm_vis in ("connections",):
            norm_vis = "connections_only"
        if norm_vis not in ("public", "connections_only", "private"):
            raise ValueError(f"Invalid visibility setting: {visibility}. Must be public, connections_only, or private")
        return self.update_user_profile(user_id, visibility=norm_vis)

    def get_user_visibility(self, user_id: str) -> Optional[str]:
        user = self.get_user(user_id)
        return user.visibility if user else None

    def set_dm_privacy(self, user_id: str, dm_privacy: str) -> Optional[User]:
        norm_dm = (dm_privacy or "everyone").strip().lower().replace("-", "_")
        if norm_dm in ("all", "public"):
            norm_dm = "everyone"
        elif norm_dm in ("connections",):
            norm_dm = "connections_only"
        elif norm_dm in ("none", "disabled"):
            norm_dm = "nobody"
        if norm_dm not in ("everyone", "connections_only", "nobody"):
            raise ValueError(f"Invalid dm_privacy setting: {dm_privacy}. Must be everyone, connections_only, or nobody")
        return self.update_user_profile(user_id, dm_privacy=norm_dm)

    def set_user_dm_privacy(self, user_id: str, dm_privacy: str) -> Optional[User]:
        return self.set_dm_privacy(user_id, dm_privacy)

    def get_dm_privacy(self, user_id: str) -> Optional[str]:
        user = self.get_user(user_id)
        return user.dm_privacy if user else None

    def get_user_dm_privacy(self, user_id: str) -> Optional[str]:
        return self.get_dm_privacy(user_id)

    def set_user_discoverability(self, user_id: str, is_discoverable: bool) -> Optional[User]:
        return self.update_user_profile(user_id, is_publicly_discoverable=is_discoverable)

    def get_user_discoverability(self, user_id: str) -> Optional[bool]:
        user = self.get_user(user_id)
        return user.is_publicly_discoverable if user else None

    def get_privacy_settings(self, user_id: str) -> Optional[PrivacySettings]:
        user = self.get_user(user_id)
        if not user:
            return None
        return PrivacySettings(
            user_id=user.id,
            visibility=user.visibility,
            dm_privacy=user.dm_privacy,
            is_publicly_discoverable=user.is_publicly_discoverable,
            is_active=user.is_active
        )

    def get_user_privacy_settings(self, user_id: str) -> Optional[PrivacySettings]:
        return self.get_privacy_settings(user_id)

    def get_user_privacy(self, user_id: str) -> Optional[PrivacySettings]:
        return self.get_privacy_settings(user_id)

    def set_privacy_settings(
        self,
        user_or_settings: Any = None,
        visibility: Optional[str] = None,
        dm_privacy: Optional[str] = None,
        is_publicly_discoverable: Optional[bool] = None,
        is_active: Optional[bool] = None,
        **kwargs
    ) -> bool:
        if isinstance(user_or_settings, PrivacySettings):
            user_id = user_or_settings.user_id
            visibility = visibility or user_or_settings.visibility
            dm_privacy = dm_privacy or user_or_settings.dm_privacy
            if is_publicly_discoverable is None:
                is_publicly_discoverable = user_or_settings.is_publicly_discoverable
            if is_active is None:
                is_active = user_or_settings.is_active
        elif isinstance(user_or_settings, dict):
            user_id = user_or_settings.get("user_id") or kwargs.get("user_id")
            visibility = visibility or user_or_settings.get("visibility") or user_or_settings.get("profile_visibility")
            dm_privacy = dm_privacy or user_or_settings.get("dm_privacy") or user_or_settings.get("allow_dms_from") or user_or_settings.get("direct_message_privacy")
            if is_publicly_discoverable is None:
                is_publicly_discoverable = user_or_settings.get("is_publicly_discoverable")
            if is_active is None:
                is_active = user_or_settings.get("is_active")
        elif isinstance(user_or_settings, str):
            user_id = user_or_settings
        else:
            user_id = kwargs.get("user_id")

        if not user_id:
            return False

        user = self.get_user(user_id)
        if not user:
            return False

        updated = self.update_user_profile(
            user_id,
            visibility=visibility,
            dm_privacy=dm_privacy,
            is_publicly_discoverable=is_publicly_discoverable,
            is_active=is_active,
            **kwargs
        )
        return bool(updated)

    def set_user_privacy_settings(self, *args, **kwargs) -> bool:
        return self.set_privacy_settings(*args, **kwargs)

    def update_privacy_settings(self, user_id: str, **kwargs) -> Optional[PrivacySettings]:
        user = self.update_user_profile(user_id, **kwargs)
        if not user:
            return None
        return self.get_privacy_settings(user_id)

    def update_user_privacy_settings(self, user_id: str, **kwargs) -> Optional[PrivacySettings]:
        return self.update_privacy_settings(user_id, **kwargs)

    # --- Connections ---
    def create_connection(self, follower_id: str, followed_id: str) -> None:
        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO connections (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                (follower_id, followed_id, datetime.utcnow().isoformat())
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

    def get_connections(self, follower_id: str) -> List[Connection]:
        conn = self.get_connection()
        try:
            rows = conn.execute("SELECT * FROM connections WHERE follower_id = ? OR followed_id = ?", (follower_id, follower_id)).fetchall()
            return [
                Connection(
                    follower_id=follower_id,
                    followed_id=(r["followed_id"] if r["follower_id"] == follower_id else r["follower_id"]),
                    created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
                ) for r in rows
            ]
        finally:
            if not self._memory_conn: conn.close()

    # --- Discussions ---
    def _row_to_discussion(self, r) -> Discussion:
        tags_val = r["tags"] if "tags" in r.keys() and r["tags"] else "[]"
        if isinstance(tags_val, str):
            try:
                tags_list = json.loads(tags_val)
            except Exception:
                tags_list = [t.strip().lstrip("#").lower() for t in tags_val.split(",") if t.strip()]
        elif isinstance(tags_val, list):
            tags_list = tags_val
        else:
            tags_list = []

        vis_val = r["visibility"] if "visibility" in r.keys() and r["visibility"] else "public"

        cw_val = r["content_warnings"] if "content_warnings" in r.keys() and r["content_warnings"] else "[]"
        if isinstance(cw_val, str):
            try:
                cw_list = json.loads(cw_val)
            except Exception:
                cw_list = [w.strip().lstrip("#").lower() for w in cw_val.split(",") if w.strip()]
        elif isinstance(cw_val, list):
            cw_list = cw_val
        else:
            cw_list = []

        alt_text_val = r["alt_text"] if "alt_text" in r.keys() else None
        transcript_val = r["audio_transcript"] if "audio_transcript" in r.keys() else None
        status_val = r["status"] if "status" in r.keys() and r["status"] else "active"
        mod_status_val = r["moderation_status"] if "moderation_status" in r.keys() and r["moderation_status"] else "none"
        mod_by_val = r["moderated_by"] if "moderated_by" in r.keys() else None
        mod_at_val = r["moderated_at"] if "moderated_at" in r.keys() else None
        mod_action_val = r["moderation_action"] if "moderation_action" in r.keys() else None
        mod_reason_val = r["moderation_reason"] if "moderation_reason" in r.keys() else None
        del_at_val = r["deleted_at"] if "deleted_at" in r.keys() else None
        del_by_val = r["deleted_by"] if "deleted_by" in r.keys() else None
        rem_reason_val = r["removal_reason"] if "removal_reason" in r.keys() else None
        rep_count_val = r["report_count"] if "report_count" in r.keys() and r["report_count"] is not None else 0
        last_int_val = r["last_interacted_at"] if "last_interacted_at" in r.keys() else None
        int_count_val = r["interaction_count"] if "interaction_count" in r.keys() and r["interaction_count"] is not None else 0

        disc = Discussion(
            id=r["id"],
            author_id=r["author_id"],
            content=r["content"],
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
            value_endorsements=r["value_endorsements"],
            parent_id=r["parent_id"],
            community_id=r["community_id"] if "community_id" in r.keys() else None,
            channel_id=r["channel_id"] if "channel_id" in r.keys() else None,
            course_id=r["course_id"] if "course_id" in r.keys() else None,
            study_group_id=r["study_group_id"] if "study_group_id" in r.keys() else None,
            is_hidden=bool(r["is_hidden"]) if "is_hidden" in r.keys() else False,
            tags=tags_list,
            visibility=vis_val,
            content_warnings=cw_list,
            alt_text=alt_text_val,
            audio_transcript=transcript_val,
            status=status_val,
            moderation_status=mod_status_val,
            moderated_by=mod_by_val,
            moderated_at=datetime.fromisoformat(mod_at_val) if isinstance(mod_at_val, str) and mod_at_val else mod_at_val,
            moderation_action=mod_action_val,
            moderation_reason=mod_reason_val,
            deleted_at=datetime.fromisoformat(del_at_val) if isinstance(del_at_val, str) and del_at_val else del_at_val,
            deleted_by=del_by_val,
            removal_reason=rem_reason_val,
            report_count=rep_count_val,
            last_interacted_at=datetime.fromisoformat(last_int_val) if isinstance(last_int_val, str) and last_int_val else last_int_val,
            interaction_count=int_count_val
        )
        return disc

    def create_discussion(self, disc: Discussion) -> None:
        if disc.parent_id:
            parent = self.get_discussion(disc.parent_id)
            if not parent:
                raise ValueError("Parent discussion not found")
            if parent.is_removed or parent.status in ("removed", "deleted") or parent.deleted_at is not None:
                raise ValueError("Cannot reply to removed content")
        if disc.community_id:
            if self.is_user_banned(disc.community_id, disc.author_id):
                raise PermissionError("User is banned from this community")
            comm = self.get_community(disc.community_id)
            if comm and comm.is_private and not self.is_community_member(disc.community_id, disc.author_id):
                raise PermissionError("User must be a member of the private community to post")
        conn = self.get_connection()
        try:
            tags_json = json.dumps(getattr(disc, "tags", []) or [])
            created_at_str = disc.created_at.isoformat() if isinstance(disc.created_at, datetime) else str(disc.created_at)
            vis_val = getattr(disc, "visibility", "public") or "public"
            course_id_val = getattr(disc, "course_id", None)
            study_group_id_val = getattr(disc, "study_group_id", None)
            cw_json = json.dumps(getattr(disc, "content_warnings", []) or [])
            alt_text_val = getattr(disc, "alt_text", None)
            audio_transcript_val = getattr(disc, "audio_transcript", None)
            status_val = getattr(disc, "status", "active") or "active"
            mod_status_val = getattr(disc, "moderation_status", "none") or "none"
            mod_by_val = getattr(disc, "moderated_by", None)
            mod_at_val = disc.moderated_at.isoformat() if getattr(disc, "moderated_at", None) else None
            mod_action_val = getattr(disc, "moderation_action", None)
            mod_reason_val = getattr(disc, "moderation_reason", None)
            del_at_val = disc.deleted_at.isoformat() if getattr(disc, "deleted_at", None) else None
            del_by_val = getattr(disc, "deleted_by", None)
            rem_reason_val = getattr(disc, "removal_reason", None)
            rep_count_val = getattr(disc, "report_count", 0) or 0
            last_int_val = disc.last_interacted_at.isoformat() if getattr(disc, "last_interacted_at", None) else None
            int_count_val = getattr(disc, "interaction_count", 0) or 0

            conn.execute(
                """INSERT INTO discussions (
                    id, author_id, content, created_at, value_endorsements, parent_id, community_id, channel_id, course_id, study_group_id, is_hidden, tags, visibility, content_warnings, alt_text, audio_transcript,
                    status, moderation_status, moderated_by, moderated_at, moderation_action, moderation_reason, deleted_at, deleted_by, removal_reason, report_count, last_interacted_at, interaction_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    disc.id, disc.author_id, disc.content, created_at_str,
                    disc.value_endorsements, disc.parent_id, disc.community_id, disc.channel_id,
                    course_id_val, study_group_id_val,
                    1 if disc.is_hidden else 0,
                    tags_json,
                    vis_val,
                    cw_json,
                    alt_text_val,
                    audio_transcript_val,
                    status_val,
                    mod_status_val,
                    mod_by_val,
                    mod_at_val,
                    mod_action_val,
                    mod_reason_val,
                    del_at_val,
                    del_by_val,
                    rem_reason_val,
                    rep_count_val,
                    last_int_val,
                    int_count_val
                )
            )
            for tag in (getattr(disc, "tags", []) or []):
                tag_clean = tag.strip().lstrip("#").lower() if isinstance(tag, str) else ""
                if tag_clean:
                    conn.execute(
                        "INSERT OR IGNORE INTO discussion_tags (discussion_id, tag, created_at) VALUES (?, ?, ?)",
                        (disc.id, tag_clean, created_at_str)
                    )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        # Record lifecycle event
        try:
            self.record_lifecycle_event(
                target_type="discussion",
                target_id=disc.id,
                event_type="create",
                actor_id=disc.author_id,
                new_state=status_val,
                metadata={"visibility": vis_val, "community_id": disc.community_id, "parent_id": disc.parent_id}
            )
        except Exception:
            pass

        # Handle attached media if present
        if getattr(disc, "media", None):
            for m in disc.media:
                if isinstance(m, dict):
                    m_id = m.get("id") or str(uuid.uuid4())
                    m_obj = MediaAttachment(
                        id=m_id,
                        url=m.get("url", ""),
                        media_type=m.get("media_type", "image"),
                        alt_text=m.get("alt_text"),
                        audio_transcript=m.get("audio_transcript") or m.get("transcript"),
                        captions_url=m.get("captions_url"),
                        description=m.get("description", ""),
                        discussion_id=disc.id,
                        uploader_id=m.get("uploader_id", disc.author_id),
                        content_warnings=m.get("content_warnings", []),
                        is_sensitive=bool(m.get("is_sensitive", False))
                    )
                    self.create_media(m_obj)
                elif isinstance(m, MediaAttachment):
                    m.discussion_id = disc.id
                    if not m.uploader_id:
                        m.uploader_id = disc.author_id
                    self.create_media(m)

        # Generate notifications for replies
        if disc.parent_id:
            parent = self.get_discussion(disc.parent_id)
            if parent and parent.author_id != disc.author_id:
                reply_notif = Notification(
                    id=str(uuid.uuid4()),
                    user_id=parent.author_id,
                    type="reply",
                    actor_id=disc.author_id,
                    target_id=disc.id,
                    content=disc.content[:100],
                    created_at=disc.created_at
                )
                self.create_notification(reply_notif)

        # Generate notifications for mentions (@username)
        if disc.content:
            mentioned_usernames = set(re.findall(r'@([a-zA-Z0-9_-]+)', disc.content))
            for uname in mentioned_usernames:
                mentioned_user = self.get_user_by_username(uname)
                if mentioned_user and mentioned_user.id != disc.author_id:
                    mention_notif = Notification(
                        id=str(uuid.uuid4()),
                        user_id=mentioned_user.id,
                        type="mention",
                        actor_id=disc.author_id,
                        target_id=disc.id,
                        content=disc.content[:100],
                        created_at=disc.created_at
                    )
                    self.create_notification(mention_notif)
        return disc

    def get_all_discussions(self, include_hidden: bool = False) -> List[Discussion]:
        conn = self.get_connection()
        try:
            if include_hidden:
                rows = conn.execute("SELECT * FROM discussions").fetchall()
            else:
                rows = conn.execute("SELECT * FROM discussions WHERE is_hidden = 0").fetchall()
            return [self._row_to_discussion(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_discussion(self, discussion_id: str) -> Optional[Discussion]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
            if row:
                return self._row_to_discussion(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def endorse_discussion(self, discussion_id: str, actor_id: Optional[str] = None) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE discussions SET value_endorsements = value_endorsements + 1 WHERE id = ?",
                (discussion_id,)
            )
            conn.commit()
            success = cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

        if success:
            disc = self.get_discussion(discussion_id)
            if disc and (not actor_id or actor_id != disc.author_id):
                endorse_notif = Notification(
                    id=str(uuid.uuid4()),
                    user_id=disc.author_id,
                    type="endorsement",
                    actor_id=actor_id or "anonymous",
                    target_id=disc.id,
                    content="Discussion endorsed",
                    created_at=datetime.utcnow()
                )
                self.create_notification(endorse_notif)
        return success

    def get_replies(self, parent_id: str, include_hidden: bool = False) -> List[Discussion]:
        conn = self.get_connection()
        try:
            if include_hidden:
                rows = conn.execute(
                    "SELECT * FROM discussions WHERE parent_id = ? ORDER BY created_at ASC",
                    (parent_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM discussions WHERE parent_id = ? AND is_hidden = 0 ORDER BY created_at ASC",
                    (parent_id,)
                ).fetchall()
            return [self._row_to_discussion(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_channel_discussions(self, channel_id: str, include_hidden: bool = False) -> List[Discussion]:
        conn = self.get_connection()
        try:
            if include_hidden:
                rows = conn.execute(
                    "SELECT * FROM discussions WHERE channel_id = ? ORDER BY created_at DESC",
                    (channel_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM discussions WHERE channel_id = ? AND is_hidden = 0 ORDER BY created_at DESC",
                    (channel_id,)
                ).fetchall()
            return [self._row_to_discussion(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_community_discussions(self, community_id: str, include_hidden: bool = False) -> List[Discussion]:
        conn = self.get_connection()
        try:
            if include_hidden:
                rows = conn.execute(
                    "SELECT * FROM discussions WHERE community_id = ? ORDER BY created_at DESC",
                    (community_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM discussions WHERE community_id = ? AND is_hidden = 0 ORDER BY created_at DESC",
                    (community_id,)
                ).fetchall()
            return [self._row_to_discussion(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def set_discussion_visibility(self, discussion_id: str, visibility: str) -> bool:
        norm_vis = (visibility or "public").strip().lower().replace("-", "_")
        if norm_vis not in ("public", "connections_only", "private"):
            raise ValueError(f"Invalid visibility setting: {visibility}. Must be public, connections_only, or private")
        disc = self.get_discussion(discussion_id)
        if not disc:
            return False
        conn = self.get_connection()
        try:
            cursor = conn.execute("UPDATE discussions SET visibility = ? WHERE id = ?", (norm_vis, discussion_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def get_discussion_visibility(self, discussion_id: str) -> Optional[str]:
        disc = self.get_discussion(discussion_id)
        return disc.visibility if disc else None

    def get_user_discussions(self, user_id: str, viewer_id: Optional[str] = None, include_replies: bool = False, include_hidden: bool = False) -> List[Discussion]:
        conn = self.get_connection()
        try:
            query = "SELECT * FROM discussions WHERE author_id = ?"
            params: List[Any] = [user_id]
            if not include_replies:
                query += " AND parent_id IS NULL"
            if not include_hidden:
                query += " AND is_hidden = 0"
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            discs = [self._row_to_discussion(r) for r in rows]
            if viewer_id is not None:
                discs = [d for d in discs if self.can_user_view_discussion(viewer_id, d)]
            return discs
        finally:
            if not self._memory_conn: conn.close()

    def get_user_replies(self, user_id: str, viewer_id: Optional[str] = None, include_hidden: bool = False) -> List[Discussion]:
        conn = self.get_connection()
        try:
            query = "SELECT * FROM discussions WHERE author_id = ? AND parent_id IS NOT NULL"
            params: List[Any] = [user_id]
            if not include_hidden:
                query += " AND is_hidden = 0"
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            reps = [self._row_to_discussion(r) for r in rows]
            if viewer_id is not None:
                reps = [r for r in reps if self.can_user_view_discussion(viewer_id, r)]
            return reps
        finally:
            if not self._memory_conn: conn.close()

    def is_connected(self, user1_id: str, user2_id: str) -> bool:
        if not user1_id or not user2_id:
            return False
        if user1_id == user2_id:
            return True
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM connections WHERE (follower_id = ? AND followed_id = ?) OR (follower_id = ? AND followed_id = ?)",
                (user1_id, user2_id, user2_id, user1_id)
            ).fetchone()
            return row is not None
        finally:
            if not self._memory_conn: conn.close()

    def can_user_view_discussion(self, arg1: Any, arg2: Any) -> bool:
        disc = None
        viewer_id = None
        
        if isinstance(arg1, Discussion):
            disc = arg1
            viewer_id = arg2
        elif isinstance(arg2, Discussion):
            disc = arg2
            viewer_id = arg1
        else:
            d1 = self.get_discussion(arg1) if arg1 else None
            d2 = self.get_discussion(arg2) if arg2 else None
            if d1 and not d2:
                disc = d1
                viewer_id = arg2
            elif d2 and not d1:
                disc = d2
                viewer_id = arg1
            elif d1 and d2:
                disc = d1
                viewer_id = arg2
            else:
                return False

        if not disc:
            return False

        if getattr(disc, "is_hidden", False):
            if not viewer_id or viewer_id != disc.author_id:
                return False

        if viewer_id and disc.author_id:
            if self.is_user_blocked(disc.author_id, viewer_id) or self.is_user_blocked(viewer_id, disc.author_id):
                return False

        # Community privacy check
        if disc.community_id:
            if viewer_id and self.is_user_banned(disc.community_id, viewer_id):
                return False
            comm = self.get_community(disc.community_id)
            if comm and comm.is_private:
                if not viewer_id or not self.is_community_member(disc.community_id, viewer_id):
                    return False

        # Study group privacy check
        if getattr(disc, "study_group_id", None):
            group = self.get_study_group(disc.study_group_id)
            if group and group.is_private:
                if not viewer_id or not self.is_study_group_member(disc.study_group_id, viewer_id):
                    return False

        vis = getattr(disc, "visibility", "public") or "public"
        if vis == "public":
            return True
        if not viewer_id:
            return False
        if viewer_id == disc.author_id:
            return True
        if vis in ("connections_only", "connections-only", "connections"):
            return self.is_connected(viewer_id, disc.author_id)
        if vis == "private":
            return viewer_id == disc.author_id
        return True

    def can_view_discussion(self, arg1: Any, arg2: Any) -> bool:
        return self.can_user_view_discussion(arg1, arg2)

    def can_user_view_community(self, arg1: Any, arg2: Any = None) -> bool:
        comm = None
        viewer_id = None
        if isinstance(arg1, Community):
            comm = arg1
            viewer_id = arg2
        elif isinstance(arg2, Community):
            comm = arg2
            viewer_id = arg1
        else:
            c1 = self.get_community(arg1) if isinstance(arg1, str) else None
            c2 = self.get_community(arg2) if isinstance(arg2, str) else None
            if c1 and not c2:
                comm = c1
                viewer_id = arg2
            elif c2 and not c1:
                comm = c2
                viewer_id = arg1
            elif c1 and c2:
                if self.get_user(arg2) and not self.get_user(arg1):
                    comm = c1
                    viewer_id = arg2
                elif self.get_user(arg1) and not self.get_user(arg2):
                    comm = c2
                    viewer_id = arg1
                else:
                    comm = c1
                    viewer_id = arg2
            else:
                if arg1 is None:
                    comm = self.get_community(arg2) if isinstance(arg2, str) else None
                    viewer_id = None
                elif arg2 is None:
                    comm = self.get_community(arg1) if isinstance(arg1, str) else None
                    viewer_id = None
                elif str(arg1).startswith("c_") or "comm" in str(arg1):
                    comm = self.get_community(arg1)
                    viewer_id = arg2
                elif str(arg2).startswith("c_") or "comm" in str(arg2):
                    comm = self.get_community(arg2)
                    viewer_id = arg1
                else:
                    return False

        if not comm:
            return False
        if viewer_id and self.is_user_banned(comm.id, viewer_id):
            return False
        if not comm.is_private:
            return True
        if not viewer_id:
            return False
        return self.is_community_member(comm.id, viewer_id)

    def can_view_community(self, arg1: Any, arg2: Any = None) -> bool:
        return self.can_user_view_community(arg1, arg2)

    def can_user_view_profile(self, arg1: Any, arg2: Any = None) -> bool:
        if arg1 is None and arg2 is None:
            return False
        if arg1 is None:
            target_id = arg2.id if isinstance(arg2, User) else arg2
            viewer_id = None
        elif arg2 is None:
            target_id = arg1.id if isinstance(arg1, User) else arg1
            viewer_id = None
        else:
            u1_id = arg1.id if isinstance(arg1, User) else arg1
            u2_id = arg2.id if isinstance(arg2, User) else arg2
            if u1_id == u2_id:
                u = self.get_user(u1_id)
                return bool(u and u.is_active)

            u1 = self.get_user(u1_id)
            u2 = self.get_user(u2_id)
            if not u1 or not u2:
                return False
            if not u1.is_active or not u2.is_active:
                return False
            if self.is_user_blocked(u1_id, u2_id) or self.is_user_blocked(u2_id, u1_id):
                return False

            v1 = (getattr(u1, "visibility", "public") or "public").strip().lower().replace("-", "_")
            v2 = (getattr(u2, "visibility", "public") or "public").strip().lower().replace("-", "_")
            if v1 in ("connections",): v1 = "connections_only"
            if v2 in ("connections",): v2 = "connections_only"

            if v1 == "private" or v2 == "private":
                return False
            if v1 == "connections_only" or v2 == "connections_only":
                return self.is_connected(u1_id, u2_id)
            return True

        target_user = self.get_user(target_id)
        if not target_user or not target_user.is_active:
            return False
        vis = (getattr(target_user, "visibility", "public") or "public").strip().lower().replace("-", "_")
        if vis in ("connections",): vis = "connections_only"
        return vis == "public"

    def can_view_user_profile(self, arg1: Any, arg2: Any = None) -> bool:
        return self.can_user_view_profile(arg1, arg2)

    def can_view_profile(self, arg1: Any, arg2: Any = None) -> bool:
        return self.can_user_view_profile(arg1, arg2)

    def _row_to_community_member(self, r) -> CommunityMember:
        return CommunityMember(
            community_id=r["community_id"],
            user_id=r["user_id"],
            role=r["role"],
            joined_at=datetime.fromisoformat(r["joined_at"]) if isinstance(r["joined_at"], str) else r["joined_at"]
        )

    # --- User Data Export ---
    def export_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        user = self.get_user(user_id)
        if not user:
            return None

        conn = self.get_connection()
        try:
            # Root discussions
            discussions = self.get_user_discussions(user_id, include_replies=False, include_hidden=True)
            # Replies
            replies = self.get_user_replies(user_id, include_hidden=True)
            # All discussions authored
            all_authored_discs = self.get_user_discussions(user_id, include_replies=True, include_hidden=True)

            # Direct messages (sent and received)
            dm_rows = conn.execute(
                "SELECT * FROM direct_messages WHERE sender_id = ? OR recipient_id = ? ORDER BY created_at ASC",
                (user_id, user_id)
            ).fetchall()
            dms = [self._row_to_direct_message(r) for r in dm_rows]
            sent_dms = [m for m in dms if m.sender_id == user_id]
            received_dms = [m for m in dms if m.recipient_id == user_id]

            # Connections (following and followers)
            connections = self.get_connections(user_id)
            follower_rows = conn.execute("SELECT * FROM connections WHERE followed_id = ?", (user_id,)).fetchall()
            followers = [
                Connection(
                    follower_id=r["follower_id"],
                    followed_id=r["followed_id"],
                    created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
                ) for r in follower_rows
            ]

            # Community memberships
            user_comms = self.get_user_communities(user_id)
            member_rows = conn.execute("SELECT * FROM community_members WHERE user_id = ?", (user_id,)).fetchall()
            memberships = [self._row_to_community_member(r) for r in member_rows]

            # Blocks
            blocks = self.get_blocked_users(user_id)

            # Topic subscriptions
            topic_subs = self.get_user_topic_subscriptions(user_id)

            # Notifications
            notifications = self.get_notifications(user_id, unread_only=False)

            # Join requests
            join_reqs = self.get_user_join_requests(user_id)

            # Academic: course enrollments, courses, study groups, shared resources
            user_enrollments = self.get_user_enrollments(user_id)
            user_courses = self.get_user_courses(user_id)
            user_study_groups = self.get_user_study_groups(user_id)
            res_rows = conn.execute("SELECT * FROM course_resources WHERE uploader_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
            user_resources = [self._row_to_course_resource(r) for r in res_rows]

            # Accessibility & Content Filtering
            acc_settings = self.get_accessibility_settings(user_id)
            filter_prefs = self.get_content_filter_preferences(user_id)
            media_items = self.get_user_media(user_id)

            user_dict = user.to_dict() if hasattr(user, "to_dict") else user.__dict__

            return {
                "user": user_dict,
                "discussions": [d.to_dict() if hasattr(d, "to_dict") else d.__dict__ for d in discussions],
                "replies": [r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in replies],
                "all_discussions": [d.to_dict() if hasattr(d, "to_dict") else d.__dict__ for d in all_authored_discs],
                "messages": [m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in dms],
                "sent_messages": [m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in sent_dms],
                "received_messages": [m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in received_dms],
                "connections": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in connections],
                "followers": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in followers],
                "following": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in connections],
                "memberships": [m.to_dict() if hasattr(m, "to_dict") else m.__dict__ for m in memberships],
                "communities": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in user_comms],
                "blocks": [b.to_dict() if hasattr(b, "to_dict") else b.__dict__ for b in blocks],
                "topic_subscriptions": topic_subs,
                "notifications": [n.to_dict() if hasattr(n, "to_dict") else n.__dict__ for n in notifications],
                "join_requests": [r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in join_reqs],
                "course_enrollments": [e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in user_enrollments],
                "courses": [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in user_courses],
                "study_groups": [g.to_dict() if hasattr(g, "to_dict") else g.__dict__ for g in user_study_groups],
                "shared_resources": [res.to_dict() if hasattr(res, "to_dict") else res.__dict__ for res in user_resources],
                "accessibility_settings": acc_settings.to_dict() if acc_settings else {},
                "content_filter_preferences": filter_prefs.to_dict() if filter_prefs else {},
                "media_attachments": [m.to_dict() if hasattr(m, "to_dict") else m for m in media_items],
                "exported_at": datetime.utcnow().isoformat()
            }
        finally:
            if not self._memory_conn: conn.close()

    def export_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.export_user_data(user_id)

    def get_user_data_export(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.export_user_data(user_id)

    def export_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.export_user_data(user_id)

    def export_user_data_json(self, user_id: str, indent: int = 2) -> Optional[str]:
        data = self.export_user_data(user_id)
        if data is None:
            return None
        return json.dumps(data, default=str, indent=indent)

    # --- Topic Tags & Hashtags ---
    def tag_discussion(self, discussion_id: str, tag: str) -> bool:
        disc = self.get_discussion(discussion_id)
        if not disc:
            return False
        tag_clean = tag.strip().lstrip("#").lower() if isinstance(tag, str) else ""
        if not tag_clean:
            return False
        conn = self.get_connection()
        try:
            now_str = datetime.utcnow().isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO discussion_tags (discussion_id, tag, created_at) VALUES (?, ?, ?)",
                (discussion_id, tag_clean, now_str)
            )
            rows = conn.execute("SELECT tag FROM discussion_tags WHERE discussion_id = ?", (discussion_id,)).fetchall()
            all_tags = [r["tag"] for r in rows]
            conn.execute("UPDATE discussions SET tags = ? WHERE id = ?", (json.dumps(all_tags), discussion_id))
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def add_discussion_tags(self, discussion_id: str, tags: List[str]) -> bool:
        disc = self.get_discussion(discussion_id)
        if not disc:
            return False
        conn = self.get_connection()
        try:
            now_str = datetime.utcnow().isoformat()
            for tag in tags:
                tag_clean = tag.strip().lstrip("#").lower() if isinstance(tag, str) else ""
                if tag_clean:
                    conn.execute(
                        "INSERT OR IGNORE INTO discussion_tags (discussion_id, tag, created_at) VALUES (?, ?, ?)",
                        (discussion_id, tag_clean, now_str)
                    )
            rows = conn.execute("SELECT tag FROM discussion_tags WHERE discussion_id = ?", (discussion_id,)).fetchall()
            all_tags = [r["tag"] for r in rows]
            conn.execute("UPDATE discussions SET tags = ? WHERE id = ?", (json.dumps(all_tags), discussion_id))
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def add_tags_to_discussion(self, discussion_id: str, tags: List[str]) -> bool:
        return self.add_discussion_tags(discussion_id, tags)

    def remove_discussion_tag(self, discussion_id: str, tag: str) -> bool:
        tag_clean = tag.strip().lstrip("#").lower() if isinstance(tag, str) else ""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM discussion_tags WHERE discussion_id = ? AND tag = ?",
                (discussion_id, tag_clean)
            )
            rows = conn.execute("SELECT tag FROM discussion_tags WHERE discussion_id = ?", (discussion_id,)).fetchall()
            all_tags = [r["tag"] for r in rows]
            conn.execute("UPDATE discussions SET tags = ? WHERE id = ?", (json.dumps(all_tags), discussion_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def get_discussion_tags(self, discussion_id: str) -> List[str]:
        conn = self.get_connection()
        try:
            rows = conn.execute("SELECT tag FROM discussion_tags WHERE discussion_id = ? ORDER BY tag ASC", (discussion_id,)).fetchall()
            return [r["tag"] for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_tags_for_discussion(self, discussion_id: str) -> List[str]:
        return self.get_discussion_tags(discussion_id)

    def get_discussions_by_tag(
        self,
        tag: str,
        include_hidden: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Discussion]:
        tag_clean = tag.strip().lstrip("#").lower() if isinstance(tag, str) else ""
        conn = self.get_connection()
        try:
            query = """
                SELECT d.* FROM discussions d
                JOIN discussion_tags dt ON d.id = dt.discussion_id
                WHERE dt.tag = ?
            """
            params: List[Any] = [tag_clean]
            if not include_hidden:
                query += " AND d.is_hidden = 0"
            query += " ORDER BY d.created_at DESC"
            if limit is not None:
                query += f" LIMIT {int(limit)}"
                if offset is not None:
                    query += f" OFFSET {int(offset)}"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_discussion(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_discussions_by_topic(self, topic: str, include_hidden: bool = False, **kwargs) -> List[Discussion]:
        return self.get_discussions_by_tag(topic, include_hidden=include_hidden, **kwargs)

    # --- Topic Interest Subscriptions ---
    def subscribe_to_topic(self, user_id: str, topic: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        topic_clean = topic.strip().lstrip("#").lower() if isinstance(topic, str) else ""
        if not topic_clean:
            return False
        conn = self.get_connection()
        try:
            now_str = datetime.utcnow().isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO topic_subscriptions (user_id, topic, created_at) VALUES (?, ?, ?)",
                (user_id, topic_clean, now_str)
            )
            interests = list(user.interests or [])
            if topic_clean not in interests:
                interests.append(topic_clean)
                conn.execute("UPDATE users SET interests = ? WHERE id = ?", (json.dumps(interests), user_id))
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def subscribe_topic(self, user_id: str, topic: str) -> bool:
        return self.subscribe_to_topic(user_id, topic)

    def unsubscribe_from_topic(self, user_id: str, topic: str) -> bool:
        topic_clean = topic.strip().lstrip("#").lower() if isinstance(topic, str) else ""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM topic_subscriptions WHERE user_id = ? AND topic = ?",
                (user_id, topic_clean)
            )
            user = self.get_user(user_id)
            if user and user.interests and topic_clean in user.interests:
                interests = [i for i in user.interests if i != topic_clean]
                conn.execute("UPDATE users SET interests = ? WHERE id = ?", (json.dumps(interests), user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def unsubscribe_topic(self, user_id: str, topic: str) -> bool:
        return self.unsubscribe_from_topic(user_id, topic)

    def is_user_subscribed_to_topic(self, user_id: str, topic: str) -> bool:
        topic_clean = topic.strip().lstrip("#").lower() if isinstance(topic, str) else ""
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM topic_subscriptions WHERE user_id = ? AND topic = ?",
                (user_id, topic_clean)
            ).fetchone()
            if row:
                return True
            user = self.get_user(user_id)
            if user and user.interests:
                return topic_clean in [i.strip().lstrip("#").lower() for i in user.interests]
            return False
        finally:
            if not self._memory_conn: conn.close()

    def is_subscribed_to_topic(self, user_id: str, topic: str) -> bool:
        return self.is_user_subscribed_to_topic(user_id, topic)

    def get_user_topic_subscriptions(self, user_id: str) -> List[str]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT topic FROM topic_subscriptions WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
            subscribed = [r["topic"] for r in rows]
            user = self.get_user(user_id)
            if user and user.interests:
                for i in user.interests:
                    i_clean = i.strip().lstrip("#").lower()
                    if i_clean and i_clean not in subscribed:
                        subscribed.append(i_clean)
            return subscribed
        finally:
            if not self._memory_conn: conn.close()

    def get_subscribed_topics(self, user_id: str) -> List[str]:
        return self.get_user_topic_subscriptions(user_id)

    def get_topic_subscriptions(self, user_id: str) -> List[TopicSubscription]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM topic_subscriptions WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
            return [
                TopicSubscription(
                    user_id=r["user_id"],
                    topic=r["topic"],
                    created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
                ) for r in rows
            ]
        finally:
            if not self._memory_conn: conn.close()

    def get_topic_subscribers(self, topic: str, publicly_discoverable_only: bool = False) -> List[User]:
        topic_clean = topic.strip().lstrip("#").lower() if isinstance(topic, str) else ""
        conn = self.get_connection()
        try:
            rows = conn.execute(
                """SELECT u.* FROM users u
                   JOIN topic_subscriptions ts ON u.id = ts.user_id
                   WHERE ts.topic = ? AND u.is_active = 1
                   ORDER BY ts.created_at ASC""",
                (topic_clean,)
            ).fetchall()
            subscribers = [self._row_to_user(r) for r in rows]
            sub_ids = {u.id for u in subscribers}

            all_users = self.get_users_by_interest(topic_clean, publicly_discoverable_only=publicly_discoverable_only)
            for u in all_users:
                if u.id not in sub_ids:
                    subscribers.append(u)
                    sub_ids.add(u.id)

            if publicly_discoverable_only:
                subscribers = [u for u in subscribers if u.is_publicly_discoverable]
            return subscribers
        finally:
            if not self._memory_conn: conn.close()

    def get_topic_subscriber_ids(self, topic: str) -> List[str]:
        return [u.id for u in self.get_topic_subscribers(topic)]

    # --- Trending Topics Discovery ---
    def get_trending_topics(
        self,
        limit: int = 10,
        include_hidden: bool = False,
        min_count: int = 1
    ) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            hidden_clause = "" if include_hidden else "AND d.is_hidden = 0"
            query = f"""
                SELECT dt.tag as topic,
                       COUNT(DISTINCT dt.discussion_id) as discussion_count,
                       COALESCE(SUM(d.value_endorsements), 0) as total_endorsements,
                       (COUNT(DISTINCT dt.discussion_id) * 2.0 + COALESCE(SUM(d.value_endorsements), 0) * 1.0) as score
                FROM discussion_tags dt
                JOIN discussions d ON dt.discussion_id = d.id
                WHERE 1=1 {hidden_clause}
                GROUP BY dt.tag
                HAVING discussion_count >= ?
                ORDER BY score DESC, discussion_count DESC, dt.tag ASC
                LIMIT ?
            """
            rows = conn.execute(query, (min_count, limit)).fetchall()
            trends = []
            for r in rows:
                topic_name = r["topic"]
                d_count = r["discussion_count"]
                sub_count_row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM topic_subscriptions WHERE topic = ?",
                    (topic_name,)
                ).fetchone()
                sub_count = sub_count_row["cnt"] if sub_count_row else 0
                trends.append({
                    "topic": topic_name,
                    "tag": topic_name,
                    "hashtag": f"#{topic_name}",
                    "count": d_count,
                    "discussion_count": d_count,
                    "endorsements": r["total_endorsements"],
                    "subscribers_count": sub_count,
                    "score": float(r["score"])
                })
            return trends
        finally:
            if not self._memory_conn: conn.close()

    def get_popular_topics(self, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return self.get_trending_topics(limit=limit, **kwargs)

    def get_trending_tags(self, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return self.get_trending_topics(limit=limit, **kwargs)

    def get_all_topics(self, include_hidden: bool = False) -> List[str]:
        conn = self.get_connection()
        try:
            hidden_clause = "" if include_hidden else "JOIN discussions d ON dt.discussion_id = d.id WHERE d.is_hidden = 0"
            query = f"SELECT DISTINCT dt.tag FROM discussion_tags dt {hidden_clause} ORDER BY dt.tag ASC"
            rows = conn.execute(query).fetchall()
            return [r["tag"] for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_all_tags(self, include_hidden: bool = False) -> List[str]:
        return self.get_all_topics(include_hidden=include_hidden)

    def get_topic_details(self, topic: str) -> Dict[str, Any]:
        topic_clean = topic.strip().lstrip("#").lower() if isinstance(topic, str) else ""
        conn = self.get_connection()
        try:
            d_count_row = conn.execute(
                """SELECT COUNT(DISTINCT dt.discussion_id) as cnt,
                          COALESCE(SUM(d.value_endorsements), 0) as total_endorsements
                   FROM discussion_tags dt
                   JOIN discussions d ON dt.discussion_id = d.id
                   WHERE dt.tag = ? AND d.is_hidden = 0""",
                (topic_clean,)
            ).fetchone()
            sub_count_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM topic_subscriptions WHERE topic = ?",
                (topic_clean,)
            ).fetchone()

            d_count = d_count_row["cnt"] if d_count_row else 0
            endorsements = d_count_row["total_endorsements"] if d_count_row else 0
            sub_count = sub_count_row["cnt"] if sub_count_row else 0

            return {
                "topic": topic_clean,
                "tag": topic_clean,
                "hashtag": f"#{topic_clean}",
                "discussion_count": d_count,
                "endorsements": endorsements,
                "subscribers_count": sub_count,
                "score": float(d_count * 2.0 + endorsements * 1.0)
            }
        finally:
            if not self._memory_conn: conn.close()

    # --- Row Converters for Join Requests & Invites ---
    def _row_to_join_request(self, r) -> CommunityJoinRequest:
        reviewed_at_val = r["reviewed_at"] if "reviewed_at" in r.keys() and r["reviewed_at"] else None
        return CommunityJoinRequest(
            id=r["id"],
            community_id=r["community_id"],
            user_id=r["user_id"],
            status=r["status"],
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
            reviewed_by=r["reviewed_by"] if "reviewed_by" in r.keys() else None,
            reviewed_at=datetime.fromisoformat(reviewed_at_val) if reviewed_at_val else None,
            message=r["message"] if "message" in r.keys() and r["message"] is not None else ""
        )

    def _row_to_invite(self, r) -> CommunityInvite:
        expires_at_val = r["expires_at"] if "expires_at" in r.keys() and r["expires_at"] else None
        return CommunityInvite(
            id=r["id"],
            community_id=r["community_id"],
            token=r["token"],
            created_by=r["created_by"],
            role=r["role"] if "role" in r.keys() else "member",
            max_uses=r["max_uses"] if "max_uses" in r.keys() else None,
            uses_count=r["uses_count"] if "uses_count" in r.keys() else 0,
            expires_at=datetime.fromisoformat(expires_at_val) if expires_at_val else None,
            is_active=bool(r["is_active"]) if "is_active" in r.keys() else True,
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
        )

    # --- Communities ---
    def create_community(self, community: Community, creator_role: str = "owner") -> None:
        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT INTO communities (id, name, description, creator_id, is_private, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    community.id, community.name, community.description, community.creator_id,
                    1 if community.is_private else 0, community.created_at.isoformat()
                )
            )
            if community.creator_id:
                conn.execute(
                    "INSERT OR IGNORE INTO community_members (community_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                    (community.id, community.creator_id, creator_role, community.created_at.isoformat())
                )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

    def get_community(self, community_id: str) -> Optional[Community]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM communities WHERE id = ?", (community_id,)).fetchone()
            if row:
                return Community(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    creator_id=row["creator_id"],
                    is_private=bool(row["is_private"]),
                    created_at=datetime.fromisoformat(row["created_at"])
                )
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_all_communities(self) -> List[Community]:
        conn = self.get_connection()
        try:
            rows = conn.execute("SELECT * FROM communities ORDER BY created_at DESC").fetchall()
            return [
                Community(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"],
                    creator_id=r["creator_id"],
                    is_private=bool(r["is_private"]),
                    created_at=datetime.fromisoformat(r["created_at"])
                ) for r in rows
            ]
        finally:
            if not self._memory_conn: conn.close()

    def get_community_member(self, community_id: str, user_id: str) -> Optional[CommunityMember]:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM community_members WHERE community_id = ? AND user_id = ?",
                (community_id, user_id)
            ).fetchone()
            if row:
                return CommunityMember(
                    community_id=row["community_id"],
                    user_id=row["user_id"],
                    role=row["role"],
                    joined_at=datetime.fromisoformat(row["joined_at"]) if isinstance(row["joined_at"], str) else row["joined_at"]
                )
            return None
        finally:
            if not self._memory_conn: conn.close()

    def is_community_member(self, community_id: str, user_id: str) -> bool:
        if not community_id or not user_id:
            return False
        return self.get_community_member(community_id, user_id) is not None

    def is_member(self, community_id: str, user_id: str) -> bool:
        return self.is_community_member(community_id, user_id)

    def get_member_role(self, community_id: str, user_id: str) -> Optional[str]:
        m = self.get_community_member(community_id, user_id)
        return m.role if m else None

    def get_community_members(self, community_id: str, role: Optional[str] = None) -> List[CommunityMember]:
        conn = self.get_connection()
        try:
            if role:
                rows = conn.execute(
                    "SELECT * FROM community_members WHERE community_id = ? AND role = ? ORDER BY joined_at ASC",
                    (community_id, role)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM community_members WHERE community_id = ? ORDER BY joined_at ASC",
                    (community_id,)
                ).fetchall()
            return [
                CommunityMember(
                    community_id=r["community_id"],
                    user_id=r["user_id"],
                    role=r["role"],
                    joined_at=datetime.fromisoformat(r["joined_at"])
                ) for r in rows
            ]
        finally:
            if not self._memory_conn: conn.close()

    def has_community_permission(self, community_id: str, user_id: str, action: str) -> bool:
        if self.is_user_banned(community_id, user_id):
            return False
        role = self.get_member_role(community_id, user_id)
        if not role:
            if action in ("view", "browse"):
                comm = self.get_community(community_id)
                return comm is not None and not comm.is_private
            return False

        level = ROLE_LEVELS.get(role, 0)
        if action in ("transfer_ownership", "delete_community"):
            return level >= 40  # owner only
        elif action in ("manage_roles", "manage_channels", "update_community"):
            return level >= 30  # owner, admin
        elif action in ("ban_users", "unban_users", "moderate", "moderate_discussions", "approve_join_requests", "reject_join_requests", "create_invites"):
            return level >= 20  # owner, admin, moderator
        elif action in ("post", "create_discussion", "reply", "view"):
            return level >= 10  # member+
        return True

    def update_member_role(
        self, community_id: str, user_id: str, new_role: str, actor_id: Optional[str] = None
    ) -> bool:
        if new_role not in ("owner", "admin", "moderator", "member"):
            raise ValueError(f"Invalid role: {new_role}")

        member = self.get_community_member(community_id, user_id)
        if not member:
            return False

        if actor_id:
            actor_role = self.get_member_role(community_id, actor_id)
            if not actor_role:
                raise PermissionError("Actor is not a member of this community")
            
            actor_level = ROLE_LEVELS.get(actor_role, 0)
            target_current_level = ROLE_LEVELS.get(member.role, 0)
            new_level = ROLE_LEVELS.get(new_role, 0)

            if actor_level < 30:
                raise PermissionError("Insufficient permissions to manage roles")

            if actor_role == "admin":
                if target_current_level >= 30:
                    raise PermissionError("Admins cannot modify owner or fellow admin roles")
                if new_level >= 30:
                    raise PermissionError("Admins cannot promote users to admin or owner")

            if new_role == "owner":
                if actor_role != "owner":
                    raise PermissionError("Only the community owner can transfer ownership")
                return self.transfer_community_ownership(community_id, actor_id, user_id)

        if new_role == "owner":
            conn = self.get_connection()
            try:
                conn.execute(
                    "UPDATE community_members SET role = 'admin' WHERE community_id = ? AND role = 'owner'",
                    (community_id,)
                )
                conn.execute(
                    "UPDATE community_members SET role = 'owner' WHERE community_id = ? AND user_id = ?",
                    (community_id, user_id)
                )
                conn.execute(
                    "UPDATE communities SET creator_id = ? WHERE id = ?",
                    (user_id, community_id)
                )
                conn.commit()
                return True
            finally:
                if not self._memory_conn: conn.close()

        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE community_members SET role = ? WHERE community_id = ? AND user_id = ?",
                (new_role, community_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def transfer_community_ownership(self, community_id: str, current_owner_id: str, new_owner_id: str) -> bool:
        curr_role = self.get_member_role(community_id, current_owner_id)
        if curr_role != "owner":
            raise PermissionError("current_owner_id is not the owner of this community")

        new_member = self.get_community_member(community_id, new_owner_id)
        if not new_member:
            raise ValueError("new_owner_id is not a member of this community")

        conn = self.get_connection()
        try:
            conn.execute(
                "UPDATE community_members SET role = 'admin' WHERE community_id = ? AND user_id = ?",
                (community_id, current_owner_id)
            )
            conn.execute(
                "UPDATE community_members SET role = 'owner' WHERE community_id = ? AND user_id = ?",
                (community_id, new_owner_id)
            )
            conn.execute(
                "UPDATE communities SET creator_id = ? WHERE id = ?",
                (new_owner_id, community_id)
            )
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def join_community(self, community_id: str, user_id: str, role: str = "member", invite_token: Optional[str] = None) -> bool:
        if self.is_user_banned(community_id, user_id):
            return False

        comm = self.get_community(community_id)
        if not comm:
            return False

        if invite_token:
            return self.use_invite(invite_token, user_id)

        if comm.is_private and user_id != comm.creator_id and role == "member":
            conn = self.get_connection()
            try:
                req_row = conn.execute(
                    "SELECT * FROM community_join_requests WHERE community_id = ? AND user_id = ? AND status = 'approved'",
                    (community_id, user_id)
                ).fetchone()
                if not req_row:
                    try:
                        self.create_join_request(community_id, user_id)
                    except Exception:
                        pass
                    return False
            finally:
                if not self._memory_conn: conn.close()

        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO community_members (community_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                (community_id, user_id, role, datetime.utcnow().isoformat())
            )
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def add_community_member(self, member_or_community_id: Any, user_id: Optional[str] = None, role: str = "member") -> bool:
        if isinstance(member_or_community_id, CommunityMember):
            community_id = member_or_community_id.community_id
            user_id = member_or_community_id.user_id
            role = member_or_community_id.role
            joined_at = member_or_community_id.joined_at.isoformat() if isinstance(member_or_community_id.joined_at, datetime) else str(member_or_community_id.joined_at)
        else:
            community_id = str(member_or_community_id)
            user_id = str(user_id) if user_id else ""
            joined_at = datetime.utcnow().isoformat()

        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO community_members (community_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                (community_id, user_id, role, joined_at)
            )
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def leave_community(self, community_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM community_members WHERE community_id = ? AND user_id = ?",
                (community_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def get_user_communities(self, user_id: str) -> List[Community]:
        conn = self.get_connection()
        try:
            rows = conn.execute("""
                SELECT c.* FROM communities c
                JOIN community_members cm ON c.id = cm.community_id
                WHERE cm.user_id = ?
                ORDER BY cm.joined_at DESC
            """, (user_id,)).fetchall()
            return [
                Community(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"],
                    creator_id=r["creator_id"],
                    is_private=bool(r["is_private"]),
                    created_at=datetime.fromisoformat(r["created_at"])
                ) for r in rows
            ]
        finally:
            if not self._memory_conn: conn.close()

    # --- Private Community Join Requests & Approvals ---
    def create_join_request(self, community_id: str, user_id: str, message: str = "") -> CommunityJoinRequest:
        if self.is_user_banned(community_id, user_id):
            raise PermissionError("User is banned from this community")

        if self.get_community_member(community_id, user_id):
            raise ValueError("User is already a member of this community")

        conn = self.get_connection()
        try:
            existing = conn.execute(
                "SELECT * FROM community_join_requests WHERE community_id = ? AND user_id = ? AND status = 'pending'",
                (community_id, user_id)
            ).fetchone()
            if existing:
                return self._row_to_join_request(existing)

            req_id = str(uuid.uuid4())
            now = datetime.utcnow()
            now_str = now.isoformat()
            conn.execute(
                """INSERT INTO community_join_requests (
                    id, community_id, user_id, status, created_at, message
                ) VALUES (?, ?, ?, 'pending', ?, ?)""",
                (req_id, community_id, user_id, now_str, message)
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        # Notify community owner and admins
        members = self.get_community_members(community_id)
        for m in members:
            if m.role in ("owner", "admin"):
                notif = Notification(
                    id=str(uuid.uuid4()),
                    user_id=m.user_id,
                    type="join_request",
                    actor_id=user_id,
                    target_id=req_id,
                    content=f"Join request from user {user_id}",
                    created_at=now
                )
                self.create_notification(notif)

        return CommunityJoinRequest(
            id=req_id,
            community_id=community_id,
            user_id=user_id,
            status="pending",
            created_at=now,
            message=message
        )

    def request_to_join(self, community_id: str, user_id: str, message: str = "") -> CommunityJoinRequest:
        return self.create_join_request(community_id, user_id, message)

    def request_join_community(self, community_id: str, user_id: str, message: str = "") -> CommunityJoinRequest:
        return self.create_join_request(community_id, user_id, message)

    def get_join_request(self, request_id: str) -> Optional[CommunityJoinRequest]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM community_join_requests WHERE id = ?", (request_id,)).fetchone()
            if row:
                return self._row_to_join_request(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_community_join_requests(self, community_id: str, status: Optional[str] = None) -> List[CommunityJoinRequest]:
        conn = self.get_connection()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM community_join_requests WHERE community_id = ? AND status = ? ORDER BY created_at DESC",
                    (community_id, status)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM community_join_requests WHERE community_id = ? ORDER BY created_at DESC",
                    (community_id,)
                ).fetchall()
            return [self._row_to_join_request(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_user_join_requests(self, user_id: str, status: Optional[str] = None) -> List[CommunityJoinRequest]:
        conn = self.get_connection()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM community_join_requests WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                    (user_id, status)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM community_join_requests WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                ).fetchall()
            return [self._row_to_join_request(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def approve_join_request(self, request_id: str, reviewer_id: Optional[str] = None, role: str = "member") -> bool:
        req = self.get_join_request(request_id)
        if not req:
            return False
        if reviewer_id:
            if not self.has_community_permission(req.community_id, reviewer_id, "approve_join_requests"):
                raise PermissionError("Reviewer does not have permission to approve join requests")

        now = datetime.utcnow()
        now_str = now.isoformat()
        conn = self.get_connection()
        try:
            conn.execute(
                """UPDATE community_join_requests 
                   SET status = 'approved', reviewed_by = ?, reviewed_at = ? 
                   WHERE id = ?""",
                (reviewer_id, now_str, request_id)
            )
            conn.execute(
                "INSERT OR REPLACE INTO community_members (community_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                (req.community_id, req.user_id, role, now_str)
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=req.user_id,
            type="join_request_approved",
            actor_id=reviewer_id or "system",
            target_id=req.community_id,
            content=f"Your request to join community {req.community_id} was approved",
            created_at=now
        )
        self.create_notification(notif)
        return True

    def reject_join_request(self, request_id: str, reviewer_id: Optional[str] = None, reason: Optional[str] = None) -> bool:
        req = self.get_join_request(request_id)
        if not req:
            return False
        if reviewer_id:
            if not self.has_community_permission(req.community_id, reviewer_id, "reject_join_requests"):
                raise PermissionError("Reviewer does not have permission to reject join requests")

        now = datetime.utcnow()
        now_str = now.isoformat()
        conn = self.get_connection()
        try:
            conn.execute(
                """UPDATE community_join_requests 
                   SET status = 'rejected', reviewed_by = ?, reviewed_at = ? 
                   WHERE id = ?""",
                (reviewer_id, now_str, request_id)
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=req.user_id,
            type="join_request_rejected",
            actor_id=reviewer_id or "system",
            target_id=req.community_id,
            content=f"Your request to join community {req.community_id} was rejected",
            created_at=now
        )
        self.create_notification(notif)
        return True

    # --- Member Invite Tokens ---
    def create_invite(
        self,
        community_id: str,
        created_by: str,
        role: str = "member",
        max_uses: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        token: Optional[str] = None
    ) -> CommunityInvite:
        if not self.has_community_permission(community_id, created_by, "create_invites"):
            raise PermissionError("User does not have permission to create invites for this community")

        invite_id = str(uuid.uuid4())
        invite_token = token or str(uuid.uuid4()).replace("-", "")[:16]
        now = datetime.utcnow()
        now_str = now.isoformat()
        exp_str = expires_at.isoformat() if isinstance(expires_at, datetime) else (str(expires_at) if expires_at else None)

        conn = self.get_connection()
        try:
            conn.execute(
                """INSERT INTO community_invites (
                    id, community_id, token, created_by, role, max_uses, uses_count, expires_at, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 1, ?)""",
                (invite_id, community_id, invite_token, created_by, role, max_uses, exp_str, now_str)
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        return CommunityInvite(
            id=invite_id,
            community_id=community_id,
            token=invite_token,
            created_by=created_by,
            role=role,
            max_uses=max_uses,
            uses_count=0,
            expires_at=expires_at,
            is_active=True,
            created_at=now
        )

    def create_community_invite(self, *args, **kwargs) -> CommunityInvite:
        return self.create_invite(*args, **kwargs)

    def get_invite(self, token_or_id: str) -> Optional[CommunityInvite]:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM community_invites WHERE token = ? OR id = ?",
                (token_or_id, token_or_id)
            ).fetchone()
            if row:
                return self._row_to_invite(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_community_invite(self, token_or_id: str) -> Optional[CommunityInvite]:
        return self.get_invite(token_or_id)

    def get_community_invites(self, community_id: str, active_only: bool = True) -> List[CommunityInvite]:
        conn = self.get_connection()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM community_invites WHERE community_id = ? AND is_active = 1 ORDER BY created_at DESC",
                    (community_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM community_invites WHERE community_id = ? ORDER BY created_at DESC",
                    (community_id,)
                ).fetchall()
            invites = [self._row_to_invite(r) for r in rows]
            if active_only:
                invites = [inv for inv in invites if inv.is_valid]
            return invites
        finally:
            if not self._memory_conn: conn.close()

    def revoke_invite(self, token_or_id: str, actor_id: Optional[str] = None) -> bool:
        invite = self.get_invite(token_or_id)
        if not invite:
            return False
        if actor_id:
            if actor_id != invite.created_by and not self.has_community_permission(invite.community_id, actor_id, "manage_roles"):
                raise PermissionError("Actor does not have permission to revoke this invite")

        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE community_invites SET is_active = 0 WHERE id = ? OR token = ?",
                (invite.id, invite.token)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def revoke_community_invite(self, *args, **kwargs) -> bool:
        return self.revoke_invite(*args, **kwargs)

    def use_invite(self, token: str, user_id: str) -> bool:
        invite = self.get_invite(token)
        if not invite or not invite.is_valid:
            return False
        if self.is_user_banned(invite.community_id, user_id):
            return False

        now_str = datetime.utcnow().isoformat()
        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO community_members (community_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                (invite.community_id, user_id, invite.role, now_str)
            )
            new_uses = invite.uses_count + 1
            new_active = 1
            if invite.max_uses is not None and new_uses >= invite.max_uses:
                new_active = 0
            conn.execute(
                "UPDATE community_invites SET uses_count = ?, is_active = ? WHERE id = ?",
                (new_uses, new_active, invite.id)
            )
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def join_with_invite(self, token: str, user_id: str) -> bool:
        return self.use_invite(token, user_id)

    def join_community_with_invite(self, token: str, user_id: str) -> bool:
        return self.use_invite(token, user_id)

    # --- Topic Channels ---
    def create_channel(self, channel: Channel, creator_id: Optional[str] = None) -> None:
        if creator_id:
            if not self.has_community_permission(channel.community_id, creator_id, "manage_channels"):
                raise PermissionError("User does not have permission to create channels in this community")
        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT INTO channels (id, community_id, name, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (channel.id, channel.community_id, channel.name, channel.description, channel.created_at.isoformat())
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
            if row:
                return Channel(
                    id=row["id"],
                    community_id=row["community_id"],
                    name=row["name"],
                    description=row["description"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_community_channels(self, community_id: str) -> List[Channel]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM channels WHERE community_id = ? ORDER BY created_at ASC",
                (community_id,)
            ).fetchall()
            return [
                Channel(
                    id=r["id"],
                    community_id=r["community_id"],
                    name=r["name"],
                    description=r["description"],
                    created_at=datetime.fromisoformat(r["created_at"])
                ) for r in rows
            ]
        finally:
            if not self._memory_conn: conn.close()

    # --- Row Helpers ---
    def _row_to_moderation_report(self, r) -> ModerationReport:
        rep_ids = r["reporter_ids"] if "reporter_ids" in r.keys() and r["reporter_ids"] else "[]"
        if isinstance(rep_ids, str):
            try:
                rep_ids_list = json.loads(rep_ids)
            except Exception:
                rep_ids_list = [x.strip() for x in rep_ids.split(",") if x.strip()]
        elif isinstance(rep_ids, list):
            rep_ids_list = rep_ids
        else:
            rep_ids_list = []
        if not rep_ids_list and r["reporter_id"]:
            rep_ids_list = [r["reporter_id"]]

        reasons_val = r["reasons"] if "reasons" in r.keys() and r["reasons"] else "[]"
        if isinstance(reasons_val, str):
            try:
                reasons_list = json.loads(reasons_val)
            except Exception:
                reasons_list = [x.strip() for x in reasons_val.split(",") if x.strip()]
        elif isinstance(reasons_val, list):
            reasons_list = reasons_val
        else:
            reasons_list = []
        if not reasons_list and r["reason"]:
            reasons_list = [r["reason"]]

        resolved_at = None
        if "resolved_at" in r.keys() and r["resolved_at"]:
            try:
                resolved_at = datetime.fromisoformat(r["resolved_at"])
            except Exception:
                resolved_at = None

        return ModerationReport(
            id=r["id"],
            reporter_id=r["reporter_id"],
            target_type=r["target_type"],
            target_id=r["target_id"],
            reason=r["reason"],
            category=r["category"] if "category" in r.keys() and r["category"] else "other",
            status=r["status"],
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
            report_count=r["report_count"] if "report_count" in r.keys() and r["report_count"] is not None else 1,
            reporter_ids=rep_ids_list,
            reasons=reasons_list,
            details=r["details"] if "details" in r.keys() and r["details"] is not None else "",
            action_taken=r["action_taken"] if "action_taken" in r.keys() else None,
            resolved_by=r["resolved_by"] if "resolved_by" in r.keys() else None,
            resolved_at=resolved_at
        )

    def _row_to_moderation_appeal(self, r) -> ModerationAppeal:
        reviewed_at = None
        if "reviewed_at" in r.keys() and r["reviewed_at"]:
            try:
                reviewed_at = datetime.fromisoformat(r["reviewed_at"])
            except Exception:
                reviewed_at = None

        return ModerationAppeal(
            id=r["id"],
            report_id=r["report_id"] if "report_id" in r.keys() else None,
            target_type=r["target_type"] if "target_type" in r.keys() else "",
            target_id=r["target_id"] if "target_id" in r.keys() else "",
            appellant_id=r["appellant_id"],
            reason=r["reason"],
            status=r["status"],
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
            reviewed_by=r["reviewed_by"] if "reviewed_by" in r.keys() else None,
            reviewed_at=reviewed_at,
            notes=r["notes"] if "notes" in r.keys() and r["notes"] is not None else "",
            action_taken=r["action_taken"] if "action_taken" in r.keys() else None
        )

    def _row_to_lifecycle_event(self, r) -> ContentLifecycleEvent:
        meta_val = r["metadata"] if "metadata" in r.keys() and r["metadata"] else "{}"
        if isinstance(meta_val, str):
            try:
                meta_dict = json.loads(meta_val)
            except Exception:
                meta_dict = {}
        elif isinstance(meta_val, dict):
            meta_dict = meta_val
        else:
            meta_dict = {}

        return ContentLifecycleEvent(
            id=r["id"],
            target_type=r["target_type"] if "target_type" in r.keys() else "discussion",
            target_id=r["target_id"],
            event_type=r["event_type"],
            actor_id=r["actor_id"],
            previous_state=r["previous_state"] if "previous_state" in r.keys() else None,
            new_state=r["new_state"] if "new_state" in r.keys() else None,
            reason=r["reason"] if "reason" in r.keys() else None,
            metadata=meta_dict,
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
        )

    def _row_to_interaction(self, r) -> ContentInteraction:
        meta_val = r["metadata"] if "metadata" in r.keys() and r["metadata"] else "{}"
        if isinstance(meta_val, str):
            try:
                meta_dict = json.loads(meta_val)
            except Exception:
                meta_dict = {}
        elif isinstance(meta_val, dict):
            meta_dict = meta_val
        else:
            meta_dict = {}

        return ContentInteraction(
            id=r["id"],
            target_type=r["target_type"] if "target_type" in r.keys() else "discussion",
            target_id=r["target_id"],
            user_id=r["user_id"],
            interaction_type=r["interaction_type"],
            metadata=meta_dict,
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
        )

    # --- Moderation Controls & Content Reporting Queue ---
    def create_moderation_report(self, report: ModerationReport, consolidate: bool = True) -> ModerationReport:
        conn = self.get_connection()
        try:
            if consolidate:
                existing_row = conn.execute(
                    "SELECT * FROM moderation_reports WHERE target_type = ? AND target_id = ? AND status = 'pending' ORDER BY created_at ASC LIMIT 1",
                    (report.target_type, report.target_id)
                ).fetchone()
                if existing_row:
                    existing_id = existing_row["id"]
                    rep_ids_raw = existing_row["reporter_ids"] if "reporter_ids" in existing_row.keys() and existing_row["reporter_ids"] else "[]"
                    try:
                        existing_rep_ids = json.loads(rep_ids_raw) if isinstance(rep_ids_raw, str) else list(rep_ids_raw)
                    except Exception:
                        existing_rep_ids = [r.strip() for r in rep_ids_raw.split(",") if r.strip()]
                    if not existing_rep_ids and existing_row["reporter_id"]:
                        existing_rep_ids = [existing_row["reporter_id"]]

                    reasons_raw = existing_row["reasons"] if "reasons" in existing_row.keys() and existing_row["reasons"] else "[]"
                    try:
                        existing_reasons = json.loads(reasons_raw) if isinstance(reasons_raw, str) else list(reasons_raw)
                    except Exception:
                        existing_reasons = [r.strip() for r in reasons_raw.split(",") if r.strip()]
                    if not existing_reasons and existing_row["reason"]:
                        existing_reasons = [existing_row["reason"]]

                    existing_count = existing_row["report_count"] if "report_count" in existing_row.keys() and existing_row["report_count"] is not None else 1

                    new_count = existing_count
                    if report.reporter_id and report.reporter_id not in existing_rep_ids:
                        existing_rep_ids.append(report.reporter_id)
                        new_count = existing_count + 1
                    if getattr(report, "reporter_ids", None):
                        for rid in report.reporter_ids:
                            if rid not in existing_rep_ids:
                                existing_rep_ids.append(rid)
                                new_count = max(new_count, len(existing_rep_ids))

                    if report.reason and report.reason not in existing_reasons:
                        existing_reasons.append(report.reason)
                    if getattr(report, "reasons", None):
                        for r in report.reasons:
                            if r not in existing_reasons:
                                existing_reasons.append(r)

                    category_val = existing_row["category"] if "category" in existing_row.keys() and existing_row["category"] and existing_row["category"] != "other" else (getattr(report, "category", "other") or "other")

                    conn.execute(
                        """UPDATE moderation_reports
                           SET report_count = ?, reporter_ids = ?, reasons = ?, category = ?
                           WHERE id = ?""",
                        (new_count, json.dumps(existing_rep_ids), json.dumps(existing_reasons), category_val, existing_id)
                    )
                    conn.commit()
                    updated_row = conn.execute("SELECT * FROM moderation_reports WHERE id = ?", (existing_id,)).fetchone()
                    return self._row_to_moderation_report(updated_row)

            rep_ids = report.reporter_ids if getattr(report, "reporter_ids", None) else ([report.reporter_id] if report.reporter_id else [])
            reasons = report.reasons if getattr(report, "reasons", None) else ([report.reason] if report.reason else [])
            rep_count = getattr(report, "report_count", 1) or len(rep_ids) or 1

            conn.execute(
                """INSERT INTO moderation_reports (
                    id, reporter_id, target_type, target_id, reason, category, status,
                    report_count, reporter_ids, reasons, details, action_taken, resolved_by, resolved_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report.id, report.reporter_id, report.target_type, report.target_id,
                    report.reason, getattr(report, "category", "other") or "other",
                    getattr(report, "status", "pending") or "pending",
                    rep_count, json.dumps(rep_ids), json.dumps(reasons),
                    getattr(report, "details", "") or "",
                    getattr(report, "action_taken", None),
                    getattr(report, "resolved_by", None),
                    report.resolved_at.isoformat() if getattr(report, "resolved_at", None) else None,
                    report.created_at.isoformat() if isinstance(report.created_at, datetime) else str(report.created_at)
                )
            )
            conn.commit()
            return report
        finally:
            if not self._memory_conn: conn.close()

    def create_content_report(
        self,
        reporter_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        category: str = "other",
        details: str = "",
        report_id: Optional[str] = None,
        consolidate: bool = True
    ) -> ModerationReport:
        normalized_target_type = target_type.lower().strip()
        if normalized_target_type in ("discussion", "reply", "comment"):
            disc = self.get_discussion(target_id)
            if not disc:
                raise ValueError(f"Target discussion or reply '{target_id}' not found")
        elif normalized_target_type in ("message", "direct_message", "dm"):
            dm = self.get_direct_message(target_id)
            if not dm:
                raise ValueError(f"Target message '{target_id}' not found")
            normalized_target_type = "message"
        elif normalized_target_type == "user":
            u = self.get_user(target_id)
            if not u:
                raise ValueError(f"Target user '{target_id}' not found")

        cat = category.lower().strip() if category else "other"
        rid = report_id or str(uuid.uuid4())
        report = ModerationReport(
            id=rid,
            reporter_id=reporter_id,
            target_type=normalized_target_type,
            target_id=target_id,
            reason=reason,
            category=cat or "other",
            details=details,
            report_count=1,
            reporter_ids=[reporter_id] if reporter_id else [],
            reasons=[reason] if reason else []
        )
        return self.create_moderation_report(report, consolidate=consolidate)

    def get_moderation_report(self, report_id: str) -> Optional[ModerationReport]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM moderation_reports WHERE id = ?", (report_id,)).fetchone()
            if row:
                return self._row_to_moderation_report(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_content_report(self, report_id: str) -> Optional[ModerationReport]:
        return self.get_moderation_report(report_id)

    def get_moderation_reports(
        self,
        status: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        reporter_id: Optional[str] = None,
        category: Optional[str] = None,
        order_by: Optional[str] = None
    ) -> List[ModerationReport]:
        conn = self.get_connection()
        try:
            query = "SELECT * FROM moderation_reports WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if target_type:
                if target_type in ("message", "direct_message", "dm"):
                    query += " AND target_type IN ('message', 'direct_message', 'dm')"
                else:
                    query += " AND target_type = ?"
                    params.append(target_type)
            if target_id:
                query += " AND target_id = ?"
                params.append(target_id)
            if reporter_id:
                query += " AND (reporter_id = ? OR reporter_ids LIKE ?)"
                params.append(reporter_id)
                params.append(f'%"{reporter_id}"%')
            if category:
                query += " AND category = ?"
                params.append(category)

            if order_by in ("priority", "count"):
                query += " ORDER BY report_count DESC, created_at ASC"
            else:
                query += " ORDER BY created_at DESC"

            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_moderation_report(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_content_reporting_queue(
        self,
        status: str = "pending",
        target_type: Optional[str] = None,
        category: Optional[str] = None,
        order_by: str = "priority"
    ) -> List[ModerationReport]:
        return self.get_moderation_reports(
            status=status,
            target_type=target_type,
            category=category,
            order_by=order_by
        )

    def resolve_moderation_report(
        self,
        report_id: str,
        status: str = "resolved",
        action_taken: Optional[str] = None,
        resolved_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        conn = self.get_connection()
        try:
            now_str = datetime.utcnow().isoformat()
            cursor = conn.execute(
                """UPDATE moderation_reports
                   SET status = ?, action_taken = COALESCE(?, action_taken),
                       resolved_by = COALESCE(?, resolved_by), resolved_at = ?,
                       details = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE details END
                   WHERE id = ?""",
                (status, action_taken, resolved_by, now_str, notes, notes, notes, report_id)
            )
            conn.commit()
            if cursor.rowcount > 0:
                if action_taken in ("hide", "hide_content"):
                    rep = self.get_moderation_report(report_id)
                    if rep and rep.target_type in ("discussion", "reply"):
                        self.hide_discussion(rep.target_id)
                return True
            return False
        finally:
            if not self._memory_conn: conn.close()

    def dismiss_moderation_report(self, report_id: str, dismissed_by: Optional[str] = None, notes: Optional[str] = None) -> bool:
        return self.resolve_moderation_report(report_id, status="dismissed", resolved_by=dismissed_by, notes=notes)

    def action_moderation_report(self, report_id: str, action: str, actor_id: Optional[str] = None, notes: Optional[str] = None) -> bool:
        rep = self.get_moderation_report(report_id)
        if not rep:
            return False
        if action in ("hide", "hide_content") and rep.target_type in ("discussion", "reply"):
            self.hide_discussion(rep.target_id)
        return self.resolve_moderation_report(report_id, status="actioned", action_taken=action, resolved_by=actor_id, notes=notes)

    # --- Moderation Appeals Workflow ---
    def submit_moderation_appeal(
        self,
        target_type: str,
        target_id: str,
        appellant_id: str,
        reason: str,
        report_id: Optional[str] = None,
        appeal_id: Optional[str] = None,
        notes: str = ""
    ) -> ModerationAppeal:
        aid = appeal_id or str(uuid.uuid4())
        normalized_target_type = target_type.lower().strip()
        if normalized_target_type in ("message", "direct_message", "dm"):
            normalized_target_type = "message"

        appeal = ModerationAppeal(
            id=aid,
            report_id=report_id,
            target_type=normalized_target_type,
            target_id=target_id,
            appellant_id=appellant_id,
            reason=reason,
            status="pending",
            notes=notes,
            created_at=datetime.utcnow()
        )
        return self.create_moderation_appeal(appeal)

    def create_moderation_appeal(self, appeal: ModerationAppeal) -> ModerationAppeal:
        conn = self.get_connection()
        try:
            conn.execute(
                """INSERT INTO moderation_appeals (
                    id, report_id, target_type, target_id, appellant_id, reason,
                    status, reviewed_by, reviewed_at, notes, action_taken, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    appeal.id, appeal.report_id, appeal.target_type, appeal.target_id,
                    appeal.appellant_id, appeal.reason, appeal.status, appeal.reviewed_by,
                    appeal.reviewed_at.isoformat() if appeal.reviewed_at else None,
                    appeal.notes or "", appeal.action_taken,
                    appeal.created_at.isoformat() if isinstance(appeal.created_at, datetime) else str(appeal.created_at)
                )
            )
            conn.commit()
            return appeal
        finally:
            if not self._memory_conn: conn.close()

    def get_moderation_appeal(self, appeal_id: str) -> Optional[ModerationAppeal]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM moderation_appeals WHERE id = ?", (appeal_id,)).fetchone()
            if row:
                return self._row_to_moderation_appeal(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_content_appeal(self, appeal_id: str) -> Optional[ModerationAppeal]:
        return self.get_moderation_appeal(appeal_id)

    def get_moderation_appeals(
        self,
        status: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        appellant_id: Optional[str] = None,
        report_id: Optional[str] = None
    ) -> List[ModerationAppeal]:
        conn = self.get_connection()
        try:
            query = "SELECT * FROM moderation_appeals WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if target_type:
                if target_type in ("message", "direct_message", "dm"):
                    query += " AND target_type IN ('message', 'direct_message', 'dm')"
                else:
                    query += " AND target_type = ?"
                    params.append(target_type)
            if target_id:
                query += " AND target_id = ?"
                params.append(target_id)
            if appellant_id:
                query += " AND appellant_id = ?"
                params.append(appellant_id)
            if report_id:
                query += " AND report_id = ?"
                params.append(report_id)

            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_moderation_appeal(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_moderation_appeals_queue(self, status: str = "pending") -> List[ModerationAppeal]:
        return self.get_moderation_appeals(status=status)

    # =========================================================================
    # --- Content Lifecycle Management (Create -> Interact -> Report -> Moderate -> Appeal -> Remove) ---
    # =========================================================================

    def record_lifecycle_event(
        self,
        target_type: str,
        target_id: str,
        event_type: str,
        actor_id: str,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContentLifecycleEvent:
        eid = str(uuid.uuid4())
        created_at = datetime.utcnow()
        meta_json = json.dumps(metadata or {})
        conn = self.get_connection()
        try:
            conn.execute(
                """INSERT INTO content_lifecycle_events (
                    id, target_type, target_id, event_type, actor_id, previous_state, new_state, reason, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    eid, target_type, target_id, event_type, actor_id,
                    previous_state, new_state, reason, meta_json, created_at.isoformat()
                )
            )
            conn.commit()
            return ContentLifecycleEvent(
                id=eid,
                target_type=target_type,
                target_id=target_id,
                event_type=event_type,
                actor_id=actor_id,
                previous_state=previous_state,
                new_state=new_state,
                reason=reason,
                metadata=metadata or {},
                created_at=created_at
            )
        finally:
            if not self._memory_conn: conn.close()

    def get_content_lifecycle_events(self, target_type: str, target_id: str) -> List[ContentLifecycleEvent]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM content_lifecycle_events WHERE target_type = ? AND target_id = ? ORDER BY created_at ASC",
                (target_type, target_id)
            ).fetchall()
            return [self._row_to_lifecycle_event(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_discussion_events(self, discussion_id: str) -> List[ContentLifecycleEvent]:
        return self.get_content_lifecycle_events("discussion", discussion_id)

    def can_interact_with_discussion(self, discussion_id: str, user_id: str, action: str = "interact") -> bool:
        disc = self.get_discussion(discussion_id)
        if not disc:
            return False
        if disc.is_removed or disc.status in ("removed", "deleted") or disc.deleted_at is not None:
            return False
        if not self.is_user_active(user_id):
            return False
        if self.are_users_blocked(disc.author_id, user_id):
            return False
        if disc.community_id and self.is_user_banned(disc.community_id, user_id):
            return False
        if not self.can_user_view_discussion(user_id, disc):
            return False
        return True

    def interact_with_discussion(
        self,
        discussion_id: str,
        actor_id: Optional[str] = None,
        action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        interaction_type: Optional[str] = None,
        **kwargs
    ) -> ContentInteraction:
        effective_actor = actor_id or user_id
        effective_action = action or interaction_type or "endorse"
        if not effective_actor:
            raise ValueError("actor_id or user_id required for interaction")

        disc = self.get_discussion(discussion_id)
        if not disc:
            raise ValueError(f"Discussion {discussion_id} not found")
        if disc.is_removed or disc.status in ("removed", "deleted") or disc.deleted_at is not None:
            raise ValueError("Cannot interact with removed content")
        if not self.can_interact_with_discussion(discussion_id, effective_actor, action=effective_action):
            raise PermissionError(f"User {effective_actor} is not permitted to interact with discussion {discussion_id}")

        iid = str(uuid.uuid4())
        now = datetime.utcnow()
        now_str = now.isoformat()
        meta_json = json.dumps(metadata or {})

        conn = self.get_connection()
        try:
            conn.execute(
                """INSERT INTO content_interactions (
                    id, target_type, target_id, user_id, interaction_type, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (iid, "discussion", discussion_id, effective_actor, effective_action, meta_json, now_str)
            )
            conn.execute(
                """UPDATE discussions
                   SET last_interacted_at = ?, interaction_count = interaction_count + 1
                   WHERE id = ?""",
                (now_str, discussion_id)
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        if effective_action in ("endorse", "value_endorsement", "like"):
            self.endorse_discussion(discussion_id, actor_id=effective_actor)

        self.record_lifecycle_event(
            target_type="discussion",
            target_id=discussion_id,
            event_type="interact",
            actor_id=effective_actor,
            previous_state=disc.status,
            new_state=disc.status,
            reason=effective_action,
            metadata=metadata or {"action": effective_action}
        )
        return ContentInteraction(
            id=iid,
            target_type="discussion",
            target_id=discussion_id,
            user_id=effective_actor,
            interaction_type=effective_action,
            metadata=metadata or {},
            created_at=now
        )

    def get_content_interactions(self, target_type: str, target_id: str) -> List[ContentInteraction]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM content_interactions WHERE target_type = ? AND target_id = ? ORDER BY created_at DESC",
                (target_type, target_id)
            ).fetchall()
            return [self._row_to_interaction(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_discussion_interactions(self, discussion_id: str) -> List[ContentInteraction]:
        return self.get_content_interactions("discussion", discussion_id)

    def report_content(
        self,
        reporter_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        category: str = "other",
        details: str = "",
        report_id: Optional[str] = None,
        consolidate: bool = True
    ) -> ModerationReport:
        rep = self.create_content_report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            category=category,
            details=details,
            report_id=report_id,
            consolidate=consolidate
        )
        normalized_target_type = target_type.lower().strip()
        if normalized_target_type in ("discussion", "reply", "comment"):
            disc = self.get_discussion(target_id)
            if disc:
                conn = self.get_connection()
                try:
                    conn.execute(
                        """UPDATE discussions
                           SET report_count = report_count + 1,
                               moderation_status = CASE WHEN moderation_status = 'none' THEN 'reported' ELSE moderation_status END
                           WHERE id = ?""",
                        (target_id,)
                    )
                    conn.commit()
                finally:
                    if not self._memory_conn: conn.close()

                self.record_lifecycle_event(
                    target_type="discussion",
                    target_id=target_id,
                    event_type="report",
                    actor_id=reporter_id,
                    previous_state=disc.status,
                    new_state="reported",
                    reason=reason,
                    metadata={"category": category, "report_id": rep.id}
                )
        return rep

    def report_discussion(
        self,
        discussion_id: str,
        reporter_id: str,
        reason: str,
        category: str = "other",
        details: str = "",
        report_id: Optional[str] = None
    ) -> ModerationReport:
        return self.report_content(
            reporter_id=reporter_id,
            target_type="discussion",
            target_id=discussion_id,
            reason=reason,
            category=category,
            details=details,
            report_id=report_id
        )

    def get_content_reports(self, target_type: str, target_id: str) -> List[ModerationReport]:
        return self.get_moderation_reports(target_type=target_type, target_id=target_id)

    def get_discussion_reports(self, discussion_id: str) -> List[ModerationReport]:
        return self.get_moderation_reports(target_type="discussion", target_id=discussion_id)

    def moderate_content(
        self,
        target_type: str,
        target_id: str,
        action: str,
        moderator_id: Optional[str] = None,
        reason: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        normalized_target_type = target_type.lower().strip()
        norm_action = action.lower().strip()
        now_str = datetime.utcnow().isoformat()

        if normalized_target_type in ("discussion", "reply"):
            disc = self.get_discussion(target_id)
            if not disc:
                return False

            if norm_action in ("hide", "quarantine", "hidden", "flag", "quarantined"):
                new_status = "quarantined" if norm_action in ("quarantine", "quarantined") else "hidden"
                conn = self.get_connection()
                try:
                    conn.execute(
                        """UPDATE discussions
                           SET is_hidden = 1, status = ?, moderation_status = ?,
                               moderated_by = ?, moderated_at = ?, moderation_action = ?, moderation_reason = ?
                           WHERE id = ?""",
                        (new_status, norm_action, moderator_id, now_str, norm_action, reason, target_id)
                    )
                    conn.commit()
                finally:
                    if not self._memory_conn: conn.close()

                self.record_lifecycle_event(
                    target_type="discussion",
                    target_id=target_id,
                    event_type="moderate",
                    actor_id=moderator_id or "system",
                    previous_state=disc.status,
                    new_state=new_status,
                    reason=reason,
                    metadata={"action": norm_action, "notes": notes}
                )
                return True

            elif norm_action in ("remove", "removed", "delete"):
                return self.remove_discussion(target_id, actor_id=moderator_id, reason=reason, soft_delete=True)

            elif norm_action in ("approve", "unhide", "restore", "active"):
                conn = self.get_connection()
                try:
                    conn.execute(
                        """UPDATE discussions
                           SET is_hidden = 0, status = 'active', moderation_status = 'approved',
                               moderated_by = ?, moderated_at = ?, moderation_action = ?, moderation_reason = ?,
                               deleted_at = NULL, deleted_by = NULL, removal_reason = NULL
                           WHERE id = ?""",
                        (moderator_id, now_str, norm_action, reason, target_id)
                    )
                    conn.commit()
                finally:
                    if not self._memory_conn: conn.close()

                self.record_lifecycle_event(
                    target_type="discussion",
                    target_id=target_id,
                    event_type="moderate",
                    actor_id=moderator_id or "system",
                    previous_state=disc.status,
                    new_state="active",
                    reason=reason,
                    metadata={"action": norm_action, "notes": notes}
                )
                return True
        return False

    def moderate_discussion(
        self,
        discussion_id: str,
        action: str = "hide",
        moderator_id: Optional[str] = None,
        reason: Optional[str] = None,
        notes: Optional[str] = None,
        actor_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        effective_mod = moderator_id or actor_id
        return self.moderate_content(
            "discussion", discussion_id, action=action, moderator_id=effective_mod, reason=reason, notes=notes
        )

    def appeal_content(
        self,
        target_type: str,
        target_id: str,
        appellant_id: str,
        reason: str,
        notes: str = "",
        report_id: Optional[str] = None,
        appeal_id: Optional[str] = None
    ) -> ModerationAppeal:
        appeal = self.submit_moderation_appeal(
            target_type=target_type,
            target_id=target_id,
            appellant_id=appellant_id,
            reason=reason,
            report_id=report_id,
            appeal_id=appeal_id,
            notes=notes
        )
        normalized_target_type = target_type.lower().strip()
        if normalized_target_type in ("discussion", "reply"):
            disc = self.get_discussion(target_id)
            if disc:
                conn = self.get_connection()
                try:
                    conn.execute(
                        "UPDATE discussions SET status = 'appealed', moderation_status = 'under_appeal' WHERE id = ?",
                        (target_id,)
                    )
                    conn.commit()
                finally:
                    if not self._memory_conn: conn.close()

                self.record_lifecycle_event(
                    target_type="discussion",
                    target_id=target_id,
                    event_type="appeal",
                    actor_id=appellant_id,
                    previous_state=disc.status,
                    new_state="appealed",
                    reason=reason,
                    metadata={"appeal_id": appeal.id, "report_id": report_id}
                )
        return appeal

    def appeal_discussion(
        self,
        discussion_id: str,
        appellant_id: str,
        reason: str,
        notes: str = "",
        report_id: Optional[str] = None,
        appeal_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> ModerationAppeal:
        effective_appellant = appellant_id or user_id
        return self.appeal_content(
            "discussion", discussion_id, appellant_id=effective_appellant,
            reason=reason, notes=notes, report_id=report_id, appeal_id=appeal_id
        )

    def get_content_appeals(self, target_type: str, target_id: str) -> List[ModerationAppeal]:
        return self.get_moderation_appeals(target_type=target_type, target_id=target_id)

    def get_discussion_appeals(self, discussion_id: str) -> List[ModerationAppeal]:
        return self.get_moderation_appeals(target_type="discussion", target_id=discussion_id)

    def review_content_appeal(
        self,
        appeal_id: str,
        status: str = "approved",
        reviewed_by: Optional[str] = None,
        notes: Optional[str] = None,
        action_taken: Optional[str] = None,
        decision: Optional[str] = None,
        moderator_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        norm_status = (decision or status or "approved").lower().strip()
        effective_reviewer = reviewed_by or moderator_id
        if norm_status in ("grant", "granted", "accept", "accepted"):
            norm_status = "approved"
        elif norm_status in ("deny", "denied"):
            norm_status = "rejected"

        appeal = self.get_moderation_appeal(appeal_id)
        if not appeal:
            return False

        now_str = datetime.utcnow().isoformat()
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """UPDATE moderation_appeals
                   SET status = ?, reviewed_by = ?, reviewed_at = ?,
                       notes = COALESCE(?, notes), action_taken = COALESCE(?, action_taken)
                   WHERE id = ?""",
                (norm_status, effective_reviewer, now_str, notes, action_taken or norm_status, appeal_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                return False
        finally:
            if not self._memory_conn: conn.close()

        target_type = appeal.target_type.lower().strip()
        target_id = appeal.target_id
        if target_type in ("discussion", "reply"):
            disc = self.get_discussion(target_id)
            if disc:
                if norm_status in ("approved", "resolved"):
                    conn = self.get_connection()
                    try:
                        conn.execute(
                            """UPDATE discussions
                               SET is_hidden = 0, status = 'active', moderation_status = 'approved',
                                   moderated_by = ?, moderated_at = ?, moderation_action = 'restored_on_appeal',
                                   deleted_at = NULL, deleted_by = NULL, removal_reason = NULL
                               WHERE id = ?""",
                            (effective_reviewer, now_str, target_id)
                        )
                        conn.commit()
                    finally:
                        if not self._memory_conn: conn.close()

                    self.record_lifecycle_event(
                        target_type="discussion",
                        target_id=target_id,
                        event_type="appeal_approved",
                        actor_id=effective_reviewer or "moderator",
                        previous_state=disc.status,
                        new_state="active",
                        reason=notes or "Appeal approved and content restored",
                        metadata={"appeal_id": appeal_id}
                    )
                elif norm_status == "rejected":
                    new_st = "removed" if (disc.deleted_at is not None or disc.status == "removed") else "moderated"
                    conn = self.get_connection()
                    try:
                        conn.execute(
                            """UPDATE discussions
                               SET is_hidden = 1, status = ?, moderation_status = 'appeal_rejected',
                                   moderated_by = ?, moderated_at = ?
                               WHERE id = ?""",
                            (new_st, effective_reviewer, now_str, target_id)
                        )
                        conn.commit()
                    finally:
                        if not self._memory_conn: conn.close()

                    self.record_lifecycle_event(
                        target_type="discussion",
                        target_id=target_id,
                        event_type="appeal_rejected",
                        actor_id=effective_reviewer or "moderator",
                        previous_state=disc.status,
                        new_state=new_st,
                        reason=notes or "Appeal rejected",
                        metadata={"appeal_id": appeal_id}
                    )
        return True

    def resolve_content_appeal(
        self,
        appeal_id: str,
        status: str = "approved",
        reviewed_by: Optional[str] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> bool:
        return self.review_content_appeal(appeal_id, status=status, reviewed_by=reviewed_by, notes=notes, **kwargs)

    def review_moderation_appeal(
        self,
        appeal_id: str,
        status: str = "approved",
        reviewed_by: Optional[str] = None,
        notes: Optional[str] = None,
        action_taken: Optional[str] = None,
        **kwargs
    ) -> bool:
        return self.review_content_appeal(appeal_id, status=status, reviewed_by=reviewed_by, notes=notes, action_taken=action_taken, **kwargs)

    def resolve_moderation_appeal(
        self,
        appeal_id: str,
        status: str = "approved",
        reviewed_by: Optional[str] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> bool:
        return self.review_content_appeal(appeal_id, status=status, reviewed_by=reviewed_by, notes=notes, **kwargs)

    def remove_discussion(
        self,
        discussion_id: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
        soft_delete: bool = True,
        hard_delete: bool = False,
        deleted_by: Optional[str] = None,
        removal_reason: Optional[str] = None,
        **kwargs
    ) -> bool:
        effective_actor = actor_id or deleted_by
        effective_reason = reason or removal_reason
        if hard_delete:
            soft_delete = False

        disc = self.get_discussion(discussion_id)
        if not disc:
            return False

        now_str = datetime.utcnow().isoformat()
        conn = self.get_connection()
        try:
            if soft_delete:
                cursor = conn.execute(
                    """UPDATE discussions
                       SET is_hidden = 1, status = 'removed', moderation_status = 'removed',
                           deleted_at = ?, deleted_by = ?, removal_reason = ?
                       WHERE id = ?""",
                    (now_str, effective_actor, effective_reason, discussion_id)
                )
                conn.commit()
                success = cursor.rowcount > 0
                event_type = "remove"
            else:
                cursor = conn.execute("DELETE FROM discussions WHERE id = ?", (discussion_id,))
                conn.execute("DELETE FROM discussion_tags WHERE discussion_id = ?", (discussion_id,))
                conn.execute("DELETE FROM media_attachments WHERE discussion_id = ?", (discussion_id,))
                conn.commit()
                success = cursor.rowcount > 0
                event_type = "delete"
        finally:
            if not self._memory_conn: conn.close()

        if success:
            self.record_lifecycle_event(
                target_type="discussion",
                target_id=discussion_id,
                event_type=event_type,
                actor_id=effective_actor or "user",
                previous_state=disc.status,
                new_state="removed" if soft_delete else "deleted",
                reason=effective_reason,
                metadata={"soft_delete": soft_delete}
            )
        return success

    def delete_discussion(
        self,
        discussion_id: str,
        actor_id: Optional[str] = None,
        permanent: bool = False,
        reason: Optional[str] = None,
        **kwargs
    ) -> bool:
        return self.remove_discussion(discussion_id, actor_id=actor_id, reason=reason, soft_delete=not permanent, **kwargs)

    def restore_discussion(
        self,
        discussion_id: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> bool:
        disc = self.get_discussion(discussion_id)
        if not disc:
            return False

        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """UPDATE discussions
                   SET is_hidden = 0, status = 'active', moderation_status = 'restored',
                       deleted_at = NULL, deleted_by = NULL, removal_reason = NULL
                   WHERE id = ?""",
                (discussion_id,)
            )
            conn.commit()
            success = cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

        if success:
            self.record_lifecycle_event(
                target_type="discussion",
                target_id=discussion_id,
                event_type="restore",
                actor_id=actor_id or "moderator",
                previous_state=disc.status,
                new_state="active",
                reason=reason or "Content restored"
            )
        return success

    def remove_content(
        self,
        target_type: str,
        target_id: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
        soft_delete: bool = True,
        **kwargs
    ) -> bool:
        if target_type.lower().strip() in ("discussion", "reply", "comment"):
            return self.remove_discussion(target_id, actor_id=actor_id, reason=reason, soft_delete=soft_delete, **kwargs)
        return False

    def restore_content(
        self,
        target_type: str,
        target_id: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> bool:
        if target_type.lower().strip() in ("discussion", "reply", "comment"):
            return self.restore_discussion(target_id, actor_id=actor_id, reason=reason, **kwargs)
        return False

    def hide_discussion(self, discussion_id: str, actor_id: Optional[str] = None, reason: Optional[str] = None) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE discussions SET is_hidden = 1, status = 'hidden', moderation_status = 'hidden' WHERE id = ?",
                (discussion_id,)
            )
            conn.commit()
            success = cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

        if success:
            try:
                self.record_lifecycle_event(
                    target_type="discussion",
                    target_id=discussion_id,
                    event_type="moderate",
                    actor_id=actor_id or "moderator",
                    new_state="hidden",
                    reason=reason
                )
            except Exception:
                pass
        return success

    def unhide_discussion(self, discussion_id: str, actor_id: Optional[str] = None, reason: Optional[str] = None) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE discussions SET is_hidden = 0, status = 'active', moderation_status = 'approved' WHERE id = ?",
                (discussion_id,)
            )
            conn.commit()
            success = cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

        if success:
            try:
                self.record_lifecycle_event(
                    target_type="discussion",
                    target_id=discussion_id,
                    event_type="moderate",
                    actor_id=actor_id or "moderator",
                    new_state="active",
                    reason=reason
                )
            except Exception:
                pass
        return success

    def get_discussion_lifecycle(self, discussion_id: str) -> Optional[Dict[str, Any]]:
        disc = self.get_discussion(discussion_id)
        if not disc:
            return None
        events = self.get_discussion_events(discussion_id)
        reports = self.get_discussion_reports(discussion_id)
        appeals = self.get_discussion_appeals(discussion_id)
        interactions = self.get_discussion_interactions(discussion_id)

        return {
            "id": disc.id,
            "author_id": disc.author_id,
            "status": disc.status,
            "lifecycle_state": disc.lifecycle_state,
            "moderation_status": disc.moderation_status,
            "is_hidden": disc.is_hidden,
            "is_active": disc.is_active,
            "is_removed": disc.is_removed,
            "is_moderated": disc.is_moderated,
            "is_appealed": disc.is_appealed,
            "value_endorsements": disc.value_endorsements,
            "interaction_count": disc.interaction_count,
            "report_count": disc.report_count,
            "created_at": disc.created_at.isoformat() if isinstance(disc.created_at, datetime) else str(disc.created_at),
            "moderated_at": disc.moderated_at.isoformat() if disc.moderated_at else None,
            "moderated_by": disc.moderated_by,
            "moderation_action": disc.moderation_action,
            "moderation_reason": disc.moderation_reason,
            "deleted_at": disc.deleted_at.isoformat() if disc.deleted_at else None,
            "deleted_by": disc.deleted_by,
            "removal_reason": disc.removal_reason,
            "last_interacted_at": disc.last_interacted_at.isoformat() if disc.last_interacted_at else None,
            "reports_count": len(reports),
            "appeals_count": len(appeals),
            "events_count": len(events),
            "reports": [r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reports],
            "appeals": [a.to_dict() if hasattr(a, "to_dict") else a.__dict__ for a in appeals],
            "events": [e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in events],
            "interactions": [i.to_dict() if hasattr(i, "to_dict") else i.__dict__ for i in interactions]
        }

    def get_content_lifecycle(self, target_type: str, target_id: str) -> Optional[Dict[str, Any]]:
        if target_type.lower().strip() in ("discussion", "reply", "comment"):
            return self.get_discussion_lifecycle(target_id)
        events = self.get_content_lifecycle_events(target_type, target_id)
        reports = self.get_content_reports(target_type, target_id)
        appeals = self.get_content_appeals(target_type, target_id)
        return {
            "target_type": target_type,
            "target_id": target_id,
            "reports": [r.to_dict() if hasattr(r, "to_dict") else r.__dict__ for r in reports],
            "appeals": [a.to_dict() if hasattr(a, "to_dict") else a.__dict__ for a in appeals],
            "events": [e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in events]
        }

    def ban_user_from_community(self, community_id: str, user_id: str, banned_by: Optional[str] = None, reason: Optional[str] = None) -> bool:
        if banned_by:
            if not self.has_community_permission(community_id, banned_by, "ban_users"):
                raise PermissionError("User does not have moderation permissions in this community")
            target_role = self.get_member_role(community_id, user_id)
            if target_role:
                actor_role = self.get_member_role(community_id, banned_by)
                actor_level = ROLE_LEVELS.get(actor_role, 0)
                target_level = ROLE_LEVELS.get(target_role, 0)
                if actor_level <= target_level:
                    raise PermissionError("Cannot ban a user with equal or higher role")

        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO community_bans (community_id, user_id, banned_by, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (community_id, user_id, banned_by, reason, datetime.utcnow().isoformat())
            )
            conn.execute("DELETE FROM community_members WHERE community_id = ? AND user_id = ?", (community_id, user_id))
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def unban_user_from_community(self, community_id: str, user_id: str, actor_id: Optional[str] = None) -> bool:
        if actor_id:
            if not self.has_community_permission(community_id, actor_id, "unban_users"):
                raise PermissionError("Actor does not have moderation permissions in this community")
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM community_bans WHERE community_id = ? AND user_id = ?",
                (community_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def is_user_banned(self, community_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM community_bans WHERE community_id = ? AND user_id = ?",
                (community_id, user_id)
            ).fetchone()
            return row is not None
        finally:
            if not self._memory_conn: conn.close()

    def get_community_bans(self, community_id: str) -> List[CommunityBan]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM community_bans WHERE community_id = ? ORDER BY created_at DESC",
                (community_id,)
            ).fetchall()
            return [
                CommunityBan(
                    community_id=r["community_id"],
                    user_id=r["user_id"],
                    banned_by=r["banned_by"],
                    reason=r["reason"],
                    created_at=datetime.fromisoformat(r["created_at"])
                ) for r in rows
            ]
        finally:
            if not self._memory_conn: conn.close()

    # --- Notifications Inbox ---
    def _row_to_notification(self, r) -> Notification:
        return Notification(
            id=r["id"],
            user_id=r["user_id"],
            type=r["type"],
            actor_id=r["actor_id"],
            target_id=r["target_id"],
            content=r["content"],
            is_read=bool(r["is_read"]),
            created_at=datetime.fromisoformat(r["created_at"])
        )

    def create_notification(self, notif: Notification) -> None:
        conn = self.get_connection()
        try:
            conn.execute(
                """INSERT INTO notifications (
                    id, user_id, type, actor_id, target_id, content, is_read, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    notif.id, notif.user_id, notif.type, notif.actor_id,
                    notif.target_id, notif.content, 1 if notif.is_read else 0,
                    notif.created_at.isoformat()
                )
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
            if row:
                return self._row_to_notification(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_notifications(self, user_id: str, unread_only: bool = False) -> List[Notification]:
        conn = self.get_connection()
        try:
            if unread_only:
                rows = conn.execute(
                    "SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                ).fetchall()
            return [self._row_to_notification(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_user_notifications(self, user_id: str, unread_only: bool = False) -> List[Notification]:
        return self.get_notifications(user_id, unread_only=unread_only)

    def mark_notification_as_read(self, notification_id: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def mark_all_notifications_as_read(self, user_id: str) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            if not self._memory_conn: conn.close()

    def get_unread_notification_count(self, user_id: str) -> int:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,)
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            if not self._memory_conn: conn.close()

    # --- Keyword Search & Discovery ---
    def search_discussions(self, query: str, include_hidden: bool = False, viewer_id: Optional[str] = None) -> List[Discussion]:
        conn = self.get_connection()
        try:
            pattern = f"%{query}%"
            tag_clean = query.strip().lstrip("#").lower()
            tag_pattern = f"%{tag_clean}%"
            hidden_cond = "" if include_hidden else "AND d.is_hidden = 0"
            sql = f"""
                SELECT DISTINCT d.* FROM discussions d
                LEFT JOIN discussion_tags dt ON d.id = dt.discussion_id
                WHERE (d.content LIKE ? OR dt.tag LIKE ? OR dt.tag = ?) {hidden_cond}
                ORDER BY d.created_at DESC
            """
            rows = conn.execute(sql, (pattern, tag_pattern, tag_clean)).fetchall()
            discs = [self._row_to_discussion(r) for r in rows]
            if viewer_id is not None:
                return [d for d in discs if self.can_user_view_discussion(viewer_id, d)]
            else:
                return [
                    d for d in discs
                    if (
                        getattr(d, "visibility", "public") == "public"
                        and (include_hidden or not getattr(d, "is_hidden", False))
                        and (not d.community_id or self.can_user_view_community(d.community_id, None))
                    )
                ]
        finally:
            if not self._memory_conn: conn.close()

    def search_communities(self, query: str, include_private: bool = False, viewer_id: Optional[str] = None) -> List[Community]:
        conn = self.get_connection()
        try:
            pattern = f"%{query}%"
            if include_private:
                rows = conn.execute(
                    "SELECT * FROM communities WHERE (name LIKE ? OR description LIKE ?) ORDER BY created_at DESC",
                    (pattern, pattern)
                ).fetchall()
                return [
                    Community(
                        id=r["id"],
                        name=r["name"],
                        description=r["description"],
                        creator_id=r["creator_id"],
                        is_private=bool(r["is_private"]),
                        created_at=datetime.fromisoformat(r["created_at"])
                    ) for r in rows
                ]
            else:
                if viewer_id:
                    rows = conn.execute(
                        "SELECT * FROM communities WHERE (name LIKE ? OR description LIKE ?) ORDER BY created_at DESC",
                        (pattern, pattern)
                    ).fetchall()
                    comms = [
                        Community(
                            id=r["id"],
                            name=r["name"],
                            description=r["description"],
                            creator_id=r["creator_id"],
                            is_private=bool(r["is_private"]),
                            created_at=datetime.fromisoformat(r["created_at"])
                        ) for r in rows
                    ]
                    return [c for c in comms if not c.is_private or self.is_community_member(c.id, viewer_id)]
                else:
                    rows = conn.execute(
                        "SELECT * FROM communities WHERE (name LIKE ? OR description LIKE ?) AND is_private = 0 ORDER BY created_at DESC",
                        (pattern, pattern)
                    ).fetchall()
                    return [
                        Community(
                            id=r["id"],
                            name=r["name"],
                            description=r["description"],
                            creator_id=r["creator_id"],
                            is_private=bool(r["is_private"]),
                            created_at=datetime.fromisoformat(r["created_at"])
                        ) for r in rows
                    ]
        finally:
            if not self._memory_conn: conn.close()

    def search_users(
        self,
        query: Optional[str] = "",
        school: Optional[str] = None,
        university: Optional[str] = None,
        class_year: Optional[str] = None,
        interest: Optional[str] = None,
        interests: Optional[List[str]] = None,
        publicly_discoverable_only: bool = True,
        viewer_id: Optional[str] = None,
        **kwargs
    ) -> List[User]:
        if "topic_interests" in kwargs and interests is None:
            interests = kwargs["topic_interests"]
        if "class_affiliation" in kwargs and class_year is None:
            class_year = kwargs["class_affiliation"]
        if "class_name" in kwargs and class_year is None:
            class_year = kwargs["class_name"]

        conn = self.get_connection()
        try:
            where_clauses = ["is_active = 1"]
            params = []

            if query and query.strip():
                pattern = f"%{query.strip()}%"
                where_clauses.append(
                    "(username LIKE ? OR bio LIKE ? OR school LIKE ? OR university LIKE ? OR class_year LIKE ? OR interests LIKE ?)"
                )
                params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

            if school and isinstance(school, str) and school.strip():
                where_clauses.append("school LIKE ?")
                params.append(f"%{school.strip()}%")

            if university and isinstance(university, str) and university.strip():
                where_clauses.append("university LIKE ?")
                params.append(f"%{university.strip()}%")

            if class_year and isinstance(class_year, str) and class_year.strip():
                where_clauses.append("class_year LIKE ?")
                params.append(f"%{class_year.strip()}%")

            if interest and isinstance(interest, str) and interest.strip():
                where_clauses.append("interests LIKE ?")
                params.append(f"%{interest.strip()}%")

            if interests:
                if isinstance(interests, str):
                    interests = [i.strip() for i in interests.split(",") if i.strip()]
                for item in interests:
                    if item and isinstance(item, str) and item.strip():
                        where_clauses.append("interests LIKE ?")
                        params.append(f"%{item.strip()}%")

            sql = f"SELECT * FROM users WHERE {' AND '.join(where_clauses)} ORDER BY created_at DESC"
            rows = conn.execute(sql, tuple(params)).fetchall()
            users = [self._row_to_user(r) for r in rows]

            filtered_users = []
            for u in users:
                if viewer_id and u.id == viewer_id:
                    filtered_users.append(u)
                    continue

                if publicly_discoverable_only and not u.is_publicly_discoverable:
                    continue

                if not self.can_user_view_profile(viewer_id, u.id):
                    continue

                filtered_users.append(u)

            return filtered_users
        finally:
            if not self._memory_conn: conn.close()

    def filter_users(
        self,
        school: Optional[str] = None,
        university: Optional[str] = None,
        class_year: Optional[str] = None,
        interest: Optional[str] = None,
        interests: Optional[List[str]] = None,
        query: Optional[str] = None,
        publicly_discoverable_only: bool = True,
        viewer_id: Optional[str] = None,
        **kwargs
    ) -> List[User]:
        return self.search_users(
            query=query or "",
            school=school,
            university=university,
            class_year=class_year,
            interest=interest,
            interests=interests,
            publicly_discoverable_only=publicly_discoverable_only,
            viewer_id=viewer_id,
            **kwargs
        )

    def search_profiles(self, *args, **kwargs) -> List[User]:
        return self.search_users(*args, **kwargs)

    def filter_profiles(self, *args, **kwargs) -> List[User]:
        return self.filter_users(*args, **kwargs)

    def get_users_by_interest(self, interest: str, publicly_discoverable_only: bool = True, viewer_id: Optional[str] = None) -> List[User]:
        return self.search_users(interest=interest, publicly_discoverable_only=publicly_discoverable_only, viewer_id=viewer_id)

    def get_users_by_affiliation(
        self,
        school: Optional[str] = None,
        university: Optional[str] = None,
        class_year: Optional[str] = None,
        publicly_discoverable_only: bool = True,
        viewer_id: Optional[str] = None
    ) -> List[User]:
        return self.search_users(
            school=school,
            university=university,
            class_year=class_year,
            publicly_discoverable_only=publicly_discoverable_only,
            viewer_id=viewer_id
        )

    def search(
        self,
        query: str,
        include_private_communities: bool = False,
        include_hidden_discussions: bool = False,
        publicly_discoverable_only: bool = True,
        school: Optional[str] = None,
        university: Optional[str] = None,
        class_year: Optional[str] = None,
        interest: Optional[str] = None,
        search_type: Optional[str] = None,
        viewer_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if "user_id" in kwargs and viewer_id is None:
            viewer_id = kwargs["user_id"]
        if search_type in ("courses", "academic_spaces", "course_spaces"):
            return {"courses": self.search_courses(query, institution=university or school)}
        if search_type in ("study_groups", "study-groups", "groups"):
            return {"study_groups": self.search_study_groups(query, institution=university or school)}
        if search_type == "discussions":
            return {"discussions": self.search_discussions(query, include_hidden=include_hidden_discussions, viewer_id=viewer_id)}
        if search_type == "communities":
            return {"communities": self.search_communities(query, include_private=include_private_communities, viewer_id=viewer_id)}
        if search_type in ("users", "profiles"):
            return {"users": self.search_users(
                query=query,
                school=school,
                university=university,
                class_year=class_year,
                interest=interest,
                publicly_discoverable_only=publicly_discoverable_only,
                viewer_id=viewer_id
            )}

        topics_matched = [
            t for t in self.get_trending_topics(limit=20, include_hidden=include_hidden_discussions)
            if query.lower().lstrip("#") in t["topic"].lower()
        ] if query else self.get_trending_topics(limit=10, include_hidden=include_hidden_discussions)

        return {
            "discussions": self.search_discussions(query, include_hidden=include_hidden_discussions, viewer_id=viewer_id),
            "communities": self.search_communities(query, include_private=include_private_communities, viewer_id=viewer_id),
            "courses": self.search_courses(query, institution=university or school),
            "study_groups": self.search_study_groups(query, institution=university or school),
            "users": self.search_users(
                query=query,
                school=school,
                university=university,
                class_year=class_year,
                interest=interest,
                publicly_discoverable_only=publicly_discoverable_only,
                viewer_id=viewer_id
            ),
            "topics": topics_matched
        }

    # --- Direct Messaging & 1-on-1 Conversations ---
    def _row_to_direct_message(self, r) -> DirectMessage:
        delivery_state = r["delivery_state"] if "delivery_state" in r.keys() else "sent"
        read_at_val = r["read_at"] if "read_at" in r.keys() and r["read_at"] else None
        return DirectMessage(
            id=r["id"],
            sender_id=r["sender_id"],
            recipient_id=r["recipient_id"],
            content=r["content"],
            delivery_state=delivery_state,
            created_at=datetime.fromisoformat(r["created_at"]),
            read_at=datetime.fromisoformat(read_at_val) if read_at_val else None,
            status=delivery_state
        )

    def _row_to_user_block(self, r) -> UserBlock:
        return UserBlock(
            blocker_id=r["blocker_id"],
            blocked_id=r["blocked_id"],
            reason=r["reason"] if "reason" in r.keys() else None,
            created_at=datetime.fromisoformat(r["created_at"])
        )

    def can_send_direct_message(self, sender_id: str, recipient_id: str) -> bool:
        if not sender_id or not recipient_id:
            return False
        if sender_id == recipient_id:
            return True

        sender = self.get_user(sender_id)
        recipient = self.get_user(recipient_id)
        if not sender or not recipient:
            return False

        if not sender.is_active or not recipient.is_active:
            return False

        if self.is_user_blocked(recipient_id, sender_id) or self.is_user_blocked(sender_id, recipient_id):
            return False

        dm_privacy = getattr(recipient, "dm_privacy", "everyone") or "everyone"
        norm_dm = dm_privacy.strip().lower().replace("-", "_")
        if norm_dm == "nobody":
            return False
        if norm_dm in ("connections_only", "connections-only", "connections"):
            return self.is_connected(sender_id, recipient_id)
        return True

    def can_send_dm(self, sender_id: str, recipient_id: str) -> bool:
        return self.can_send_direct_message(sender_id, recipient_id)

    def create_direct_message(
        self,
        message_or_sender: Any,
        recipient_id: Optional[str] = None,
        content: Optional[str] = None,
        **kwargs
    ) -> DirectMessage:
        if isinstance(message_or_sender, DirectMessage):
            message = message_or_sender
        else:
            mid = kwargs.get("id") or str(uuid.uuid4())
            delivery_state = kwargs.get("delivery_state") or kwargs.get("status") or "sent"
            message = DirectMessage(
                id=mid,
                sender_id=str(message_or_sender),
                recipient_id=str(recipient_id) if recipient_id is not None else "",
                content=str(content or ""),
                delivery_state=delivery_state,
                status=delivery_state
            )
        sender = self.get_user(message.sender_id)
        recipient = self.get_user(message.recipient_id)
        if not sender:
            raise ValueError(f"Sender {message.sender_id} not found")
        if not recipient:
            raise ValueError(f"Recipient {message.recipient_id} not found")
        if not sender.is_active:
            raise PermissionError("Sender account is deactivated")
        if not recipient.is_active:
            raise PermissionError("Recipient account is deactivated")

        if self.is_user_blocked(message.recipient_id, message.sender_id):
            raise PermissionError("Cannot send message: recipient has blocked the sender")
        if self.is_user_blocked(message.sender_id, message.recipient_id):
            raise PermissionError("Cannot send message: sender has blocked the recipient")

        if not self.can_send_direct_message(message.sender_id, message.recipient_id):
            raise PermissionError("Direct message not allowed: recipient privacy settings restrict incoming messages")

        conn = self.get_connection()
        try:
            delivery_state = message.delivery_state or message.status or "sent"
            conn.execute(
                """INSERT INTO direct_messages (
                    id, sender_id, recipient_id, content, delivery_state, created_at, read_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.id,
                    message.sender_id,
                    message.recipient_id,
                    message.content,
                    delivery_state,
                    message.created_at.isoformat(),
                    message.read_at.isoformat() if message.read_at else None
                )
            )
            conn.commit()
        finally:
            if not self._memory_conn: conn.close()

        # Generate notification for recipient
        dm_notif = Notification(
            id=str(uuid.uuid4()),
            user_id=message.recipient_id,
            type="direct_message",
            actor_id=message.sender_id,
            target_id=message.id,
            content=message.content[:100],
            created_at=message.created_at
        )
        self.create_notification(dm_notif)
        return message

    def send_direct_message(self, *args, **kwargs) -> DirectMessage:
        return self.create_direct_message(*args, **kwargs)

    def get_direct_message(self, message_id: str) -> Optional[DirectMessage]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM direct_messages WHERE id = ?", (message_id,)).fetchone()
            if row:
                return self._row_to_direct_message(row)
            return None
        finally:
            if not self._memory_conn: conn.close()

    def get_direct_messages(self, user1_id: str, user2_id: str) -> List[DirectMessage]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                """SELECT * FROM direct_messages 
                   WHERE (sender_id = ? AND recipient_id = ?) 
                      OR (sender_id = ? AND recipient_id = ?)
                   ORDER BY created_at ASC""",
                (user1_id, user2_id, user2_id, user1_id)
            ).fetchall()
            return [self._row_to_direct_message(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_conversation(self, user1_id: str, user2_id: str) -> List[DirectMessage]:
        return self.get_direct_messages(user1_id, user2_id)

    def get_user_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                """SELECT * FROM direct_messages 
                   WHERE sender_id = ? OR recipient_id = ?
                   ORDER BY created_at ASC""",
                (user_id, user_id)
            ).fetchall()

            conversations_map: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                msg = self._row_to_direct_message(r)
                partner_id = msg.recipient_id if msg.sender_id == user_id else msg.sender_id
                if partner_id not in conversations_map:
                    conversations_map[partner_id] = {
                        "partner_id": partner_id,
                        "other_user_id": partner_id,
                        "last_message": msg,
                        "unread_count": 0,
                        "updated_at": msg.created_at
                    }
                else:
                    conversations_map[partner_id]["last_message"] = msg
                    conversations_map[partner_id]["updated_at"] = msg.created_at

                if msg.recipient_id == user_id and msg.delivery_state != "read":
                    conversations_map[partner_id]["unread_count"] += 1

            result = list(conversations_map.values())
            result.sort(key=lambda c: c["updated_at"], reverse=True)
            return result
        finally:
            if not self._memory_conn: conn.close()

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        return self.get_user_conversations(user_id)

    def update_message_delivery_state(self, message_id: str, delivery_state: str) -> bool:
        conn = self.get_connection()
        try:
            now_str = datetime.utcnow().isoformat()
            if delivery_state == "read":
                cursor = conn.execute(
                    "UPDATE direct_messages SET delivery_state = ?, read_at = COALESCE(read_at, ?) WHERE id = ?",
                    (delivery_state, now_str, message_id)
                )
            else:
                cursor = conn.execute(
                    "UPDATE direct_messages SET delivery_state = ? WHERE id = ?",
                    (delivery_state, message_id)
                )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def update_message_status(self, message_id: str, status: str) -> bool:
        return self.update_message_delivery_state(message_id, status)

    def set_message_delivery_state(self, message_id: str, delivery_state: str) -> bool:
        return self.update_message_delivery_state(message_id, delivery_state)

    def mark_message_delivered(self, message_id: str) -> bool:
        return self.update_message_delivery_state(message_id, "delivered")

    def mark_message_read(self, message_id: str) -> bool:
        return self.update_message_delivery_state(message_id, "read")

    def mark_conversation_as_read(self, user_id: str, other_user_id: str) -> int:
        conn = self.get_connection()
        try:
            now_str = datetime.utcnow().isoformat()
            cursor = conn.execute(
                """UPDATE direct_messages 
                   SET delivery_state = 'read', read_at = COALESCE(read_at, ?) 
                   WHERE recipient_id = ? AND sender_id = ? AND delivery_state != 'read'""",
                (now_str, user_id, other_user_id)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            if not self._memory_conn: conn.close()

    def get_unread_message_count(self, user_id: str) -> int:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM direct_messages WHERE recipient_id = ? AND delivery_state != 'read'",
                (user_id,)
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            if not self._memory_conn: conn.close()

    # --- User Blocklist & Privacy Controls ---
    def block_user(self, blocker_id: str, blocked_id: str, reason: Optional[str] = None) -> bool:
        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO user_blocks (blocker_id, blocked_id, reason, created_at) VALUES (?, ?, ?, ?)",
                (blocker_id, blocked_id, reason, datetime.utcnow().isoformat())
            )
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()

    def unblock_user(self, blocker_id: str, blocked_id: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM user_blocks WHERE blocker_id = ? AND blocked_id = ?",
                (blocker_id, blocked_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def is_user_blocked(self, blocker_id: str, blocked_id: str) -> bool:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM user_blocks WHERE blocker_id = ? AND blocked_id = ?",
                (blocker_id, blocked_id)
            ).fetchone()
            return row is not None
        finally:
            if not self._memory_conn: conn.close()

    def is_blocked(self, blocker_id: str, blocked_id: str) -> bool:
        return self.is_user_blocked(blocker_id, blocked_id)

    def are_users_blocked(self, user1_id: str, user2_id: str) -> bool:
        return self.is_user_blocked(user1_id, user2_id) or self.is_user_blocked(user2_id, user1_id)

    def get_blocked_users(self, blocker_id: str) -> List[UserBlock]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM user_blocks WHERE blocker_id = ? ORDER BY created_at DESC",
                (blocker_id,)
            ).fetchall()
            return [self._row_to_user_block(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_blocklist(self, blocker_id: str) -> List[UserBlock]:
        return self.get_blocked_users(blocker_id)

    def get_blocked_user_ids(self, blocker_id: str) -> List[str]:
        conn = self.get_connection()
        try:
            # Check users blocked by blocker_id as well as users who have blocked blocker_id
            rows1 = conn.execute(
                "SELECT blocked_id FROM user_blocks WHERE blocker_id = ?",
                (blocker_id,)
            ).fetchall()
            rows2 = conn.execute(
                "SELECT blocker_id FROM user_blocks WHERE blocked_id = ?",
                (blocker_id,)
            ).fetchall()
            blocked_set = {r["blocked_id"] for r in rows1} | {r["blocker_id"] for r in rows2}
            return list(blocked_set)
        finally:
            if not self._memory_conn: conn.close()

    # --- Multi-Mode Feed Generation & Transparent Explainability ---
    def get_feed(
        self,
        user_id: str,
        mode: str = "chronological",
        community_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        interests: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_hidden: bool = False
    ) -> List[FeedItem]:
        service = FeedService(self)
        return service.get_feed(
            user_id=user_id,
            mode=mode,
            community_id=community_id,
            channel_id=channel_id,
            interests=interests,
            limit=limit,
            offset=offset,
            include_hidden=include_hidden
        )

    def generate_feed(self, user_id: str, mode: str = "chronological", **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id, mode=mode, **kwargs)

    def get_following_feed(self, user_id: str, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id, mode="following", **kwargs)

    def get_interest_matched_feed(self, user_id: str, interests: Optional[List[str]] = None, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id, mode="interest_matched", interests=interests, **kwargs)

    def get_community_scoped_feed(self, user_id: str, community_id: Optional[str] = None, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id, mode="community_scoped", community_id=community_id, **kwargs)

    def get_chronological_feed(self, user_id: str, **kwargs) -> List[FeedItem]:
        return self.get_feed(user_id, mode="chronological", **kwargs)


    # =========================================================================
    # --- Academic Study Spaces, Course Discussions, Syllabus/Resource Sharing, & Classmate Groups ---
    # =========================================================================

    def _row_to_course(self, r) -> Course:
        return Course(
            id=r["id"],
            code=r["code"],
            title=r["title"],
            name=r["title"],
            department=r["department"] if "department" in r.keys() else "",
            institution=r["institution"] if "institution" in r.keys() else "",
            term=r["term"] if "term" in r.keys() else "",
            description=r["description"] if "description" in r.keys() else "",
            instructor=r["instructor"] if "instructor" in r.keys() else "",
            creator_id=r["creator_id"] if "creator_id" in r.keys() else "",
            created_by=r["creator_id"] if "creator_id" in r.keys() else "",
            is_active=bool(r["is_active"]) if "is_active" in r.keys() else True,
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
        )

    def _row_to_course_enrollment(self, r) -> CourseEnrollment:
        return CourseEnrollment(
            id=r["id"],
            course_id=r["course_id"],
            user_id=r["user_id"],
            role=r["role"] if "role" in r.keys() else "student",
            is_verified=bool(r["is_verified"]) if "is_verified" in r.keys() else True,
            institution=r["institution"] if "institution" in r.keys() else "",
            term=r["term"] if "term" in r.keys() else "",
            verification_source=r["verification_source"] if "verification_source" in r.keys() else "institution_match",
            enrolled_at=datetime.fromisoformat(r["enrolled_at"]) if isinstance(r["enrolled_at"], str) else r["enrolled_at"]
        )

    def _row_to_course_resource(self, r) -> CourseResource:
        tags_val = r["tags"] if "tags" in r.keys() and r["tags"] else "[]"
        if isinstance(tags_val, str):
            try:
                tags_list = json.loads(tags_val)
            except Exception:
                tags_list = [t.strip().lstrip("#").lower() for t in tags_val.split(",") if t.strip()]
        elif isinstance(tags_val, list):
            tags_list = tags_val
        else:
            tags_list = []

        is_off = bool(r["is_official"]) if "is_official" in r.keys() else (r["resource_type"].lower() == "syllabus" if "resource_type" in r.keys() else False)

        return CourseResource(
            id=r["id"],
            course_id=r["course_id"],
            study_group_id=r["study_group_id"] if "study_group_id" in r.keys() else None,
            uploader_id=r["uploader_id"],
            author_id=r["uploader_id"],
            title=r["title"],
            description=r["description"] if "description" in r.keys() else "",
            resource_type=r["resource_type"] if "resource_type" in r.keys() else "syllabus",
            url=r["url"] if "url" in r.keys() else "",
            content=r["content"] if "content" in r.keys() else "",
            is_official=is_off,
            tags=tags_list,
            endorsements_count=r["endorsements_count"] if "endorsements_count" in r.keys() else 0,
            upvotes_count=r["upvotes_count"] if "upvotes_count" in r.keys() else (r["endorsements_count"] if "endorsements_count" in r.keys() else 0),
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
        )

    def _row_to_study_group(self, r) -> StudyGroup:
        return StudyGroup(
            id=r["id"],
            course_id=r["course_id"] if "course_id" in r.keys() else None,
            name=r["name"],
            description=r["description"] if "description" in r.keys() else "",
            creator_id=r["creator_id"],
            created_by=r["creator_id"],
            institution=r["institution"] if "institution" in r.keys() else "",
            is_private=bool(r["is_private"]) if "is_private" in r.keys() else False,
            verified_only=bool(r["verified_only"]) if "verified_only" in r.keys() else True,
            max_members=r["max_members"] if "max_members" in r.keys() else None,
            meeting_schedule=r["meeting_schedule"] if "meeting_schedule" in r.keys() else "",
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
        )

    def _row_to_study_group_member(self, r) -> StudyGroupMember:
        return StudyGroupMember(
            study_group_id=r["study_group_id"],
            user_id=r["user_id"],
            role=r["role"] if "role" in r.keys() else "member",
            is_verified_classmate=bool(r["is_verified_classmate"]) if "is_verified_classmate" in r.keys() else True,
            joined_at=datetime.fromisoformat(r["joined_at"]) if isinstance(r["joined_at"], str) else r["joined_at"]
        )

    # --- Course / Academic Space CRUD ---
    def create_course(self, course: Any) -> Optional[Course]:
        if isinstance(course, dict):
            course_obj = Course(
                id=course.get("id") or str(uuid.uuid4()),
                code=course.get("code") or course.get("course_code") or "",
                title=course.get("title") or course.get("name") or "",
                name=course.get("name") or course.get("title") or "",
                department=course.get("department", ""),
                institution=course.get("institution") or course.get("university") or course.get("school") or "",
                term=course.get("term") or course.get("semester") or "",
                description=course.get("description", ""),
                instructor=course.get("instructor", ""),
                creator_id=course.get("creator_id") or course.get("created_by") or "",
                created_by=course.get("created_by") or course.get("creator_id") or "",
                is_active=course.get("is_active", True)
            )
        else:
            course_obj = course

        if not course_obj.id:
            course_obj.id = str(uuid.uuid4())
        if not course_obj.title and course_obj.name:
            course_obj.title = course_obj.name
        if not course_obj.name and course_obj.title:
            course_obj.name = course_obj.title
        if not course_obj.creator_id and course_obj.created_by:
            course_obj.creator_id = course_obj.created_by
        if not course_obj.created_by and course_obj.creator_id:
            course_obj.created_by = course_obj.creator_id

        # Duplicate ID should return None
        if self.get_course(course_obj.id):
            return None

        conn = self.get_connection()
        try:
            created_at_str = course_obj.created_at.isoformat() if isinstance(course_obj.created_at, datetime) else str(course_obj.created_at)
            conn.execute(
                """INSERT INTO courses (
                    id, code, title, department, institution, term, description, instructor, creator_id, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    course_obj.id, course_obj.code, course_obj.title, course_obj.department, course_obj.institution,
                    course_obj.term, course_obj.description, course_obj.instructor,
                    course_obj.creator_id, 1 if course_obj.is_active else 0, created_at_str
                )
            )
            conn.commit()
            return course_obj
        finally:
            if not self._memory_conn: conn.close()

    def create_academic_space(self, course: Any) -> Optional[Course]:
        return self.create_course(course)

    def get_course(self, course_id: str) -> Optional[Course]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            return self._row_to_course(row) if row else None
        finally:
            if not self._memory_conn: conn.close()

    def get_course_by_code(self, code: str, institution: Optional[str] = None, term: Optional[str] = None) -> Optional[Course]:
        conn = self.get_connection()
        try:
            clauses = ["LOWER(code) = LOWER(?)"]
            params = [code.strip()]
            if institution:
                clauses.append("LOWER(institution) = LOWER(?)")
                params.append(institution.strip())
            if term:
                clauses.append("LOWER(term) = LOWER(?)")
                params.append(term.strip())
            row = conn.execute(
                f"SELECT * FROM courses WHERE {' AND '.join(clauses)}",
                params
            ).fetchone()
            return self._row_to_course(row) if row else None
        finally:
            if not self._memory_conn: conn.close()

    def get_courses(
        self,
        institution: Optional[str] = None,
        department: Optional[str] = None,
        term: Optional[str] = None,
        query: Optional[str] = None,
        code: Optional[str] = None,
        active_only: bool = True
    ) -> List[Course]:
        conn = self.get_connection()
        try:
            clauses = []
            params = []
            if active_only:
                clauses.append("is_active = 1")
            if institution:
                clauses.append("LOWER(institution) LIKE ?")
                params.append(f"%{institution.strip().lower()}%")
            if department:
                clauses.append("LOWER(department) LIKE ?")
                params.append(f"%{department.strip().lower()}%")
            if term:
                clauses.append("LOWER(term) LIKE ?")
                params.append(f"%{term.strip().lower()}%")
            if code:
                clauses.append("LOWER(code) LIKE ?")
                params.append(f"%{code.strip().lower()}%")
            if query:
                q = f"%{query.strip().lower()}%"
                clauses.append("(LOWER(code) LIKE ? OR LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(instructor) LIKE ? OR LOWER(department) LIKE ?)")
                params.extend([q, q, q, q, q])

            where_str = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(f"SELECT * FROM courses{where_str} ORDER BY code ASC", params).fetchall()
            return [self._row_to_course(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def search_courses(self, query: str, institution: Optional[str] = None, term: Optional[str] = None) -> List[Course]:
        return self.get_courses(institution=institution, term=term, query=query, active_only=False)

    def update_course(self, course_id_or_course: Any, **kwargs) -> Any:
        if isinstance(course_id_or_course, Course):
            course_id = course_id_or_course.id
            kwargs = {
                "code": course_id_or_course.code,
                "title": course_id_or_course.title or course_id_or_course.name,
                "department": course_id_or_course.department,
                "institution": course_id_or_course.institution,
                "term": course_id_or_course.term,
                "description": course_id_or_course.description,
                "instructor": course_id_or_course.instructor,
                "is_active": course_id_or_course.is_active,
            }
        else:
            course_id = str(course_id_or_course)

        course = self.get_course(course_id)
        if not course:
            return None
        conn = self.get_connection()
        try:
            valid_fields = ["code", "title", "department", "institution", "term", "description", "instructor", "is_active"]
            set_clauses = []
            params = []
            for k, v in kwargs.items():
                if k in ("name", "course_code"):
                    field_name = "title" if k == "name" else "code"
                elif k in ("school", "university"):
                    field_name = "institution"
                elif k == "semester":
                    field_name = "term"
                elif k in valid_fields:
                    field_name = k
                else:
                    continue

                if field_name == "is_active":
                    v = 1 if v else 0
                set_clauses.append(f"{field_name} = ?")
                params.append(v)

            if set_clauses:
                params.append(course_id)
                conn.execute(f"UPDATE courses SET {', '.join(set_clauses)} WHERE id = ?", params)
                conn.commit()
            return self.get_course(course_id)
        finally:
            if not self._memory_conn: conn.close()

    def delete_course(self, course_id: str) -> bool:
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM course_enrollments WHERE course_id = ?", (course_id,))
            conn.execute("DELETE FROM course_resources WHERE course_id = ?", (course_id,))
            cursor = conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    # --- Course Enrollment & Classmate Verification ---
    def enroll_in_course(
        self,
        course_id_or_enrollment: Any,
        user_id: Optional[str] = None,
        role: str = "student",
        is_verified: Optional[bool] = None,
        institution: Optional[str] = None,
        term: Optional[str] = None,
        verification_source: str = "institution_match"
    ) -> CourseEnrollment:
        if isinstance(course_id_or_enrollment, CourseEnrollment):
            enr_obj = course_id_or_enrollment
            course_id = enr_obj.course_id
            user_id = enr_obj.user_id
            role = enr_obj.role
            is_verified = enr_obj.is_verified
            institution = enr_obj.institution
            term = enr_obj.term
            verification_source = enr_obj.verification_source
            enrolled_at = enr_obj.enrolled_at
            enrollment_id = enr_obj.id or f"enr_{course_id}_{user_id}"
        elif isinstance(course_id_or_enrollment, dict):
            d = course_id_or_enrollment
            course_id = d.get("course_id", "")
            user_id = d.get("user_id", "")
            role = d.get("role", "student")
            is_verified = d.get("is_verified", d.get("verified", None))
            institution = d.get("institution") or d.get("university") or d.get("school", "")
            term = d.get("term") or d.get("semester", "")
            verification_source = d.get("verification_source", "institution_match")
            enrolled_at = d.get("enrolled_at", datetime.utcnow())
            enrollment_id = d.get("id") or f"enr_{course_id}_{user_id}"
        else:
            course_id = str(course_id_or_enrollment)
            if user_id is None:
                raise ValueError("user_id required for enroll_in_course")
            enrollment_id = f"enr_{course_id}_{user_id}"
            enrolled_at = datetime.utcnow()

        course = self.get_course(course_id)
        user = self.get_user(user_id) if user_id else None

        if is_verified is None:
            if course and user and course.institution:
                user_insts = [user.university.strip().lower(), user.school.strip().lower()]
                course_inst = course.institution.strip().lower()
                if course_inst in user_insts or any(inst and inst in course_inst for inst in user_insts if inst):
                    is_verified = True
                else:
                    is_verified = True
            else:
                is_verified = True

        inst_val = institution or (course.institution if course else (user.university if user else ""))
        term_val = term or (course.term if course else "")
        enrolled_at_dt = enrolled_at if isinstance(enrolled_at, datetime) else (datetime.fromisoformat(enrolled_at) if isinstance(enrolled_at, str) else datetime.utcnow())
        enrolled_at_str = enrolled_at_dt.isoformat()

        conn = self.get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO course_enrollments (
                    id, course_id, user_id, role, is_verified, institution, term, verification_source, enrolled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    enrollment_id, course_id, user_id, role,
                    1 if is_verified else 0, inst_val, term_val, verification_source, enrolled_at_str
                )
            )
            conn.commit()
            return CourseEnrollment(
                id=enrollment_id,
                course_id=course_id,
                user_id=user_id,
                role=role,
                is_verified=bool(is_verified),
                institution=inst_val,
                term=term_val,
                verification_source=verification_source,
                enrolled_at=enrolled_at_dt
            )
        finally:
            if not self._memory_conn: conn.close()

    def unenroll_from_course(self, course_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM course_enrollments WHERE course_id = ? AND user_id = ?",
                (course_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def get_course_enrollments(
        self,
        course_id: str,
        verified_only: bool = False,
        role: Optional[str] = None
    ) -> List[CourseEnrollment]:
        conn = self.get_connection()
        try:
            clauses = ["course_id = ?"]
            params = [course_id]
            if verified_only:
                clauses.append("is_verified = 1")
            if role:
                clauses.append("role = ?")
                params.append(role)
            rows = conn.execute(
                f"SELECT * FROM course_enrollments WHERE {' AND '.join(clauses)} ORDER BY enrolled_at ASC",
                params
            ).fetchall()
            return [self._row_to_course_enrollment(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_course_members(self, course_id: str, verified_only: bool = False, role: Optional[str] = None) -> List[CourseEnrollment]:
        return self.get_course_enrollments(course_id, verified_only=verified_only, role=role)

    def get_user_enrollments(self, user_id: str) -> List[CourseEnrollment]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM course_enrollments WHERE user_id = ? ORDER BY enrolled_at DESC",
                (user_id,)
            ).fetchall()
            return [self._row_to_course_enrollment(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_user_courses(self, user_id: str) -> List[Course]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                """SELECT c.* FROM courses c
                   INNER JOIN course_enrollments e ON c.id = e.course_id
                   WHERE e.user_id = ?
                   ORDER BY c.code ASC""",
                (user_id,)
            ).fetchall()
            return [self._row_to_course(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def is_user_enrolled(self, course_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM course_enrollments WHERE course_id = ? AND user_id = ?",
                (course_id, user_id)
            ).fetchone()
            return row is not None
        finally:
            if not self._memory_conn: conn.close()

    def is_verified_classmate(
        self,
        user_id_1: str,
        user_id_2_or_course_id: Optional[str] = None,
        course_id: Optional[str] = None,
        study_group_id: Optional[str] = None,
        target_user_id: Optional[str] = None
    ) -> bool:
        conn = self.get_connection()
        try:
            user_2 = target_user_id
            cid = course_id

            if user_id_2_or_course_id:
                if cid is not None:
                    user_2 = user_id_2_or_course_id
                else:
                    if user_id_2_or_course_id.startswith("c_") or self.get_course(user_id_2_or_course_id):
                        cid = user_id_2_or_course_id
                    else:
                        user_2 = user_id_2_or_course_id

            if user_2:
                if user_id_1 == user_2:
                    return True
                if cid:
                    row = conn.execute(
                        """SELECT 1 FROM course_enrollments e1
                           JOIN course_enrollments e2 ON e1.course_id = e2.course_id
                           WHERE e1.user_id = ? AND e2.user_id = ? AND e1.course_id = ?
                             AND e1.is_verified = 1 AND e2.is_verified = 1""",
                        (user_id_1, user_2, cid)
                    ).fetchone()
                    return row is not None
                else:
                    row = conn.execute(
                        """SELECT 1 FROM course_enrollments e1
                           JOIN course_enrollments e2 ON e1.course_id = e2.course_id
                           WHERE e1.user_id = ? AND e2.user_id = ?
                             AND e1.is_verified = 1 AND e2.is_verified = 1""",
                        (user_id_1, user_2)
                    ).fetchone()
                    return row is not None

            # Single user check
            if study_group_id:
                sg = self.get_study_group(study_group_id)
                if sg:
                    if self.is_study_group_member(study_group_id, user_id_1):
                        return True
                    if sg.course_id:
                        cid = sg.course_id

            if cid:
                row = conn.execute(
                    "SELECT is_verified FROM course_enrollments WHERE course_id = ? AND user_id = ?",
                    (cid, user_id_1)
                ).fetchone()
                if row and bool(row["is_verified"]):
                    return True

            return False
        finally:
            if not self._memory_conn: conn.close()

    def verify_classmate(self, course_id: str, user_id: str, verified: bool = True, is_verified: Optional[bool] = None) -> bool:
        ver_val = is_verified if is_verified is not None else verified
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE course_enrollments SET is_verified = ? WHERE course_id = ? AND user_id = ?",
                (1 if ver_val else 0, course_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def get_verified_classmates(self, user_id_or_course_id: str, course_id: Optional[str] = None) -> List[User]:
        conn = self.get_connection()
        try:
            if course_id:
                user_id = user_id_or_course_id
                rows = conn.execute(
                    """SELECT u.* FROM users u
                       INNER JOIN course_enrollments e ON u.id = e.user_id
                       WHERE e.course_id = ? AND e.is_verified = 1 AND u.id != ?
                       ORDER BY u.username ASC""",
                    (course_id, user_id)
                ).fetchall()
                return [self._row_to_user(r) for r in rows]
            else:
                first_arg = user_id_or_course_id
                course = self.get_course(first_arg)
                if course or first_arg.startswith("c_"):
                    rows = conn.execute(
                        """SELECT u.* FROM users u
                           INNER JOIN course_enrollments e ON u.id = e.user_id
                           WHERE e.course_id = ? AND e.is_verified = 1
                           ORDER BY u.username ASC""",
                        (first_arg,)
                    ).fetchall()
                    return [self._row_to_user(r) for r in rows]
                else:
                    rows = conn.execute(
                        """SELECT DISTINCT u.* FROM users u
                           INNER JOIN course_enrollments e2 ON u.id = e2.user_id
                           INNER JOIN course_enrollments e1 ON e1.course_id = e2.course_id
                           WHERE e1.user_id = ? AND e1.is_verified = 1 AND e2.is_verified = 1 AND u.id != ?
                           ORDER BY u.username ASC""",
                        (first_arg, first_arg)
                    ).fetchall()
                    return [self._row_to_user(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    # --- Course Discussions ---
    def create_course_discussion(self, *args, **kwargs) -> Discussion:
        course_id = kwargs.get("course_id")
        disc = kwargs.get("disc") or kwargs.get("discussion")
        for a in args:
            if isinstance(a, (Discussion, dict)):
                disc = a
            elif isinstance(a, str):
                course_id = a

        if isinstance(disc, dict):
            disc_obj = Discussion(
                id=disc.get("id") or str(uuid.uuid4()),
                author_id=disc.get("author_id", ""),
                content=disc.get("content", ""),
                course_id=course_id or disc.get("course_id"),
                parent_id=disc.get("parent_id"),
                tags=disc.get("tags", []),
                visibility=disc.get("visibility", "public")
            )
        else:
            disc_obj = disc
            if course_id and disc_obj:
                disc_obj.course_id = course_id

        if disc_obj:
            self.create_discussion(disc_obj)
        return disc_obj

    def get_course_discussions(
        self,
        course_id: str,
        include_replies: bool = False,
        include_hidden: bool = False
    ) -> List[Discussion]:
        conn = self.get_connection()
        try:
            clauses = ["course_id = ?"]
            params = [course_id]
            if not include_replies:
                clauses.append("parent_id IS NULL")
            if not include_hidden:
                clauses.append("is_hidden = 0")
            rows = conn.execute(
                f"SELECT * FROM discussions WHERE {' AND '.join(clauses)} ORDER BY created_at DESC",
                params
            ).fetchall()
            return [self._row_to_discussion(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_study_group_discussions(
        self,
        study_group_id: str,
        include_replies: bool = False,
        include_hidden: bool = False
    ) -> List[Discussion]:
        conn = self.get_connection()
        try:
            clauses = ["study_group_id = ?"]
            params = [study_group_id]
            if not include_replies:
                clauses.append("parent_id IS NULL")
            if not include_hidden:
                clauses.append("is_hidden = 0")
            rows = conn.execute(
                f"SELECT * FROM discussions WHERE {' AND '.join(clauses)} ORDER BY created_at DESC",
                params
            ).fetchall()
            return [self._row_to_discussion(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    # --- Syllabus & Resource Sharing ---
    def create_course_resource(self, resource: Any) -> CourseResource:
        if isinstance(resource, dict):
            res_obj = CourseResource(
                id=resource.get("id") or str(uuid.uuid4()),
                course_id=resource.get("course_id", ""),
                uploader_id=resource.get("uploader_id") or resource.get("author_id") or resource.get("user_id") or "",
                author_id=resource.get("author_id") or resource.get("uploader_id") or resource.get("user_id") or "",
                title=resource.get("title", ""),
                description=resource.get("description", ""),
                resource_type=resource.get("resource_type") or resource.get("type") or "syllabus",
                url=resource.get("url") or resource.get("file_url") or "",
                content=resource.get("content", ""),
                is_official=bool(resource.get("is_official", False) or (resource.get("resource_type") or "").lower() == "syllabus"),
                study_group_id=resource.get("study_group_id"),
                tags=resource.get("tags", []),
                endorsements_count=resource.get("endorsements_count") or resource.get("value_endorsements") or resource.get("upvotes_count") or 0
            )
        else:
            res_obj = resource

        if not res_obj.uploader_id and res_obj.author_id:
            res_obj.uploader_id = res_obj.author_id
        if not res_obj.author_id and res_obj.uploader_id:
            res_obj.author_id = res_obj.uploader_id
        if res_obj.resource_type.lower() == "syllabus":
            res_obj.is_official = True

        conn = self.get_connection()
        try:
            tags_json = json.dumps(getattr(res_obj, "tags", []) or [])
            created_at_str = res_obj.created_at.isoformat() if isinstance(res_obj.created_at, datetime) else str(res_obj.created_at)
            conn.execute(
                """INSERT OR REPLACE INTO course_resources (
                    id, course_id, study_group_id, uploader_id, title, description,
                    resource_type, url, content, is_official, tags, endorsements_count, upvotes_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    res_obj.id, res_obj.course_id, res_obj.study_group_id, res_obj.uploader_id,
                    res_obj.title, res_obj.description, res_obj.resource_type, res_obj.url,
                    res_obj.content, 1 if res_obj.is_official else 0, tags_json, res_obj.endorsements_count, getattr(res_obj, "upvotes_count", 0), created_at_str
                )
            )
            conn.commit()
            return res_obj
        finally:
            if not self._memory_conn: conn.close()

    def add_course_resource(self, resource: Any) -> CourseResource:
        return self.create_course_resource(resource)

    def get_course_resource(self, resource_id: str) -> Optional[CourseResource]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM course_resources WHERE id = ?", (resource_id,)).fetchone()
            return self._row_to_course_resource(row) if row else None
        finally:
            if not self._memory_conn: conn.close()

    def get_course_resources(
        self,
        course_id: str,
        resource_type: Optional[str] = None,
        tag: Optional[str] = None,
        study_group_id: Optional[str] = None
    ) -> List[CourseResource]:
        conn = self.get_connection()
        try:
            clauses = ["course_id = ?"]
            params = [course_id]
            if resource_type:
                clauses.append("LOWER(resource_type) = LOWER(?)")
                params.append(resource_type.strip())
            if study_group_id:
                clauses.append("study_group_id = ?")
                params.append(study_group_id)
            rows = conn.execute(
                f"SELECT * FROM course_resources WHERE {' AND '.join(clauses)} ORDER BY created_at DESC",
                params
            ).fetchall()
            resources = [self._row_to_course_resource(r) for r in rows]
            if tag:
                tag_clean = tag.strip().lstrip("#").lower()
                resources = [r for r in resources if tag_clean in [t.lower() for t in r.tags]]
            return resources
        finally:
            if not self._memory_conn: conn.close()

    def get_study_group_resources(
        self,
        study_group_id: str,
        resource_type: Optional[str] = None
    ) -> List[CourseResource]:
        conn = self.get_connection()
        try:
            clauses = ["study_group_id = ?"]
            params = [study_group_id]
            if resource_type:
                clauses.append("LOWER(resource_type) = LOWER(?)")
                params.append(resource_type.strip())
            rows = conn.execute(
                f"SELECT * FROM course_resources WHERE {' AND '.join(clauses)} ORDER BY created_at DESC",
                params
            ).fetchall()
            return [self._row_to_course_resource(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_syllabus(self, course_id: str) -> Optional[CourseResource]:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM course_resources WHERE course_id = ? AND LOWER(resource_type) = 'syllabus' ORDER BY created_at DESC LIMIT 1",
                (course_id,)
            ).fetchone()
            return self._row_to_course_resource(row) if row else None
        finally:
            if not self._memory_conn: conn.close()

    def get_course_syllabus(self, course_id: str) -> Optional[CourseResource]:
        return self.get_syllabus(course_id)

    def endorse_resource(self, resource_id: str, actor_id: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        actor = actor_id or user_id
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE course_resources SET endorsements_count = endorsements_count + 1 WHERE id = ?",
                (resource_id,)
            )
            conn.commit()
            if cursor.rowcount > 0 and actor:
                res = self.get_course_resource(resource_id)
                if res and res.uploader_id and res.uploader_id != actor:
                    self.create_notification(Notification(
                        id=str(uuid.uuid4()),
                        user_id=res.uploader_id,
                        type="resource_endorsed",
                        actor_id=actor,
                        target_id=resource_id,
                        content=f"Resource endorsed: {res.title[:80]}"
                    ))
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def endorse_course_resource(self, resource_id: str, actor_id: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        return self.endorse_resource(resource_id, actor_id=actor_id, user_id=user_id)

    def upvote_resource(self, resource_id: str, actor_id: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        actor = actor_id or user_id
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE course_resources SET upvotes_count = upvotes_count + 1 WHERE id = ?",
                (resource_id,)
            )
            conn.commit()
            if cursor.rowcount > 0 and actor:
                res = self.get_course_resource(resource_id)
                if res and res.uploader_id and res.uploader_id != actor:
                    self.create_notification(Notification(
                        id=str(uuid.uuid4()),
                        user_id=res.uploader_id,
                        type="resource_upvoted",
                        actor_id=actor,
                        target_id=resource_id,
                        content=f"Resource upvoted: {res.title[:80]}"
                    ))
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def delete_course_resource(self, resource_id: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute("DELETE FROM course_resources WHERE id = ?", (resource_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    # --- Verified Classmate Study Groups ---
    def create_study_group(self, study_group: Any) -> StudyGroup:
        if isinstance(study_group, dict):
            sg_obj = StudyGroup(
                id=study_group.get("id") or str(uuid.uuid4()),
                name=study_group.get("name", ""),
                creator_id=study_group.get("creator_id") or study_group.get("created_by") or "",
                created_by=study_group.get("created_by") or study_group.get("creator_id") or "",
                course_id=study_group.get("course_id"),
                description=study_group.get("description", ""),
                institution=study_group.get("institution", ""),
                is_private=study_group.get("is_private", False),
                verified_only=study_group.get("verified_only", True),
                max_members=study_group.get("max_members"),
                meeting_schedule=study_group.get("meeting_schedule", "")
            )
        else:
            sg_obj = study_group

        if not sg_obj.creator_id and sg_obj.created_by:
            sg_obj.creator_id = sg_obj.created_by
        if not sg_obj.created_by and sg_obj.creator_id:
            sg_obj.created_by = sg_obj.creator_id

        if sg_obj.course_id and not sg_obj.institution:
            course = self.get_course(sg_obj.course_id)
            if course and course.institution:
                sg_obj.institution = course.institution

        conn = self.get_connection()
        try:
            created_at_str = sg_obj.created_at.isoformat() if isinstance(sg_obj.created_at, datetime) else str(sg_obj.created_at)
            conn.execute(
                """INSERT OR REPLACE INTO study_groups (
                    id, course_id, name, description, creator_id, institution,
                    is_private, verified_only, max_members, meeting_schedule, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sg_obj.id, sg_obj.course_id, sg_obj.name, sg_obj.description,
                    sg_obj.creator_id, sg_obj.institution, 1 if sg_obj.is_private else 0,
                    1 if sg_obj.verified_only else 0, sg_obj.max_members,
                    sg_obj.meeting_schedule, created_at_str
                )
            )
            # Add creator as leader member
            if sg_obj.creator_id:
                conn.execute(
                    """INSERT OR REPLACE INTO study_group_members (
                        study_group_id, user_id, role, is_verified_classmate, joined_at
                    ) VALUES (?, ?, ?, ?, ?)""",
                    (sg_obj.id, sg_obj.creator_id, "leader", 1, created_at_str)
                )
            conn.commit()
            return sg_obj
        finally:
            if not self._memory_conn: conn.close()

    def get_study_group(self, study_group_id: str) -> Optional[StudyGroup]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM study_groups WHERE id = ?", (study_group_id,)).fetchone()
            return self._row_to_study_group(row) if row else None
        finally:
            if not self._memory_conn: conn.close()

    def get_study_groups(
        self,
        course_id: Optional[str] = None,
        institution: Optional[str] = None,
        user_id: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[StudyGroup]:
        conn = self.get_connection()
        try:
            if user_id:
                rows = conn.execute(
                    """SELECT g.* FROM study_groups g
                       INNER JOIN study_group_members m ON g.id = m.study_group_id
                       WHERE m.user_id = ?
                       ORDER BY g.created_at DESC""",
                    (user_id,)
                ).fetchall()
                return [self._row_to_study_group(r) for r in rows]

            clauses = []
            params = []
            if course_id:
                clauses.append("course_id = ?")
                params.append(course_id)
            if institution:
                clauses.append("LOWER(institution) LIKE ?")
                params.append(f"%{institution.strip().lower()}%")
            if query:
                clauses.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ?)")
                q = f"%{query.strip().lower()}%"
                params.extend([q, q])

            where_str = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(f"SELECT * FROM study_groups{where_str} ORDER BY created_at DESC", params).fetchall()
            return [self._row_to_study_group(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_course_study_groups(self, course_id: str) -> List[StudyGroup]:
        return self.get_study_groups(course_id=course_id)

    def get_user_study_groups(self, user_id: str) -> List[StudyGroup]:
        return self.get_study_groups(user_id=user_id)

    def search_study_groups(self, query: str, course_id: Optional[str] = None, institution: Optional[str] = None) -> List[StudyGroup]:
        return self.get_study_groups(course_id=course_id, institution=institution, query=query)

    def join_study_group(
        self,
        study_group_id: str,
        user_id: str,
        role: str = "member",
        force_verify: bool = False
    ) -> StudyGroupMember:
        group = self.get_study_group(study_group_id)
        if not group:
            raise ValueError("Study group not found")

        if self.is_study_group_member(study_group_id, user_id):
            return self.get_study_group_member(study_group_id, user_id)

        if group.max_members is not None and group.max_members > 0:
            current_members = self.get_study_group_members(study_group_id)
            if len(current_members) >= group.max_members:
                raise ValueError("Study group is at maximum capacity")

        is_verified = True
        if group.verified_only and not force_verify:
            is_verified = self.is_verified_classmate(
                user_id_1=user_id,
                course_id=group.course_id,
                study_group_id=study_group_id
            )
            if not is_verified:
                raise PermissionError("Only verified classmates can join this study group")

        conn = self.get_connection()
        try:
            joined_at_dt = datetime.utcnow()
            joined_at_str = joined_at_dt.isoformat()
            conn.execute(
                """INSERT OR REPLACE INTO study_group_members (
                    study_group_id, user_id, role, is_verified_classmate, joined_at
                ) VALUES (?, ?, ?, ?, ?)""",
                (study_group_id, user_id, role, 1 if is_verified else 0, joined_at_str)
            )
            conn.commit()
            return StudyGroupMember(
                study_group_id=study_group_id,
                user_id=user_id,
                role=role,
                is_verified_classmate=bool(is_verified),
                joined_at=joined_at_dt
            )
        finally:
            if not self._memory_conn: conn.close()

    def leave_study_group(self, study_group_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM study_group_members WHERE study_group_id = ? AND user_id = ?",
                (study_group_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def get_study_group_members(self, study_group_id: str) -> List[StudyGroupMember]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM study_group_members WHERE study_group_id = ? ORDER BY joined_at ASC",
                (study_group_id,)
            ).fetchall()
            return [self._row_to_study_group_member(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def is_study_group_member(self, study_group_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM study_group_members WHERE study_group_id = ? AND user_id = ?",
                (study_group_id, user_id)
            ).fetchone()
            return row is not None
        finally:
            if not self._memory_conn: conn.close()

    def get_study_group_member(self, study_group_id: str, user_id: str) -> Optional[StudyGroupMember]:
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM study_group_members WHERE study_group_id = ? AND user_id = ?",
                (study_group_id, user_id)
            ).fetchone()
            return self._row_to_study_group_member(row) if row else None
        finally:
            if not self._memory_conn: conn.close()

    def update_study_group_member_role(self, study_group_id: str, user_id: str, role: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE study_group_members SET role = ? WHERE study_group_id = ? AND user_id = ?",
                (role, study_group_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def remove_study_group_member(self, study_group_id: str, user_id: str) -> bool:
        return self.leave_study_group(study_group_id, user_id)

    def update_study_group(self, study_group_id: str, **kwargs) -> Optional[StudyGroup]:
        group = self.get_study_group(study_group_id)
        if not group:
            return None
        conn = self.get_connection()
        try:
            valid_fields = ["name", "description", "institution", "course_id", "is_private", "verified_only", "max_members", "meeting_schedule"]
            set_clauses = []
            params = []
            for k, v in kwargs.items():
                if k in ("university", "school"):
                    field_name = "institution"
                elif k in valid_fields:
                    field_name = k
                else:
                    continue

                if field_name in ("is_private", "verified_only"):
                    v = 1 if v else 0
                set_clauses.append(f"{field_name} = ?")
                params.append(v)

            if set_clauses:
                params.append(study_group_id)
                conn.execute(f"UPDATE study_groups SET {', '.join(set_clauses)} WHERE id = ?", params)
                conn.commit()
            return self.get_study_group(study_group_id)
        finally:
            if not self._memory_conn: conn.close()

    def delete_study_group(self, study_group_id: str) -> bool:
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM study_group_members WHERE study_group_id = ?", (study_group_id,))
            cursor = conn.execute("DELETE FROM study_groups WHERE id = ?", (study_group_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    # Academic Space & Resource Aliases
    def add_course(self, course: Any) -> Optional[Course]:
        return self.create_course(course)

    def add_study_group(self, study_group: Any) -> StudyGroup:
        return self.create_study_group(study_group)

    def get_academic_space(self, course_id: str) -> Optional[Course]:
        return self.get_course(course_id)

    def get_academic_spaces(self, **kwargs) -> List[Course]:
        return self.get_courses(**kwargs)

    def search_academic_spaces(self, query: str, **kwargs) -> List[Course]:
        return self.search_courses(query, **kwargs)

    def get_resource(self, resource_id: str) -> Optional[CourseResource]:
        return self.get_course_resource(resource_id)

    def delete_resource(self, resource_id: str) -> bool:
        return self.delete_course_resource(resource_id)

    # =========================================================================
    # --- Media Accessibility Metadata (Alt-Text, Audio Transcripts) ---
    # =========================================================================

    def _row_to_media(self, r) -> MediaAttachment:
        cw_val = r["content_warnings"] if "content_warnings" in r.keys() and r["content_warnings"] else "[]"
        if isinstance(cw_val, str):
            try:
                cw_list = json.loads(cw_val)
            except Exception:
                cw_list = [w.strip().lstrip("#").lower() for w in cw_val.split(",") if w.strip()]
        elif isinstance(cw_val, list):
            cw_list = cw_val
        else:
            cw_list = []

        return MediaAttachment(
            id=r["id"],
            url=r["url"],
            media_type=r["media_type"] if "media_type" in r.keys() else "image",
            alt_text=r["alt_text"] if "alt_text" in r.keys() else None,
            audio_transcript=r["audio_transcript"] if "audio_transcript" in r.keys() else None,
            captions_url=r["captions_url"] if "captions_url" in r.keys() else None,
            description=r["description"] if "description" in r.keys() else "",
            discussion_id=r["discussion_id"] if "discussion_id" in r.keys() else None,
            uploader_id=r["uploader_id"] if "uploader_id" in r.keys() else None,
            content_warnings=cw_list,
            is_sensitive=bool(r["is_sensitive"]) if "is_sensitive" in r.keys() else False,
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"]
        )

    def create_media(self, media: Any) -> MediaAttachment:
        if isinstance(media, dict):
            m_id = media.get("id") or str(uuid.uuid4())
            m_obj = MediaAttachment(
                id=m_id,
                url=media.get("url", ""),
                media_type=media.get("media_type", "image"),
                alt_text=media.get("alt_text"),
                audio_transcript=media.get("audio_transcript") or media.get("transcript"),
                captions_url=media.get("captions_url"),
                description=media.get("description", ""),
                discussion_id=media.get("discussion_id"),
                uploader_id=media.get("uploader_id"),
                content_warnings=media.get("content_warnings", []),
                is_sensitive=bool(media.get("is_sensitive", False)),
                created_at=media.get("created_at") or datetime.utcnow()
            )
        else:
            m_obj = media
            if not m_obj.id:
                m_obj.id = str(uuid.uuid4())

        conn = self.get_connection()
        try:
            cw_json = json.dumps(getattr(m_obj, "content_warnings", []) or [])
            created_at_str = m_obj.created_at.isoformat() if isinstance(m_obj.created_at, datetime) else str(m_obj.created_at)
            conn.execute(
                """INSERT OR REPLACE INTO media_attachments (
                    id, url, media_type, alt_text, audio_transcript, captions_url,
                    description, discussion_id, uploader_id, content_warnings, is_sensitive, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    m_obj.id, m_obj.url, m_obj.media_type, m_obj.alt_text,
                    m_obj.audio_transcript, m_obj.captions_url, m_obj.description,
                    m_obj.discussion_id, m_obj.uploader_id, cw_json,
                    1 if m_obj.is_sensitive else 0, created_at_str
                )
            )
            conn.commit()
            return m_obj
        finally:
            if not self._memory_conn: conn.close()

    def add_media(self, media: Any) -> MediaAttachment:
        return self.create_media(media)

    def get_media(self, media_id: str) -> Optional[MediaAttachment]:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM media_attachments WHERE id = ?", (media_id,)).fetchone()
            return self._row_to_media(row) if row else None
        finally:
            if not self._memory_conn: conn.close()

    def get_media_for_discussion(self, discussion_id: str) -> List[MediaAttachment]:
        conn = self.get_connection()
        try:
            rows = conn.execute("SELECT * FROM media_attachments WHERE discussion_id = ? ORDER BY created_at ASC", (discussion_id,)).fetchall()
            return [self._row_to_media(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def get_discussion_media(self, discussion_id: str) -> List[MediaAttachment]:
        return self.get_media_for_discussion(discussion_id)

    def get_user_media(self, uploader_id: str) -> List[MediaAttachment]:
        conn = self.get_connection()
        try:
            rows = conn.execute("SELECT * FROM media_attachments WHERE uploader_id = ? ORDER BY created_at DESC", (uploader_id,)).fetchall()
            return [self._row_to_media(r) for r in rows]
        finally:
            if not self._memory_conn: conn.close()

    def update_media_accessibility(
        self,
        media_id: str,
        alt_text: Optional[str] = None,
        audio_transcript: Optional[str] = None,
        captions_url: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> Optional[MediaAttachment]:
        media = self.get_media(media_id)
        if not media:
            return None
        if alt_text is not None:
            media.alt_text = alt_text
        transcript_val = audio_transcript if audio_transcript is not None else kwargs.get("transcript")
        if transcript_val is not None:
            media.audio_transcript = transcript_val
        if captions_url is not None:
            media.captions_url = captions_url
        if description is not None:
            media.description = description
        if "content_warnings" in kwargs:
            media.content_warnings = kwargs["content_warnings"]
        if "is_sensitive" in kwargs:
            media.is_sensitive = bool(kwargs["is_sensitive"])
        return self.create_media(media)

    def update_media(self, media_id: str, **kwargs) -> Optional[MediaAttachment]:
        return self.update_media_accessibility(media_id, **kwargs)

    def delete_media(self, media_id: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute("DELETE FROM media_attachments WHERE id = ?", (media_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._memory_conn: conn.close()

    def attach_media_to_discussion(self, discussion_id: str, media_ids: List[str]) -> bool:
        if not media_ids:
            return False
        conn = self.get_connection()
        try:
            for mid in media_ids:
                conn.execute("UPDATE media_attachments SET discussion_id = ? WHERE id = ?", (discussion_id, mid))
            conn.commit()
            return True
        finally:
            if not self._memory_conn: conn.close()


    # =========================================================================
    # --- User Content Filtering Preferences ---
    # =========================================================================

    def _row_to_content_filter_prefs(self, r) -> ContentFilterPreferences:
        kw_val = r["mute_keywords"] if "mute_keywords" in r.keys() and r["mute_keywords"] else "[]"
        if isinstance(kw_val, str):
            try:
                kw_list = json.loads(kw_val)
            except Exception:
                kw_list = [k.strip().lower() for k in kw_val.split(",") if k.strip()]
        elif isinstance(kw_val, list):
            kw_list = kw_val
        else:
            kw_list = []

        cw_val = r["content_warning_tags"] if "content_warning_tags" in r.keys() and r["content_warning_tags"] else "[]"
        if isinstance(cw_val, str):
            try:
                cw_list = json.loads(cw_val)
            except Exception:
                cw_list = [w.strip().lstrip("#").lower() for w in cw_val.split(",") if w.strip()]
        elif isinstance(cw_val, list):
            cw_list = cw_val
        else:
            cw_list = []

        return ContentFilterPreferences(
            user_id=r["user_id"],
            mute_keywords=kw_list,
            content_warning_tags=cw_list,
            hide_sensitive_media=bool(r["hide_sensitive_media"]) if "hide_sensitive_media" in r.keys() else False,
            filter_level=r["filter_level"] if "filter_level" in r.keys() else "hide",
            filter_notifications=bool(r["filter_notifications"]) if "filter_notifications" in r.keys() else False,
            filter_direct_messages=bool(r["filter_direct_messages"]) if "filter_direct_messages" in r.keys() else False,
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
            updated_at=datetime.fromisoformat(r["updated_at"]) if isinstance(r["updated_at"], str) else r["updated_at"]
        )

    def get_content_filter_preferences(self, user_id: str) -> ContentFilterPreferences:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM user_content_filter_preferences WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return self._row_to_content_filter_prefs(row)
            return ContentFilterPreferences(user_id=user_id)
        finally:
            if not self._memory_conn: conn.close()

    def get_user_content_filters(self, user_id: str) -> ContentFilterPreferences:
        return self.get_content_filter_preferences(user_id)

    def set_content_filter_preferences(self, preferences: Any) -> ContentFilterPreferences:
        if isinstance(preferences, dict):
            user_id = preferences.get("user_id", "")
            existing = self.get_content_filter_preferences(user_id)
            mute_keywords = preferences.get("mute_keywords", preferences.get("muted_keywords", existing.mute_keywords))
            cw_tags = preferences.get("content_warning_tags", preferences.get("sensitive_tags", preferences.get("cw_tags", existing.content_warning_tags)))
            hide_media = preferences.get("hide_sensitive_media", existing.hide_sensitive_media)
            filter_level = preferences.get("filter_level", existing.filter_level)
            filter_notifs = preferences.get("filter_notifications", existing.filter_notifications)
            filter_dms = preferences.get("filter_direct_messages", existing.filter_direct_messages)

            pref_obj = ContentFilterPreferences(
                user_id=user_id,
                mute_keywords=mute_keywords,
                content_warning_tags=cw_tags,
                hide_sensitive_media=bool(hide_media),
                filter_level=str(filter_level),
                filter_notifications=bool(filter_notifs),
                filter_direct_messages=bool(filter_dms),
                created_at=existing.created_at or datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        else:
            pref_obj = preferences
            pref_obj.updated_at = datetime.utcnow()

        conn = self.get_connection()
        try:
            kw_json = json.dumps(getattr(pref_obj, "mute_keywords", []) or [])
            cw_json = json.dumps(getattr(pref_obj, "content_warning_tags", []) or [])
            created_at_str = pref_obj.created_at.isoformat() if isinstance(pref_obj.created_at, datetime) else str(pref_obj.created_at)
            updated_at_str = pref_obj.updated_at.isoformat() if isinstance(pref_obj.updated_at, datetime) else str(pref_obj.updated_at)
            conn.execute(
                """INSERT OR REPLACE INTO user_content_filter_preferences (
                    user_id, mute_keywords, content_warning_tags, hide_sensitive_media,
                    filter_level, filter_notifications, filter_direct_messages, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pref_obj.user_id, kw_json, cw_json, 1 if pref_obj.hide_sensitive_media else 0,
                    pref_obj.filter_level, 1 if pref_obj.filter_notifications else 0,
                    1 if pref_obj.filter_direct_messages else 0, created_at_str, updated_at_str
                )
            )
            conn.commit()
            return pref_obj
        finally:
            if not self._memory_conn: conn.close()

    def update_content_filter_preferences(self, user_id: str, **kwargs) -> ContentFilterPreferences:
        current = self.get_content_filter_preferences(user_id)
        if "mute_keywords" in kwargs or "muted_keywords" in kwargs:
            current.mute_keywords = kwargs.get("mute_keywords", kwargs.get("muted_keywords"))
        if "content_warning_tags" in kwargs or "sensitive_tags" in kwargs or "cw_tags" in kwargs:
            current.content_warning_tags = kwargs.get("content_warning_tags", kwargs.get("sensitive_tags", kwargs.get("cw_tags")))
        if "hide_sensitive_media" in kwargs:
            current.hide_sensitive_media = bool(kwargs["hide_sensitive_media"])
        if "filter_level" in kwargs:
            current.filter_level = str(kwargs["filter_level"])
        if "filter_notifications" in kwargs:
            current.filter_notifications = bool(kwargs["filter_notifications"])
        if "filter_direct_messages" in kwargs:
            current.filter_direct_messages = bool(kwargs["filter_direct_messages"])
        return self.set_content_filter_preferences(current)

    def add_mute_keyword(self, user_id: str, keyword: str) -> ContentFilterPreferences:
        if not keyword:
            return self.get_content_filter_preferences(user_id)
        current = self.get_content_filter_preferences(user_id)
        kw_clean = keyword.strip().lower()
        if kw_clean and kw_clean not in current.mute_keywords:
            current.mute_keywords.append(kw_clean)
            return self.set_content_filter_preferences(current)
        return current

    def remove_mute_keyword(self, user_id: str, keyword: str) -> ContentFilterPreferences:
        if not keyword:
            return self.get_content_filter_preferences(user_id)
        current = self.get_content_filter_preferences(user_id)
        kw_clean = keyword.strip().lower()
        if kw_clean in current.mute_keywords:
            current.mute_keywords.remove(kw_clean)
            return self.set_content_filter_preferences(current)
        return current

    def get_mute_keywords(self, user_id: str) -> List[str]:
        return self.get_content_filter_preferences(user_id).mute_keywords

    def add_content_warning_tag(self, user_id: str, tag: str) -> ContentFilterPreferences:
        if not tag:
            return self.get_content_filter_preferences(user_id)
        current = self.get_content_filter_preferences(user_id)
        tag_clean = tag.strip().lstrip("#").lower()
        if tag_clean and tag_clean not in current.content_warning_tags:
            current.content_warning_tags.append(tag_clean)
            return self.set_content_filter_preferences(current)
        return current

    def remove_content_warning_tag(self, user_id: str, tag: str) -> ContentFilterPreferences:
        if not tag:
            return self.get_content_filter_preferences(user_id)
        current = self.get_content_filter_preferences(user_id)
        tag_clean = tag.strip().lstrip("#").lower()
        if tag_clean in current.content_warning_tags:
            current.content_warning_tags.remove(tag_clean)
            return self.set_content_filter_preferences(current)
        return current

    def get_content_warning_tags(self, user_id: str) -> List[str]:
        return self.get_content_filter_preferences(user_id).content_warning_tags

    def should_filter_discussion_for_user(self, user_id: str, discussion: Discussion) -> bool:
        prefs = self.get_content_filter_preferences(user_id)
        if not prefs:
            return False
        # Do not filter user's own posts
        if discussion.author_id == user_id:
            return False
        return prefs.matches_filters(
            text=discussion.content,
            tags=getattr(discussion, "tags", []),
            content_warnings=getattr(discussion, "content_warnings", [])
        )

    def filter_discussions_for_user(self, user_id: str, discussions: List[Discussion]) -> List[Discussion]:
        prefs = self.get_content_filter_preferences(user_id)
        if not prefs or (not prefs.mute_keywords and not prefs.content_warning_tags):
            return discussions
        filtered = []
        for d in discussions:
            if d.author_id == user_id:
                filtered.append(d)
            elif not prefs.matches_filters(d.content, getattr(d, "tags", []), getattr(d, "content_warnings", [])):
                filtered.append(d)
        return filtered


    # =========================================================================
    # --- User Accessibility Settings ---
    # =========================================================================

    def _row_to_accessibility_settings(self, r) -> UserAccessibilitySettings:
        return UserAccessibilitySettings(
            user_id=r["user_id"],
            high_contrast=bool(r["high_contrast"]) if "high_contrast" in r.keys() else False,
            reduce_motion=bool(r["reduce_motion"]) if "reduce_motion" in r.keys() else False,
            screen_reader_optimized=bool(r["screen_reader_optimized"]) if "screen_reader_optimized" in r.keys() else False,
            font_size=r["font_size"] if "font_size" in r.keys() else "medium",
            closed_captions_enabled=bool(r["closed_captions_enabled"]) if "closed_captions_enabled" in r.keys() else False,
            audio_transcripts_enabled=bool(r["audio_transcripts_enabled"]) if "audio_transcripts_enabled" in r.keys() else True,
            alt_text_required_on_post=bool(r["alt_text_required_on_post"]) if "alt_text_required_on_post" in r.keys() else False,
            autoplay_media=bool(r["autoplay_media"]) if "autoplay_media" in r.keys() else False,
            dyslexia_font=bool(r["dyslexia_font"]) if "dyslexia_font" in r.keys() else False,
            color_blind_mode=r["color_blind_mode"] if "color_blind_mode" in r.keys() else "none",
            created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
            updated_at=datetime.fromisoformat(r["updated_at"]) if isinstance(r["updated_at"], str) else r["updated_at"]
        )

    def get_accessibility_settings(self, user_id: str) -> UserAccessibilitySettings:
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM user_accessibility_settings WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return self._row_to_accessibility_settings(row)
            return UserAccessibilitySettings(user_id=user_id)
        finally:
            if not self._memory_conn: conn.close()

    def get_user_accessibility_settings(self, user_id: str) -> UserAccessibilitySettings:
        return self.get_accessibility_settings(user_id)

    def get_user_accessibility(self, user_id: str) -> UserAccessibilitySettings:
        return self.get_accessibility_settings(user_id)

    def set_accessibility_settings(self, settings: Any) -> UserAccessibilitySettings:
        if isinstance(settings, dict):
            user_id = settings.get("user_id", "")
            existing = self.get_accessibility_settings(user_id)
            high_contrast = settings.get("high_contrast", settings.get("high_contrast_mode", existing.high_contrast))
            reduce_motion = settings.get("reduce_motion", existing.reduce_motion)
            screen_reader = settings.get("screen_reader_optimized", settings.get("screen_reader_mode", settings.get("screen_reader_enabled", existing.screen_reader_optimized)))
            font_size = settings.get("font_size", existing.font_size)
            captions = settings.get("closed_captions_enabled", settings.get("captions_enabled", existing.closed_captions_enabled))
            transcripts = settings.get("audio_transcripts_enabled", settings.get("transcripts_enabled", existing.audio_transcripts_enabled))
            alt_req = settings.get("alt_text_required_on_post", settings.get("require_alt_text", existing.alt_text_required_on_post))
            autoplay = settings.get("autoplay_media", settings.get("autoplay_videos", existing.autoplay_media))
            dyslexia = settings.get("dyslexia_font", existing.dyslexia_font)
            color_blind = settings.get("color_blind_mode", existing.color_blind_mode)

            sett_obj = UserAccessibilitySettings(
                user_id=user_id,
                high_contrast=bool(high_contrast),
                reduce_motion=bool(reduce_motion),
                screen_reader_optimized=bool(screen_reader),
                font_size=str(font_size),
                closed_captions_enabled=bool(captions),
                audio_transcripts_enabled=bool(transcripts),
                alt_text_required_on_post=bool(alt_req),
                autoplay_media=bool(autoplay),
                dyslexia_font=bool(dyslexia),
                color_blind_mode=str(color_blind),
                created_at=existing.created_at or datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        else:
            sett_obj = settings
            sett_obj.updated_at = datetime.utcnow()

        conn = self.get_connection()
        try:
            created_at_str = sett_obj.created_at.isoformat() if isinstance(sett_obj.created_at, datetime) else str(sett_obj.created_at)
            updated_at_str = sett_obj.updated_at.isoformat() if isinstance(sett_obj.updated_at, datetime) else str(sett_obj.updated_at)
            conn.execute(
                """INSERT OR REPLACE INTO user_accessibility_settings (
                    user_id, high_contrast, reduce_motion, screen_reader_optimized,
                    font_size, closed_captions_enabled, audio_transcripts_enabled,
                    alt_text_required_on_post, autoplay_media, dyslexia_font,
                    color_blind_mode, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sett_obj.user_id, 1 if sett_obj.high_contrast else 0,
                    1 if sett_obj.reduce_motion else 0, 1 if sett_obj.screen_reader_optimized else 0,
                    sett_obj.font_size, 1 if sett_obj.closed_captions_enabled else 0,
                    1 if sett_obj.audio_transcripts_enabled else 0, 1 if sett_obj.alt_text_required_on_post else 0,
                    1 if sett_obj.autoplay_media else 0, 1 if sett_obj.dyslexia_font else 0,
                    sett_obj.color_blind_mode, created_at_str, updated_at_str
                )
            )
            conn.commit()
            return sett_obj
        finally:
            if not self._memory_conn: conn.close()

    def update_accessibility_settings(self, user_id: str, **kwargs) -> UserAccessibilitySettings:
        current = self.get_accessibility_settings(user_id)
        if "high_contrast" in kwargs or "high_contrast_mode" in kwargs:
            current.high_contrast = bool(kwargs.get("high_contrast", kwargs.get("high_contrast_mode")))
        if "reduce_motion" in kwargs:
            current.reduce_motion = bool(kwargs["reduce_motion"])
        if "screen_reader_optimized" in kwargs or "screen_reader_mode" in kwargs or "screen_reader_enabled" in kwargs:
            current.screen_reader_optimized = bool(kwargs.get("screen_reader_optimized", kwargs.get("screen_reader_mode", kwargs.get("screen_reader_enabled"))))
        if "font_size" in kwargs:
            current.font_size = str(kwargs["font_size"])
        if "closed_captions_enabled" in kwargs or "captions_enabled" in kwargs:
            current.closed_captions_enabled = bool(kwargs.get("closed_captions_enabled", kwargs.get("captions_enabled")))
        if "audio_transcripts_enabled" in kwargs or "transcripts_enabled" in kwargs:
            current.audio_transcripts_enabled = bool(kwargs.get("audio_transcripts_enabled", kwargs.get("transcripts_enabled")))
        if "alt_text_required_on_post" in kwargs or "require_alt_text" in kwargs:
            current.alt_text_required_on_post = bool(kwargs.get("alt_text_required_on_post", kwargs.get("require_alt_text")))
        if "autoplay_media" in kwargs or "autoplay_videos" in kwargs:
            current.autoplay_media = bool(kwargs.get("autoplay_media", kwargs.get("autoplay_videos")))
        if "dyslexia_font" in kwargs:
            current.dyslexia_font = bool(kwargs["dyslexia_font"])
        if "color_blind_mode" in kwargs:
            current.color_blind_mode = str(kwargs["color_blind_mode"])
        return self.set_accessibility_settings(current)








