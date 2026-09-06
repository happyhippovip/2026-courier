from typing import Dict, List, Optional, Any, Union
from .client import SocialPlatformClient


class UserSession:
    """
    Stateful workflow session bound to an active user ID.
    Provides ergonomic end-to-end interactions with the platform.
    """

    def __init__(self, client: SocialPlatformClient, user_id: str):
        self.client = client
        self.user_id = user_id

    # --------------------------------------------------------------------------
    # Profile & Identity
    # --------------------------------------------------------------------------

    def get_profile(self) -> Dict[str, Any]:
        """Gets the active user's profile."""
        return self.client.get_profile(self.user_id)

    def update_profile(self, **fields) -> Dict[str, Any]:
        """Updates the active user's profile."""
        return self.client.update_profile(self.user_id, **fields)

    def get_privacy_settings(self) -> Dict[str, Any]:
        """Gets active user's privacy settings."""
        return self.client.get_privacy_settings(self.user_id)

    def update_privacy(
        self,
        visibility: Optional[str] = None,
        dm_privacy: Optional[str] = None,
        is_publicly_discoverable: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Updates active user's privacy preferences."""
        return self.client.update_privacy(
            self.user_id,
            visibility=visibility,
            dm_privacy=dm_privacy,
            is_publicly_discoverable=is_publicly_discoverable,
            is_active=is_active
        )

    def export_data(self) -> Dict[str, Any]:
        """Exports all data associated with the active user."""
        return self.client.export_user_data(self.user_id)

    # --------------------------------------------------------------------------
    # Content & Feed
    # --------------------------------------------------------------------------

    def post(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        visibility: str = "public",
        content_warnings: Optional[List[str]] = None,
        alt_text: Optional[str] = None,
        community_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        course_id: Optional[str] = None,
        study_group_id: Optional[str] = None,
        media: Optional[List[Any]] = None,
        discussion_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publishes a new discussion / post from this user."""
        return self.client.create_discussion(
            author_id=self.user_id,
            content=content,
            discussion_id=discussion_id,
            tags=tags,
            visibility=visibility,
            content_warnings=content_warnings,
            alt_text=alt_text,
            community_id=community_id,
            channel_id=channel_id,
            course_id=course_id,
            study_group_id=study_group_id,
            media=media
        )

    def reply(
        self,
        parent_id: str,
        content: str,
        tags: Optional[List[str]] = None,
        content_warnings: Optional[List[str]] = None,
        reply_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Replies to a discussion."""
        return self.client.reply(
            parent_id=parent_id,
            author_id=self.user_id,
            content=content,
            tags=tags,
            content_warnings=content_warnings,
            reply_id=reply_id
        )

    def endorse(self, discussion_id: str) -> Dict[str, Any]:
        """Endorses a discussion for substance/value."""
        return self.client.endorse_discussion(discussion_id=discussion_id, user_id=self.user_id)

    def feed(
        self,
        mode: str = "chronological",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        community_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        interests: Optional[List[str]] = None,
        include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieves personal feed."""
        return self.client.get_feed(
            user_id=self.user_id,
            mode=mode,
            community_id=community_id,
            channel_id=channel_id,
            interests=interests,
            limit=limit,
            offset=offset,
            include_hidden=include_hidden
        )

    def following_feed(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves chronological feed of users followed by this user."""
        return self.client.get_following_feed(user_id=self.user_id, limit=limit, offset=offset)

    def interest_feed(self, interests: Optional[List[str]] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves feed based on matched topics and interests."""
        return self.client.get_interest_feed(user_id=self.user_id, interests=interests, limit=limit, offset=offset)

    def community_feed(self, community_id: str, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves feed for a specific community."""
        return self.client.get_community_feed(user_id=self.user_id, community_id=community_id, limit=limit, offset=offset)

    # --------------------------------------------------------------------------
    # Social Graph
    # --------------------------------------------------------------------------

    def follow(self, target_user_id: str) -> Dict[str, Any]:
        """Follows another user."""
        return self.client.follow(follower_id=self.user_id, followed_id=target_user_id)

    def unfollow(self, target_user_id: str) -> Dict[str, Any]:
        """Unfollows a user."""
        return self.client.unfollow(follower_id=self.user_id, followed_id=target_user_id)

    def get_following(self) -> List[Dict[str, Any]]:
        """Lists users this user is following."""
        return self.client.get_connections(self.user_id)

    def block(self, target_user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Blocks a user."""
        return self.client.block_user(blocker_id=self.user_id, blocked_id=target_user_id, reason=reason)

    def unblock(self, target_user_id: str) -> Dict[str, Any]:
        """Unblocks a user."""
        return self.client.unblock_user(blocker_id=self.user_id, blocked_id=target_user_id)

    def get_blocked(self) -> List[Dict[str, Any]]:
        """Lists blocked users."""
        return self.client.get_blocked_users(self.user_id)

    # --------------------------------------------------------------------------
    # Direct Messaging
    # --------------------------------------------------------------------------

    def send_message(self, recipient_id: str, content: str) -> Dict[str, Any]:
        """Sends a direct message to another user."""
        return self.client.send_dm(sender_id=self.user_id, recipient_id=recipient_id, content=content)

    def get_conversations(self) -> List[Dict[str, Any]]:
        """Lists active DM conversations."""
        return self.client.get_conversations(self.user_id)

    def get_thread(self, other_user_id: str) -> List[Dict[str, Any]]:
        """Gets message history with another user."""
        return self.client.get_messages(user1=self.user_id, user2=other_user_id)

    def get_unread_message_count(self) -> int:
        """Gets number of unread direct messages."""
        return self.client.get_unread_message_count(self.user_id)

    # --------------------------------------------------------------------------
    # Communities & Academic Spaces
    # --------------------------------------------------------------------------

    def create_community(
        self,
        name: str,
        description: str = "",
        is_private: bool = False,
        community_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a community with this user as creator/owner."""
        return self.client.create_community(
            name=name,
            creator_id=self.user_id,
            description=description,
            is_private=is_private,
            community_id=community_id
        )

    def join_community(self, community_id: str) -> Dict[str, Any]:
        """Joins a community."""
        return self.client.join_community(community_id=community_id, user_id=self.user_id)

    def leave_community(self, community_id: str) -> Dict[str, Any]:
        """Leaves a community."""
        return self.client.leave_community(community_id=community_id, user_id=self.user_id)

    def request_join_community(self, community_id: str, message: str = "") -> Dict[str, Any]:
        """Sends request to join private community."""
        return self.client.request_join_community(community_id=community_id, user_id=self.user_id, message=message)

    def enroll_in_course(self, course_id: str, role: str = "student", verified: bool = True) -> Dict[str, Any]:
        """Enrolls into a verified course."""
        return self.client.enroll_course(course_id=course_id, user_id=self.user_id, role=role, verified=verified)

    def get_my_courses(self) -> List[Dict[str, Any]]:
        """Lists enrolled courses."""
        return self.client.get_user_courses(self.user_id)

    def create_study_group(self, course_id: str, name: str, institution: str = "", description: str = "") -> Dict[str, Any]:
        """Creates a study group."""
        return self.client.create_study_group(
            course_id=course_id,
            name=name,
            creator_id=self.user_id,
            institution=institution,
            description=description
        )

    def join_study_group(self, study_group_id: str, role: str = "member") -> Dict[str, Any]:
        """Joins an academic study group."""
        return self.client.join_study_group(study_group_id=study_group_id, user_id=self.user_id, role=role)

    # --------------------------------------------------------------------------
    # Moderation & Appeals
    # --------------------------------------------------------------------------

    def report(self, target_type: str, target_id: str, reason: str, category: str = "general") -> Dict[str, Any]:
        """Reports violating content."""
        return self.client.report_content(
            reporter_id=self.user_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            category=category
        )

    def appeal(self, target_type: str, target_id: str, reason: str) -> Dict[str, Any]:
        """Submits moderation appeal."""
        return self.client.appeal(
            appellant_id=self.user_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason
        )

    # --------------------------------------------------------------------------
    # Notifications & Preferences
    # --------------------------------------------------------------------------

    def get_notifications(self, unread_only: bool = False) -> List[Dict[str, Any]]:
        """Gets user notifications."""
        return self.client.get_notifications(self.user_id, unread_only=unread_only)

    def get_unread_notification_count(self) -> int:
        """Gets unread notification count."""
        return self.client.get_unread_notification_count(self.user_id)

    def mark_all_notifications_read(self) -> Dict[str, Any]:
        """Marks all notifications read."""
        return self.client.mark_all_notifications_read(self.user_id)

    def search(self, query: str, search_type: str = "all", **filters) -> Dict[str, Any]:
        """Runs search scoped to viewer context."""
        return self.client.search(query=query, search_type=search_type, viewer_id=self.user_id, **filters)
