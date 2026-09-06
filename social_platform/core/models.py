import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

class Visibility:
    PUBLIC = "public"
    CONNECTIONS_ONLY = "connections_only"
    PRIVATE = "private"

VISIBILITY_SETTINGS = ["public", "connections_only", "connections-only", "private"]
UserVisibility = Visibility
VisibilitySetting = Visibility

class DMPrivacy:
    EVERYONE = "everyone"
    CONNECTIONS_ONLY = "connections_only"
    NOBODY = "nobody"

DM_PRIVACY_SETTINGS = ["everyone", "connections_only", "connections-only", "nobody", "all", "public", "connections", "none", "disabled"]
DirectMessagePrivacy = DMPrivacy

@dataclass
class PrivacySettings:
    user_id: str
    visibility: str = "public"
    dm_privacy: str = "everyone"
    is_publicly_discoverable: bool = False
    is_active: bool = True

    def __post_init__(self):
        if self.visibility:
            self.visibility = self.visibility.strip().lower().replace("-", "_")
        if self.dm_privacy:
            self.dm_privacy = self.dm_privacy.strip().lower().replace("-", "_")
            if self.dm_privacy in ("all", "public"):
                self.dm_privacy = "everyone"
            elif self.dm_privacy in ("connections",):
                self.dm_privacy = "connections_only"
            elif self.dm_privacy in ("none", "disabled"):
                self.dm_privacy = "nobody"

    @property
    def profile_visibility(self) -> str:
        return self.visibility

    @property
    def allow_dms_from(self) -> str:
        return self.dm_privacy

    @property
    def direct_message_privacy(self) -> str:
        return self.dm_privacy

    @property
    def is_deactivated(self) -> bool:
        return not self.is_active

    @property
    def is_public(self) -> bool:
        return self.visibility == "public"

    @property
    def is_private(self) -> bool:
        return self.visibility == "private"

    @property
    def is_connections_only(self) -> bool:
        return self.visibility in ("connections_only", "connections-only", "connections")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "visibility": self.visibility,
            "profile_visibility": self.visibility,
            "dm_privacy": self.dm_privacy,
            "allow_dms_from": self.dm_privacy,
            "direct_message_privacy": self.dm_privacy,
            "is_publicly_discoverable": self.is_publicly_discoverable,
            "is_active": self.is_active,
            "is_deactivated": not self.is_active
        }

UserPrivacySettings = PrivacySettings

@dataclass
class User:
    id: str
    username: str
    is_active: bool = True
    # Privacy by default: explicit opt-in required for public indexing
    is_publicly_discoverable: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    bio: str = ""
    avatar_url: Optional[str] = None
    school: str = ""
    university: str = ""
    class_year: str = ""
    interests: List[str] = field(default_factory=list)
    visibility: str = "public"
    dm_privacy: str = "everyone"

    def __post_init__(self):
        if isinstance(self.interests, str):
            try:
                self.interests = json.loads(self.interests)
            except Exception:
                self.interests = [i.strip() for i in self.interests.split(",") if i.strip()]
        elif self.interests is None:
            self.interests = []
        elif not isinstance(self.interests, list):
            self.interests = list(self.interests)

        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

        if self.visibility:
            self.visibility = self.visibility.strip().lower().replace("-", "_")

        if self.dm_privacy:
            self.dm_privacy = self.dm_privacy.strip().lower().replace("-", "_")
            if self.dm_privacy in ("all", "public"):
                self.dm_privacy = "everyone"
            elif self.dm_privacy in ("connections",):
                self.dm_privacy = "connections_only"
            elif self.dm_privacy in ("none", "disabled"):
                self.dm_privacy = "nobody"

    @property
    def topic_interests(self) -> List[str]:
        return self.interests

    @property
    def class_affiliation(self) -> str:
        return self.class_year

    @property
    def is_deactivated(self) -> bool:
        return not self.is_active

    @property
    def profile_visibility(self) -> str:
        return self.visibility

    @property
    def allow_dms_from(self) -> str:
        return self.dm_privacy

    @property
    def direct_message_privacy(self) -> str:
        return self.dm_privacy

    @property
    def is_public(self) -> bool:
        return self.visibility == "public"

    @property
    def is_private(self) -> bool:
        return self.visibility == "private"

    @property
    def is_connections_only(self) -> bool:
        return self.visibility in ("connections_only", "connections-only", "connections")

    @property
    def privacy_settings(self) -> PrivacySettings:
        return PrivacySettings(
            user_id=self.id,
            visibility=self.visibility,
            dm_privacy=self.dm_privacy,
            is_publicly_discoverable=self.is_publicly_discoverable,
            is_active=self.is_active
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "is_active": self.is_active,
            "is_publicly_discoverable": self.is_publicly_discoverable,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "school": self.school,
            "university": self.university,
            "class_year": self.class_year,
            "interests": self.interests,
            "visibility": self.visibility,
            "profile_visibility": self.visibility,
            "dm_privacy": self.dm_privacy,
            "allow_dms_from": self.dm_privacy,
            "direct_message_privacy": self.dm_privacy
        }


@dataclass
class Connection:
    follower_id: str
    followed_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "follower_id": self.follower_id,
            "followed_id": self.followed_id,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

import re

class ContentLifecycleState:
    ACTIVE = "active"
    DRAFT = "draft"
    REPORTED = "reported"
    MODERATED = "moderated"
    HIDDEN = "hidden"
    QUARANTINED = "quarantined"
    APPEALED = "appealed"
    UNDER_APPEAL = "under_appeal"
    REMOVED = "removed"
    DELETED = "deleted"
    RESTORED = "restored"

ContentStatus = ContentLifecycleState
ContentState = ContentLifecycleState

class ContentLifecycleAction:
    CREATE = "create"
    INTERACT = "interact"
    ENDORSE = "endorse"
    REPLY = "reply"
    REPORT = "report"
    MODERATE = "moderate"
    HIDE = "hide"
    UNHIDE = "unhide"
    FLAG = "flag"
    QUARANTINE = "quarantine"
    APPEAL = "appeal"
    REVIEW_APPEAL = "review_appeal"
    APPROVE_APPEAL = "approve_appeal"
    REJECT_APPEAL = "reject_appeal"
    REMOVE = "remove"
    DELETE = "delete"
    RESTORE = "restore"

@dataclass
class ContentLifecycleEvent:
    id: str
    target_type: str
    target_id: str
    event_type: str
    actor_id: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if isinstance(self.metadata, str):
            try:
                self.metadata = json.loads(self.metadata)
            except Exception:
                self.metadata = {}
        elif self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "reason": self.reason,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

@dataclass
class ContentInteraction:
    id: str
    target_type: str = "discussion"
    target_id: str = ""
    user_id: str = ""
    interaction_type: str = "endorse"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if isinstance(self.metadata, str):
            try:
                self.metadata = json.loads(self.metadata)
            except Exception:
                self.metadata = {}
        elif self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "user_id": self.user_id,
            "interaction_type": self.interaction_type,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

@dataclass
class Discussion:
    id: str
    author_id: str
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    # Value over engagement: users can endorse a discussion for its value, but no "like" counters are publicly pushed by default.
    value_endorsements: int = 0
    weighted_value_endorsements: float = 0.0
    domain: Optional[str] = None
    domain_reputation_score: float = 0.0
    parent_id: Optional[str] = None
    community_id: Optional[str] = None
    channel_id: Optional[str] = None
    is_hidden: bool = False
    course_id: Optional[str] = None
    study_group_id: Optional[str] = None
    explanation_tags: List[str] = field(default_factory=list)
    explanation: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    visibility: str = "public"
    content_warnings: List[str] = field(default_factory=list)
    alt_text: Optional[str] = None
    audio_transcript: Optional[str] = None
    media: List[Any] = field(default_factory=list)
    status: str = "active"
    moderation_status: str = "none"
    moderated_by: Optional[str] = None
    moderated_at: Optional[datetime] = None
    moderation_action: Optional[str] = None
    moderation_reason: Optional[str] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    removal_reason: Optional[str] = None
    report_count: int = 0
    last_interacted_at: Optional[datetime] = None
    interaction_count: int = 0

    def __post_init__(self):
        if isinstance(self.tags, str):
            try:
                self.tags = json.loads(self.tags)
            except Exception:
                self.tags = [t.strip().lstrip("#").lower() for t in self.tags.split(",") if t.strip()]
        elif self.tags is None:
            self.tags = []
        elif not isinstance(self.tags, list):
            self.tags = list(self.tags)

        # Normalize tags
        normalized_tags = []
        for t in self.tags:
            if isinstance(t, str):
                cleaned = t.strip().lstrip("#").lower()
                if cleaned and cleaned not in normalized_tags:
                    normalized_tags.append(cleaned)
        self.tags = normalized_tags

        # Extract hashtags from content
        if self.content:
            hashtags = re.findall(r'#([a-zA-Z0-9_-]+)', self.content)
            for ht in hashtags:
                ht_clean = ht.lower()
                if ht_clean not in self.tags:
                    self.tags.append(ht_clean)

        # Normalize content warnings
        if isinstance(self.content_warnings, str):
            try:
                self.content_warnings = json.loads(self.content_warnings)
            except Exception:
                self.content_warnings = [w.strip().lstrip("#").lower() for w in self.content_warnings.split(",") if w.strip()]
        elif self.content_warnings is None:
            self.content_warnings = []
        elif not isinstance(self.content_warnings, list):
            self.content_warnings = list(self.content_warnings)
        self.content_warnings = [str(w).strip().lstrip("#").lower() for w in self.content_warnings if str(w).strip()]

        if isinstance(self.media, str):
            try:
                self.media = json.loads(self.media)
            except Exception:
                self.media = []
        elif self.media is None:
            self.media = []
        elif not isinstance(self.media, list):
            self.media = list(self.media)

        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

        for dt_field in ("moderated_at", "deleted_at", "last_interacted_at"):
            val = getattr(self, dt_field, None)
            if isinstance(val, str) and val:
                try:
                    setattr(self, dt_field, datetime.fromisoformat(val))
                except Exception:
                    pass

        if self.status:
            self.status = str(self.status).strip().lower()
        else:
            self.status = "active"

        if self.deleted_at is not None or self.status in ("removed", "deleted"):
            self.is_hidden = True

        if self.visibility:
            self.visibility = self.visibility.strip().lower().replace("-", "_")

    @property
    def topic_tags(self) -> List[str]:
        return self.tags

    @property
    def hashtags(self) -> List[str]:
        return [f"#{t}" for t in self.tags]

    @property
    def content_warning_tags(self) -> List[str]:
        return self.content_warnings

    @property
    def cw_tags(self) -> List[str]:
        return self.content_warnings

    @property
    def endorsements_count(self) -> int:
        return self.value_endorsements

    @property
    def has_content_warning(self) -> bool:
        return len(self.content_warnings) > 0

    @property
    def media_attachments(self) -> List[Any]:
        return self.media

    @property
    def is_public(self) -> bool:
        return self.visibility == "public"

    @property
    def is_private(self) -> bool:
        return self.visibility == "private"

    @property
    def is_connections_only(self) -> bool:
        return self.visibility in ("connections_only", "connections-only", "connections")

    @property
    def lifecycle_state(self) -> str:
        return self.status

    @property
    def lifecycle_status(self) -> str:
        return self.status

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "restored") and not self.is_hidden and self.deleted_at is None

    @property
    def is_removed(self) -> bool:
        return self.status in ("removed", "deleted") or self.deleted_at is not None

    @property
    def is_moderated(self) -> bool:
        return self.status in ("moderated", "hidden", "quarantined") or self.moderated_at is not None

    @property
    def is_appealed(self) -> bool:
        return self.status in ("appealed", "under_appeal")

    @property
    def is_under_appeal(self) -> bool:
        return self.status in ("appealed", "under_appeal")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "author_id": self.author_id,
            "content": self.content,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "value_endorsements": self.value_endorsements,
            "endorsements_count": self.value_endorsements,
            "weighted_value_endorsements": getattr(self, "weighted_value_endorsements", float(self.value_endorsements)),
            "domain": getattr(self, "domain", None),
            "domain_reputation_score": getattr(self, "domain_reputation_score", 0.0),
            "parent_id": self.parent_id,
            "community_id": self.community_id,
            "channel_id": self.channel_id,
            "course_id": self.course_id,
            "study_group_id": self.study_group_id,
            "is_hidden": self.is_hidden,
            "tags": self.tags,
            "explanation_tags": self.explanation_tags,
            "explanation": self.explanation,
            "visibility": self.visibility,
            "content_warnings": self.content_warnings,
            "content_warning_tags": self.content_warnings,
            "cw_tags": self.content_warnings,
            "has_content_warning": self.has_content_warning,
            "alt_text": self.alt_text,
            "audio_transcript": self.audio_transcript,
            "media": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.media],
            "media_attachments": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.media],
            "status": self.status,
            "lifecycle_state": self.status,
            "lifecycle_status": self.status,
            "moderation_status": self.moderation_status,
            "moderated_by": self.moderated_by,
            "moderated_at": self.moderated_at.isoformat() if isinstance(self.moderated_at, datetime) else (str(self.moderated_at) if self.moderated_at else None),
            "moderation_action": self.moderation_action,
            "moderation_reason": self.moderation_reason,
            "deleted_at": self.deleted_at.isoformat() if isinstance(self.deleted_at, datetime) else (str(self.deleted_at) if self.deleted_at else None),
            "deleted_by": self.deleted_by,
            "removal_reason": self.removal_reason,
            "report_count": self.report_count,
            "last_interacted_at": self.last_interacted_at.isoformat() if isinstance(self.last_interacted_at, datetime) else (str(self.last_interacted_at) if self.last_interacted_at else None),
            "interaction_count": self.interaction_count,
            "is_active": self.is_active,
            "is_removed": self.is_removed,
            "is_moderated": self.is_moderated,
            "is_appealed": self.is_appealed
        }

@dataclass
class FeedItem:
    discussion: Discussion
    explanation_tags: List[str] = field(default_factory=list)
    explanation: str = ""
    mode: str = "chronological"
    score: float = 0.0
    matched_interests: List[str] = field(default_factory=list)
    media: List[Any] = field(default_factory=list)
    content_warnings: List[str] = field(default_factory=list)
    is_filtered: bool = False
    filter_reasons: List[str] = field(default_factory=list)
    weighted_value_endorsements: float = 0.0
    domain: Optional[str] = None
    domain_reputation_score: float = 0.0

    def __post_init__(self):
        if not self.explanation_tags and hasattr(self.discussion, "explanation_tags") and self.discussion.explanation_tags:
            self.explanation_tags = list(self.discussion.explanation_tags)
        elif self.explanation_tags and hasattr(self.discussion, "explanation_tags"):
            self.discussion.explanation_tags = self.explanation_tags
        if not self.explanation and hasattr(self.discussion, "explanation") and self.discussion.explanation:
            self.explanation = self.discussion.explanation
        elif self.explanation and hasattr(self.discussion, "explanation"):
            self.discussion.explanation = self.explanation

        if not self.media and hasattr(self.discussion, "media") and self.discussion.media:
            self.media = list(self.discussion.media)
        if not self.content_warnings and hasattr(self.discussion, "content_warnings") and self.discussion.content_warnings:
            self.content_warnings = list(self.discussion.content_warnings)

    @property
    def id(self) -> str:
        return self.discussion.id

    @property
    def author_id(self) -> str:
        return self.discussion.author_id

    @property
    def content(self) -> str:
        return self.discussion.content

    @property
    def created_at(self) -> datetime:
        return self.discussion.created_at

    @property
    def value_endorsements(self) -> int:
        return self.discussion.value_endorsements

    @property
    def endorsements_count(self) -> int:
        return self.discussion.value_endorsements

    @property
    def weighted_endorsements(self) -> float:
        return self.weighted_value_endorsements or getattr(self.discussion, "weighted_value_endorsements", float(self.discussion.value_endorsements))

    @property
    def parent_id(self) -> Optional[str]:
        return self.discussion.parent_id

    @property
    def community_id(self) -> Optional[str]:
        return self.discussion.community_id

    @property
    def channel_id(self) -> Optional[str]:
        return self.discussion.channel_id

    @property
    def course_id(self) -> Optional[str]:
        return getattr(self.discussion, "course_id", None)

    @property
    def study_group_id(self) -> Optional[str]:
        return getattr(self.discussion, "study_group_id", None)

    @property
    def is_hidden(self) -> bool:
        return self.discussion.is_hidden

    @property
    def tags(self) -> List[str]:
        return getattr(self.discussion, "tags", [])

    @property
    def topic_tags(self) -> List[str]:
        return getattr(self.discussion, "tags", [])

    @property
    def hashtags(self) -> List[str]:
        return getattr(self.discussion, "hashtags", [f"#{t}" for t in self.tags])

    @property
    def content_warning_tags(self) -> List[str]:
        return self.content_warnings

    @property
    def cw_tags(self) -> List[str]:
        return self.content_warnings

    @property
    def has_content_warning(self) -> bool:
        return len(self.content_warnings) > 0

    @property
    def media_attachments(self) -> List[Any]:
        return self.media

    def __getitem__(self, key: str) -> Any:
        if key in ("explanation_tags", "explanation", "mode", "score", "matched_interests", "discussion", "tags", "topic_tags", "hashtags", "course_id", "study_group_id", "media", "content_warnings", "is_filtered", "filter_reasons", "weighted_value_endorsements", "domain", "domain_reputation_score"):
            return getattr(self, key)
        return getattr(self.discussion, key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.discussion.id,
            "author_id": self.discussion.author_id,
            "content": self.discussion.content,
            "created_at": self.discussion.created_at.isoformat() if isinstance(self.discussion.created_at, datetime) else str(self.discussion.created_at),
            "value_endorsements": self.discussion.value_endorsements,
            "endorsements_count": self.discussion.value_endorsements,
            "weighted_value_endorsements": self.weighted_value_endorsements or getattr(self.discussion, "weighted_value_endorsements", float(self.discussion.value_endorsements)),
            "domain": self.domain or getattr(self.discussion, "domain", None),
            "domain_reputation_score": self.domain_reputation_score or getattr(self.discussion, "domain_reputation_score", 0.0),
            "parent_id": self.discussion.parent_id,
            "community_id": self.discussion.community_id,
            "channel_id": self.discussion.channel_id,
            "course_id": self.course_id,
            "study_group_id": self.study_group_id,
            "is_hidden": self.discussion.is_hidden,
            "tags": self.tags,
            "explanation_tags": self.explanation_tags,
            "explanation": self.explanation,
            "mode": self.mode,
            "score": self.score,
            "matched_interests": self.matched_interests,
            "media": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.media],
            "media_attachments": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.media],
            "content_warnings": self.content_warnings,
            "content_warning_tags": self.content_warnings,
            "cw_tags": self.content_warnings,
            "has_content_warning": self.has_content_warning,
            "is_filtered": self.is_filtered,
            "filter_reasons": self.filter_reasons,
            "discussion": self.discussion.to_dict() if hasattr(self.discussion, "to_dict") else (self.discussion.__dict__ if hasattr(self.discussion, "__dict__") else {})
        }


@dataclass
class TopicSubscription:
    user_id: str
    topic: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.topic and isinstance(self.topic, str):
            self.topic = self.topic.strip().lstrip("#").lower()

    @property
    def hashtag(self) -> str:
        return f"#{self.topic}" if self.topic else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "topic": self.topic,
            "hashtag": self.hashtag,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }


@dataclass
class TopicTrend:
    topic: str
    count: int = 0
    discussion_count: int = 0
    score: float = 0.0

    @property
    def tag(self) -> str:
        return self.topic

    @property
    def hashtag(self) -> str:
        return f"#{self.topic}" if self.topic else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "tag": self.topic,
            "hashtag": self.hashtag,
            "count": self.count,
            "discussion_count": self.discussion_count or self.count,
            "score": self.score
        }



class CommunityRole:
    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"

COMMUNITY_ROLES = ["owner", "admin", "moderator", "member"]

@dataclass
class Community:
    id: str
    name: str
    creator_id: str = ""
    description: str = ""
    is_private: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_public(self) -> bool:
        return not self.is_private

    @property
    def visibility(self) -> str:
        return "private" if self.is_private else "public"

    @property
    def rules(self) -> str:
        return ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "creator_id": self.creator_id,
            "description": self.description,
            "is_private": self.is_private,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

@dataclass
class CommunityMember:
    community_id: str
    user_id: str
    role: str = "member"
    joined_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_owner(self) -> bool:
        return self.role == CommunityRole.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role in (CommunityRole.OWNER, CommunityRole.ADMIN)

    @property
    def is_moderator(self) -> bool:
        return self.role in (CommunityRole.OWNER, CommunityRole.ADMIN, CommunityRole.MODERATOR)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "community_id": self.community_id,
            "user_id": self.user_id,
            "role": self.role,
            "joined_at": self.joined_at.isoformat() if isinstance(self.joined_at, datetime) else str(self.joined_at)
        }

@dataclass
class CommunityJoinRequest:
    id: str
    community_id: str
    user_id: str
    status: str = "pending"  # "pending", "approved", "rejected"
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "community_id": self.community_id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if isinstance(self.reviewed_at, datetime) else (str(self.reviewed_at) if self.reviewed_at else None),
            "message": self.message,
        }

@dataclass
class CommunityInvite:
    id: str
    community_id: str
    token: str
    created_by: str
    role: str = "member"
    max_uses: Optional[int] = None
    uses_count: int = 0
    expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.expires_at, str):
            try:
                self.expires_at = datetime.fromisoformat(self.expires_at)
            except Exception:
                pass
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        exp = self.expires_at if isinstance(self.expires_at, datetime) else datetime.fromisoformat(self.expires_at)
        return datetime.utcnow() > exp

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.is_expired:
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "community_id": self.community_id,
            "token": self.token,
            "created_by": self.created_by,
            "role": self.role,
            "max_uses": self.max_uses,
            "uses_count": self.uses_count,
            "expires_at": self.expires_at.isoformat() if isinstance(self.expires_at, datetime) else (str(self.expires_at) if self.expires_at else None),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "is_valid": self.is_valid
        }

CommunityInviteToken = CommunityInvite

@dataclass
class Channel:
    id: str
    community_id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

REPORT_REASON_CATEGORIES: List[str] = [
    "spam", "harassment", "hate_speech", "misinformation",
    "violence", "copyright", "inappropriate", "privacy_violation",
    "impersonation", "other"
]
REPORT_CATEGORIES = REPORT_REASON_CATEGORIES
REPORT_REASONS = REPORT_REASON_CATEGORIES

class ReportCategory:
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    MISINFORMATION = "misinformation"
    VIOLENCE = "violence"
    COPYRIGHT = "copyright"
    INAPPROPRIATE = "inappropriate"
    PRIVACY_VIOLATION = "privacy_violation"
    IMPERSONATION = "impersonation"
    OTHER = "other"

ReportReason = ReportCategory

class ReportStatus:
    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ACTIONED = "actioned"
    UNDER_REVIEW = "under_review"

class AppealStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_REVIEW = "under_review"

@dataclass
class ModerationReport:
    id: str
    reporter_id: str
    target_type: str
    target_id: str
    reason: str
    category: str = "other"
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    report_count: int = 1
    reporter_ids: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    details: str = ""
    action_taken: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if isinstance(self.resolved_at, str):
            try:
                self.resolved_at = datetime.fromisoformat(self.resolved_at)
            except Exception:
                pass

        if isinstance(self.reporter_ids, str):
            try:
                self.reporter_ids = json.loads(self.reporter_ids)
            except Exception:
                self.reporter_ids = [r.strip() for r in self.reporter_ids.split(",") if r.strip()]
        elif self.reporter_ids is None:
            self.reporter_ids = []
        elif not isinstance(self.reporter_ids, list):
            self.reporter_ids = list(self.reporter_ids)

        if not self.reporter_ids and self.reporter_id:
            self.reporter_ids = [self.reporter_id]

        if isinstance(self.reasons, str):
            try:
                self.reasons = json.loads(self.reasons)
            except Exception:
                self.reasons = [r.strip() for r in self.reasons.split(",") if r.strip()]
        elif self.reasons is None:
            self.reasons = []
        elif not isinstance(self.reasons, list):
            self.reasons = list(self.reasons)

        if not self.reasons and self.reason:
            self.reasons = [self.reason]

    @property
    def reason_category(self) -> str:
        return self.category

    @property
    def count(self) -> int:
        return self.report_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "reporter_id": self.reporter_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "reason": self.reason,
            "category": self.category,
            "reason_category": self.category,
            "status": self.status,
            "report_count": self.report_count,
            "count": self.report_count,
            "reporter_ids": self.reporter_ids,
            "reasons": self.reasons,
            "details": self.details,
            "action_taken": self.action_taken,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if isinstance(self.resolved_at, datetime) else (str(self.resolved_at) if self.resolved_at else None),
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
        }

ContentReport = ModerationReport

@dataclass
class ModerationAppeal:
    id: str
    target_type: str
    target_id: str
    appellant_id: str
    reason: str
    report_id: Optional[str] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    notes: str = ""
    action_taken: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if isinstance(self.reviewed_at, str):
            try:
                self.reviewed_at = datetime.fromisoformat(self.reviewed_at)
            except Exception:
                pass

    @property
    def user_id(self) -> str:
        return self.appellant_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "report_id": self.report_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "appellant_id": self.appellant_id,
            "user_id": self.appellant_id,
            "reason": self.reason,
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if isinstance(self.reviewed_at, datetime) else (str(self.reviewed_at) if self.reviewed_at else None),
            "notes": self.notes,
            "action_taken": self.action_taken,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
        }

ContentAppeal = ModerationAppeal


@dataclass
class CommunityBan:
    community_id: str
    user_id: str
    banned_by: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "community_id": self.community_id,
            "user_id": self.user_id,
            "banned_by": self.banned_by,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

@dataclass
class Notification:
    id: str
    user_id: str
    type: str  # "mention", "reply", "endorsement", "direct_message"
    actor_id: str
    target_id: str
    content: str = ""
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "content": self.content,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

@dataclass
class UserBlock:
    blocker_id: str
    blocked_id: str
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "blocked_id": self.blocked_id,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

@dataclass
class DirectMessage:
    id: str
    sender_id: str
    recipient_id: str
    content: str
    delivery_state: str = "sent"  # "sent", "delivered", "read"
    created_at: datetime = field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None
    status: Optional[str] = None

    def __post_init__(self):
        if self.status is not None:
            self.delivery_state = self.status
        else:
            self.status = self.delivery_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "content": self.content,
            "delivery_state": self.delivery_state,
            "status": self.status or self.delivery_state,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "read_at": self.read_at.isoformat() if isinstance(self.read_at, datetime) else (str(self.read_at) if self.read_at else None)
        }


# --- Academic Study Spaces, Course Discussions, Syllabus/Resource Sharing, & Classmate Groups ---

@dataclass
class Course:
    id: str
    code: str
    title: str = ""
    name: str = ""
    department: str = ""
    institution: str = ""
    term: str = ""
    description: str = ""
    instructor: str = ""
    creator_id: str = ""
    created_by: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.title and self.name:
            self.title = self.name
        elif not self.name and self.title:
            self.name = self.title
        if not self.creator_id and self.created_by:
            self.creator_id = self.created_by
        elif not self.created_by and self.creator_id:
            self.created_by = self.creator_id
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

    @property
    def course_code(self) -> str:
        return self.code

    @property
    def university(self) -> str:
        return self.institution

    @property
    def school(self) -> str:
        return self.institution

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "course_code": self.code,
            "title": self.title,
            "name": self.name or self.title or self.code,
            "department": self.department,
            "institution": self.institution,
            "university": self.institution,
            "school": self.institution,
            "term": self.term,
            "description": self.description,
            "instructor": self.instructor,
            "creator_id": self.creator_id,
            "created_by": self.creator_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

AcademicSpace = Course
CourseSpace = Course


@dataclass
class CourseEnrollment:
    id: str
    course_id: str
    user_id: str
    role: str = "student"  # "student", "ta", "instructor", "auditor"
    is_verified: bool = True
    institution: str = ""
    term: str = ""
    verification_source: str = "institution_match"
    enrolled_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.enrolled_at, str):
            try:
                self.enrolled_at = datetime.fromisoformat(self.enrolled_at)
            except Exception:
                pass

    @property
    def is_verified_classmate(self) -> bool:
        return self.is_verified

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "course_id": self.course_id,
            "user_id": self.user_id,
            "role": self.role,
            "is_verified": self.is_verified,
            "is_verified_classmate": self.is_verified,
            "verified": self.is_verified,
            "institution": self.institution,
            "term": self.term,
            "verification_source": self.verification_source,
            "enrolled_at": self.enrolled_at.isoformat() if isinstance(self.enrolled_at, datetime) else str(self.enrolled_at)
        }

ClassmateVerification = CourseEnrollment
CourseMember = CourseEnrollment


@dataclass
class CourseResource:
    id: str
    course_id: str
    title: str
    uploader_id: str = ""
    author_id: str = ""
    description: str = ""
    resource_type: str = "syllabus"  # "syllabus", "lecture_notes", "notes", "slides", "assignment", "past_exam", "exam_prep", "reading", "study_guide", "link", "resource"
    url: str = ""
    content: str = ""
    is_official: bool = False
    study_group_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    endorsements_count: int = 0
    upvotes_count: int = 0
    weighted_endorsements_count: float = 0.0
    domain_reputation_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.uploader_id and self.author_id:
            self.uploader_id = self.author_id
        elif not self.author_id and self.uploader_id:
            self.author_id = self.uploader_id
        if self.resource_type.lower() == "syllabus":
            self.is_official = True

        if isinstance(self.tags, str):
            try:
                self.tags = json.loads(self.tags)
            except Exception:
                self.tags = [t.strip().lstrip("#").lower() for t in self.tags.split(",") if t.strip()]
        elif self.tags is None:
            self.tags = []
        elif not isinstance(self.tags, list):
            self.tags = list(self.tags)

        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

    @property
    def user_id(self) -> str:
        return self.uploader_id

    @property
    def file_url(self) -> str:
        return self.url

    @property
    def is_syllabus(self) -> bool:
        return self.resource_type.lower() == "syllabus"

    @property
    def value_endorsements(self) -> int:
        return self.endorsements_count

    @property
    def weighted_endorsements(self) -> float:
        return self.weighted_endorsements_count or float(self.endorsements_count)

    @property
    def upvotes(self) -> int:
        return self.upvotes_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "course_id": self.course_id,
            "uploader_id": self.uploader_id,
            "author_id": self.uploader_id,
            "user_id": self.uploader_id,
            "title": self.title,
            "description": self.description,
            "resource_type": self.resource_type,
            "url": self.url,
            "file_url": self.url,
            "content": self.content,
            "is_official": self.is_official,
            "study_group_id": self.study_group_id,
            "tags": self.tags,
            "endorsements_count": self.endorsements_count,
            "upvotes_count": self.upvotes_count,
            "value_endorsements": self.endorsements_count,
            "weighted_endorsements_count": self.weighted_endorsements_count or float(self.endorsements_count),
            "weighted_value_endorsements": self.weighted_endorsements_count or float(self.endorsements_count),
            "domain_reputation_score": self.domain_reputation_score,
            "upvotes": self.upvotes_count,
            "is_syllabus": self.is_syllabus,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

StudyResource = CourseResource
Syllabus = CourseResource


@dataclass
class StudyGroup:
    id: str
    name: str
    creator_id: str = ""
    created_by: str = ""
    course_id: Optional[str] = None
    description: str = ""
    institution: str = ""
    is_private: bool = False
    verified_only: bool = True
    max_members: Optional[int] = None
    meeting_schedule: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.creator_id and self.created_by:
            self.creator_id = self.created_by
        elif not self.created_by and self.creator_id:
            self.created_by = self.creator_id
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "creator_id": self.creator_id,
            "created_by": self.creator_id,
            "course_id": self.course_id,
            "description": self.description,
            "institution": self.institution,
            "is_private": self.is_private,
            "verified_only": self.verified_only,
            "max_members": self.max_members,
            "meeting_schedule": self.meeting_schedule,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

AcademicStudyGroup = StudyGroup


@dataclass
class StudyGroupMember:
    study_group_id: str
    user_id: str
    role: str = "member"  # "creator", "leader", "member"
    is_verified_classmate: bool = True
    joined_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.joined_at, str):
            try:
                self.joined_at = datetime.fromisoformat(self.joined_at)
            except Exception:
                pass

    @property
    def is_leader(self) -> bool:
        return self.role in ("leader", "creator", "admin")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "study_group_id": self.study_group_id,
            "user_id": self.user_id,
            "role": self.role,
            "is_verified_classmate": self.is_verified_classmate,
            "joined_at": self.joined_at.isoformat() if isinstance(self.joined_at, datetime) else str(self.joined_at)
        }


# =========================================================================
# --- Media Accessibility Metadata & Content Filtering Preferences ---
# =========================================================================

@dataclass
class MediaAttachment:
    id: str
    url: str
    media_type: str = "image"  # "image", "audio", "video", "document"
    alt_text: Optional[str] = None
    audio_transcript: Optional[str] = None
    captions_url: Optional[str] = None
    description: str = ""
    discussion_id: Optional[str] = None
    uploader_id: Optional[str] = None
    content_warnings: List[str] = field(default_factory=list)
    is_sensitive: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.content_warnings, str):
            try:
                self.content_warnings = json.loads(self.content_warnings)
            except Exception:
                self.content_warnings = [w.strip().lstrip("#").lower() for w in self.content_warnings.split(",") if w.strip()]
        elif self.content_warnings is None:
            self.content_warnings = []
        elif not isinstance(self.content_warnings, list):
            self.content_warnings = list(self.content_warnings)
        self.content_warnings = [str(w).strip().lstrip("#").lower() for w in self.content_warnings if str(w).strip()]

        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

    @property
    def transcript(self) -> Optional[str]:
        return self.audio_transcript

    @property
    def has_alt_text(self) -> bool:
        return bool(self.alt_text and str(self.alt_text).strip())

    @property
    def has_audio_transcript(self) -> bool:
        return bool(self.audio_transcript and str(self.audio_transcript).strip())

    @property
    def content_warning_tags(self) -> List[str]:
        return self.content_warnings

    @property
    def cw_tags(self) -> List[str]:
        return self.content_warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "media_type": self.media_type,
            "alt_text": self.alt_text,
            "audio_transcript": self.audio_transcript,
            "transcript": self.audio_transcript,
            "captions_url": self.captions_url,
            "description": self.description,
            "discussion_id": self.discussion_id,
            "uploader_id": self.uploader_id,
            "content_warnings": self.content_warnings,
            "content_warning_tags": self.content_warnings,
            "cw_tags": self.content_warnings,
            "is_sensitive": self.is_sensitive,
            "has_alt_text": self.has_alt_text,
            "has_audio_transcript": self.has_audio_transcript,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

Media = MediaAttachment
MediaMetadata = MediaAttachment
MediaAccessibility = MediaAttachment


@dataclass
class ContentFilterPreferences:
    user_id: str
    mute_keywords: List[str] = field(default_factory=list)
    content_warning_tags: List[str] = field(default_factory=list)
    hide_sensitive_media: bool = False
    filter_level: str = "hide"  # "hide", "warn", "blur"
    filter_notifications: bool = False
    filter_direct_messages: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        for attr in ("mute_keywords", "content_warning_tags"):
            val = getattr(self, attr)
            if isinstance(val, str):
                try:
                    setattr(self, attr, json.loads(val))
                except Exception:
                    setattr(self, attr, [k.strip().lstrip("#").lower() for k in val.split(",") if k.strip()])
            elif val is None:
                setattr(self, attr, [])
            elif not isinstance(val, list):
                setattr(self, attr, list(val))
            setattr(self, attr, [str(k).strip().lstrip("#").lower() for k in getattr(self, attr) if str(k).strip()])

        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if isinstance(self.updated_at, str):
            try:
                self.updated_at = datetime.fromisoformat(self.updated_at)
            except Exception:
                pass

    @property
    def muted_keywords(self) -> List[str]:
        return self.mute_keywords

    @property
    def sensitive_tags(self) -> List[str]:
        return self.content_warning_tags

    @property
    def cw_tags(self) -> List[str]:
        return self.content_warning_tags

    def is_text_muted(self, text: str) -> bool:
        if not text or not self.mute_keywords:
            return False
        text_lower = text.lower()
        for kw in self.mute_keywords:
            if kw and kw in text_lower:
                return True
        return False

    def has_matching_warning(self, tags: List[str]) -> bool:
        if not tags or not self.content_warning_tags:
            return False
        normalized_tags = {str(t).lower().lstrip("#") for t in tags if str(t).strip()}
        for cw in self.content_warning_tags:
            cw_norm = cw.lower().lstrip("#")
            if cw_norm in normalized_tags or any(cw_norm in t for t in normalized_tags):
                return True
        return False

    def matches_filters(self, text: str = "", tags: Optional[List[str]] = None, content_warnings: Optional[List[str]] = None) -> bool:
        if self.is_text_muted(text):
            return True
        if self.has_matching_warning(tags or []):
            return True
        if self.has_matching_warning(content_warnings or []):
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "mute_keywords": self.mute_keywords,
            "muted_keywords": self.mute_keywords,
            "content_warning_tags": self.content_warning_tags,
            "sensitive_tags": self.content_warning_tags,
            "cw_tags": self.content_warning_tags,
            "hide_sensitive_media": self.hide_sensitive_media,
            "filter_level": self.filter_level,
            "filter_notifications": self.filter_notifications,
            "filter_direct_messages": self.filter_direct_messages,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else str(self.updated_at)
        }

UserContentFilter = ContentFilterPreferences
UserContentFilterPreferences = ContentFilterPreferences
ContentFilteringPreferences = ContentFilterPreferences


@dataclass
class UserAccessibilitySettings:
    user_id: str
    high_contrast: bool = False
    reduce_motion: bool = False
    screen_reader_optimized: bool = False
    font_size: str = "medium"  # "small", "medium", "large", "x-large"
    closed_captions_enabled: bool = False
    audio_transcripts_enabled: bool = True
    alt_text_required_on_post: bool = False
    autoplay_media: bool = False
    dyslexia_font: bool = False
    color_blind_mode: str = "none"  # "none", "protanopia", "deuteranopia", "tritanopia"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if isinstance(self.updated_at, str):
            try:
                self.updated_at = datetime.fromisoformat(self.updated_at)
            except Exception:
                pass

    @property
    def screen_reader_mode(self) -> bool:
        return self.screen_reader_optimized

    @property
    def high_contrast_mode(self) -> bool:
        return self.high_contrast

    @property
    def captions_enabled(self) -> bool:
        return self.closed_captions_enabled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "high_contrast": self.high_contrast,
            "high_contrast_mode": self.high_contrast,
            "reduce_motion": self.reduce_motion,
            "screen_reader_optimized": self.screen_reader_optimized,
            "screen_reader_mode": self.screen_reader_optimized,
            "font_size": self.font_size,
            "closed_captions_enabled": self.closed_captions_enabled,
            "captions_enabled": self.closed_captions_enabled,
            "audio_transcripts_enabled": self.audio_transcripts_enabled,
            "alt_text_required_on_post": self.alt_text_required_on_post,
            "autoplay_media": self.autoplay_media,
            "dyslexia_font": self.dyslexia_font,
            "color_blind_mode": self.color_blind_mode,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else str(self.updated_at)
        }

AccessibilitySettings = UserAccessibilitySettings
UserSettingsAccessibility = UserAccessibilitySettings


# --- Content Transformation Dossiers & Export Packaging Models ---

class DossierFormat:
    JSON = "json"
    MARKDOWN = "markdown"
    MD = "markdown"
    HTML = "html"
    TEXT = "text"
    TXT = "text"
    CSV = "csv"
    ZIP = "zip"
    TAR = "tar"

ExportFormat = DossierFormat

class DossierType:
    USER_ARCHIVE = "user_archive"
    USER_PROFILE = "user_profile"
    ACADEMIC_PORTFOLIO = "academic_portfolio"
    RESEARCH_DOSSIER = "research_dossier"
    COMMUNITY_DIGEST = "community_digest"
    DISCUSSION_THREAD = "discussion_thread"
    GDPR_PACKAGE = "gdpr_package"

ExportScope = DossierType

class TransformationStyle:
    STANDARD = "standard"
    COMPACT = "compact"
    EXECUTIVE = "executive"
    ACADEMIC = "academic"


@dataclass
class TransformationOptions:
    format: str = "markdown"
    dossier_type: str = "user_archive"
    style: str = "standard"
    anonymize_pii: bool = False
    redact_private_messages: bool = False
    include_replies: bool = True
    include_media_metadata: bool = True
    include_academic_data: bool = True
    include_communities: bool = True
    include_direct_messages: bool = True
    include_system_metadata: bool = True
    include_frontmatter: bool = True
    include_toc: bool = True
    filter_tags: List[str] = field(default_factory=list)
    since_date: Optional[str] = None
    until_date: Optional[str] = None

    def __post_init__(self):
        if self.format:
            self.format = self.format.lower().strip().lstrip(".")
            if self.format == "md":
                self.format = "markdown"
            elif self.format == "txt":
                self.format = "text"
        if self.dossier_type:
            self.dossier_type = self.dossier_type.lower().strip()
        if self.style:
            self.style = self.style.lower().strip()
        if isinstance(self.filter_tags, str):
            try:
                self.filter_tags = json.loads(self.filter_tags)
            except Exception:
                self.filter_tags = [t.strip() for t in self.filter_tags.split(",") if t.strip()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": self.format,
            "dossier_type": self.dossier_type,
            "style": self.style,
            "anonymize_pii": self.anonymize_pii,
            "redact_private_messages": self.redact_private_messages,
            "include_replies": self.include_replies,
            "include_media_metadata": self.include_media_metadata,
            "include_academic_data": self.include_academic_data,
            "include_communities": self.include_communities,
            "include_direct_messages": self.include_direct_messages,
            "include_system_metadata": self.include_system_metadata,
            "include_frontmatter": self.include_frontmatter,
            "include_toc": self.include_toc,
            "filter_tags": self.filter_tags,
            "since_date": self.since_date,
            "until_date": self.until_date
        }

DossierOptions = TransformationOptions
ExportPackagingOptions = TransformationOptions


@dataclass
class DossierSection:
    title: str
    section_type: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    item_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "section_type": self.section_type,
            "content": self.content,
            "metadata": self.metadata,
            "item_count": self.item_count
        }


@dataclass
class TransformationDossier:
    id: str
    title: str
    dossier_type: str
    format: str
    target_id: str
    target_type: str = "user"
    summary: str = ""
    sections: List[DossierSection] = field(default_factory=list)
    rendered_content: str = ""
    item_counts: Dict[str, int] = field(default_factory=dict)
    checksum: str = ""
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if not self.size_bytes and self.rendered_content:
            self.size_bytes = len(self.rendered_content.encode("utf-8"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "dossier_type": self.dossier_type,
            "format": self.format,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "summary": self.summary,
            "sections": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.sections],
            "rendered_content": self.rendered_content,
            "item_counts": self.item_counts,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "metadata": self.metadata
        }


@dataclass
class ExportPackageManifest:
    package_id: str
    user_id: Optional[str] = None
    format: str = "zip"
    file_list: List[Dict[str, Any]] = field(default_factory=list)
    total_files: int = 0
    total_bytes: int = 0
    checksum: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "user_id": self.user_id,
            "format": self.format,
            "file_list": self.file_list,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "metadata": self.metadata
        }


@dataclass
class ExportPackage:
    manifest: ExportPackageManifest
    archive_bytes: bytes = field(default=b"")
    archive_base64: Optional[str] = None
    filename: str = ""
    content_type: str = "application/zip"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict() if hasattr(self.manifest, "to_dict") else self.manifest,
            "filename": self.filename,
            "content_type": self.content_type,
            "archive_base64": self.archive_base64,
            "size_bytes": len(self.archive_bytes) if self.archive_bytes else 0
        }


# =========================================================================
# --- Weighted Value Endorsements & Domain Reputation Models ---
# =========================================================================

class EndorsementCategory:
    GENERAL = "general"
    ACADEMIC = "academic"
    RESEARCH = "academic"
    ACCURACY = "accuracy"
    RIGOR = "accuracy"
    CLARITY = "clarity"
    PEDAGOGICAL = "pedagogical"
    THOROUGHNESS = "thoroughness"
    INNOVATION = "innovation"
    BREAKTHROUGH = "innovation"
    CODE_QUALITY = "code_quality"


class ReputationBadge:
    NOVICE = "novice"
    CONTRIBUTOR = "contributor"
    SCHOLAR = "scholar"
    DOMAIN_EXPERT = "domain_expert"
    DISTINGUISHED_SCHOLAR = "distinguished_scholar"


@dataclass
class Endorsement:
    id: str
    target_type: str = "discussion"  # "discussion", "course_resource", "study_space", "study_group", "reply", "user"
    target_id: str = ""
    endorser_id: str = ""
    domain: str = "general"
    weight: float = 1.0
    value_category: str = "general"
    comment: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except Exception:
                pass
        if isinstance(self.metadata, str):
            try:
                self.metadata = json.loads(self.metadata)
            except Exception:
                self.metadata = {}
        elif self.metadata is None:
            self.metadata = {}
        if self.domain:
            self.domain = str(self.domain).strip().lower().lstrip("#")
        else:
            self.domain = "general"
        if self.weight is not None:
            self.weight = float(self.weight)
        else:
            self.weight = 1.0

    def __getitem__(self, key):
        return getattr(self, key)

    @property
    def user_id(self) -> str:
        return self.endorser_id

    @property
    def actor_id(self) -> str:
        return self.endorser_id

    @property
    def author_id(self) -> str:
        return self.endorser_id

    @property
    def score(self) -> float:
        return self.weight

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "endorser_id": self.endorser_id,
            "user_id": self.endorser_id,
            "actor_id": self.endorser_id,
            "domain": self.domain,
            "weight": self.weight,
            "score": self.weight,
            "value_category": self.value_category,
            "category": self.value_category,
            "comment": self.comment,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

ValueEndorsement = Endorsement
WeightedEndorsement = Endorsement


@dataclass
class DomainReputation:
    user_id: str
    domain: str = "general"
    score: float = 0.0
    endorsements_received_count: int = 0
    weighted_endorsements_received: float = 0.0
    endorsements_given_count: int = 0
    discussions_count: int = 0
    resources_count: int = 0
    verified_role: str = "member"
    badge: str = ReputationBadge.NOVICE
    updated_at: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.domain:
            self.domain = str(self.domain).strip().lower().lstrip("#")
        else:
            self.domain = "general"
        if isinstance(self.updated_at, str):
            try:
                self.updated_at = datetime.fromisoformat(self.updated_at)
            except Exception:
                pass
        self.score = float(self.score)
        self.weighted_endorsements_received = float(self.weighted_endorsements_received)
        if not self.badge or self.badge == "contributor":
            if self.score >= 100.0:
                self.badge = ReputationBadge.DISTINGUISHED_SCHOLAR
            elif self.score >= 50.0:
                self.badge = ReputationBadge.DOMAIN_EXPERT
            elif self.score >= 25.0:
                self.badge = ReputationBadge.SCHOLAR
            elif self.score >= 10.0:
                self.badge = ReputationBadge.CONTRIBUTOR
            else:
                self.badge = ReputationBadge.NOVICE

    def __getitem__(self, key):
        return getattr(self, key)

    @property
    def reputation_score(self) -> float:
        return self.score

    @property
    def topic(self) -> str:
        return self.domain

    @property
    def total_endorsements_received(self) -> int:
        return self.endorsements_received_count

    @property
    def total_endorsements_given(self) -> int:
        return self.endorsements_given_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "domain": self.domain,
            "topic": self.domain,
            "score": self.score,
            "reputation_score": self.score,
            "endorsements_received_count": self.endorsements_received_count,
            "total_endorsements_received": self.endorsements_received_count,
            "weighted_endorsements_received": self.weighted_endorsements_received,
            "endorsements_given_count": self.endorsements_given_count,
            "total_endorsements_given": self.endorsements_given_count,
            "discussions_count": self.discussions_count,
            "resources_count": self.resources_count,
            "verified_role": self.verified_role,
            "badge": self.badge,
            "details": self.details,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else str(self.updated_at)
        }

UserDomainReputation = DomainReputation
ReputationScore = DomainReputation
UserReputation = DomainReputation


@dataclass
class DomainLeaderboardEntry:
    user_id: str
    username: str
    domain: str
    score: float
    badge: str
    rank: int = 1
    endorsements_received: int = 0
    weighted_endorsements: float = 0.0
    contributions_count: int = 0
    verified_role: str = "member"

    def __getitem__(self, key):
        return getattr(self, key)

    @property
    def reputation_score(self) -> float:
        return self.score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "domain": self.domain,
            "score": self.score,
            "reputation_score": self.score,
            "rank": self.rank,
            "badge": self.badge,
            "endorsements_received": self.endorsements_received,
            "weighted_endorsements": self.weighted_endorsements,
            "contributions_count": self.contributions_count,
            "verified_role": self.verified_role
        }


@dataclass
class StudySpaceReputation:
    target_id: str
    target_type: str = "course"  # "course" or "study_group"
    name: str = ""
    domain: str = ""
    reputation_score: float = 0.0
    quality_score: float = 0.0
    activity_score: float = 0.0
    total_resources: int = 0
    total_resource_endorsements: int = 0
    total_weighted_endorsements: float = 0.0
    total_discussions: int = 0
    member_count: int = 0
    verified_member_count: int = 0
    top_contributors: List[Dict[str, Any]] = field(default_factory=list)

    def __getitem__(self, key):
        return getattr(self, key)

    @property
    def space_id(self) -> str:
        return self.target_id

    @property
    def total_endorsements(self) -> int:
        return self.total_resource_endorsements

    @property
    def weighted_endorsements(self) -> float:
        return self.total_weighted_endorsements

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "space_id": self.target_id,
            "target_type": self.target_type,
            "name": self.name,
            "title": self.name,
            "domain": self.domain,
            "reputation_score": self.reputation_score,
            "quality_score": self.quality_score,
            "activity_score": self.activity_score,
            "total_resources": self.total_resources,
            "total_resource_endorsements": self.total_resource_endorsements,
            "total_endorsements": self.total_resource_endorsements,
            "total_weighted_endorsements": self.total_weighted_endorsements,
            "weighted_endorsements": self.total_weighted_endorsements,
            "total_discussions": self.total_discussions,
            "member_count": self.member_count,
            "verified_member_count": self.verified_member_count,
            "top_contributors": self.top_contributors
        }

CourseReputation = StudySpaceReputation
StudyGroupReputation = StudySpaceReputation
