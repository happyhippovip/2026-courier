from typing import Dict, List, Optional, Any, Union
from .client import SocialPlatformClient


class UserSession:
    """
    Stateful workflow session bound to an active user ID.
    Provides ergonomic end-to-end interactions with the platform.
    """

    def __init__(
        self,
        arg1: Any = None,
        arg2: Any = None,
        *,
        client: Any = None,
        user_id: Any = None
    ):
        resolved_client = client
        resolved_user_id = user_id

        if arg1 is not None:
            if isinstance(arg1, SocialPlatformClient):
                resolved_client = arg1
            elif isinstance(arg1, str) or isinstance(arg1, (int, float)):
                resolved_user_id = str(arg1)
            else:
                resolved_client = arg1

        if arg2 is not None:
            if isinstance(arg2, SocialPlatformClient):
                resolved_client = arg2
            elif isinstance(arg2, str) or isinstance(arg2, (int, float)):
                resolved_user_id = str(arg2)
            else:
                if resolved_client is None:
                    resolved_client = arg2
                else:
                    resolved_user_id = str(arg2)

        self.client = resolved_client
        self.user_id = str(resolved_user_id) if resolved_user_id is not None else ""

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

    def get_dossier(
        self,
        format: str = "markdown",
        dossier_type: str = "user_archive",
        style: str = "standard",
        anonymize_pii: bool = False,
        redact_private_messages: bool = False
    ) -> Dict[str, Any]:
        """Generates a structured content transformation dossier for this session's user."""
        return self.client.get_user_dossier(
            self.user_id,
            format=format,
            dossier_type=dossier_type,
            style=style,
            anonymize_pii=anonymize_pii,
            redact_private_messages=redact_private_messages
        )

    def get_academic_portfolio(self, format: str = "markdown", **kwargs) -> Dict[str, Any]:
        """Generates academic portfolio dossier for this session's user."""
        return self.client.get_user_dossier(self.user_id, format=format, dossier_type="academic_portfolio", **kwargs)

    def get_research_dossier(self, format: str = "markdown", **kwargs) -> Dict[str, Any]:
        """Generates research and publications dossier for this session's user."""
        return self.client.get_user_dossier(self.user_id, format=format, dossier_type="research_dossier", **kwargs)

    def export_package(self, format: str = "zip", output_path: Optional[str] = None) -> Any:
        """Creates or downloads a complete multi-format export archive package."""
        if output_path:
            return self.client.download_export_package(self.user_id, output_path=output_path, format=format)
        return self.client.create_export_package(self.user_id, format=format)

    def get_discussion_dossier(self, discussion_id: str, format: str = "markdown", **kwargs) -> Dict[str, Any]:
        """Generates formatted discussion thread dossier."""
        return self.client.get_discussion_dossier(discussion_id, format=format, **kwargs)

    def get_community_dossier(self, community_id: str, format: str = "markdown", **kwargs) -> Dict[str, Any]:
        """Generates formatted community knowledge digest dossier."""
        return self.client.get_community_dossier(community_id, format=format, **kwargs)

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

    def endorse(
        self,
        discussion_id: str,
        weight: Optional[float] = None,
        domain: Optional[str] = None,
        value_category: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Endorses a discussion for substance/value with optional domain reputation weighting."""
        return self.client.endorse_discussion(
            discussion_id=discussion_id,
            user_id=self.user_id,
            weight=weight,
            domain=domain,
            value_category=value_category,
            comment=comment
        )

    def endorse_discussion(
        self,
        discussion_id: str,
        weight: Optional[float] = None,
        domain: Optional[str] = None,
        value_category: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Alias for endorse."""
        return self.endorse(
            discussion_id=discussion_id,
            weight=weight,
            domain=domain,
            value_category=value_category,
            comment=comment
        )

    def endorse_resource(
        self,
        resource_id: str,
        weight: Optional[float] = None,
        domain: Optional[str] = None,
        value_category: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Endorses an academic study resource with optional domain reputation weighting."""
        return self.client.endorse_resource(
            resource_id=resource_id,
            user_id=self.user_id,
            weight=weight,
            domain=domain,
            value_category=value_category,
            comment=comment
        )

    def feed(
        self,
        mode: str = "chronological",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        community_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        interests: Optional[List[str]] = None,
        domain: Optional[str] = None,
        include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieves personal feed."""
        return self.client.get_feed(
            user_id=self.user_id,
            mode=mode,
            community_id=community_id,
            channel_id=channel_id,
            interests=interests,
            domain=domain,
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

    def weighted_feed(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves feed ranked by weighted value endorsements and peer validation."""
        return self.client.get_weighted_feed(user_id=self.user_id, limit=limit, offset=offset)

    def domain_feed(self, domain: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves feed ranked by domain expertise and author reputation."""
        return self.client.get_domain_feed(user_id=self.user_id, domain=domain, limit=limit, offset=offset)

    def get_reputation(self, domain: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Gets active user's domain reputation score(s)."""
        return self.client.get_user_reputation(user_id=self.user_id, domain=domain)

    def get_domain_reputation(self, domain: str) -> Dict[str, Any]:
        """Gets active user's reputation in a specific domain."""
        return self.client.get_domain_reputation(user_id=self.user_id, domain=domain)

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

    def get_notification_preferences(self) -> Dict[str, Any]:
        """Gets user notification preferences."""
        return self.client.get_notification_preferences(self.user_id)

    def update_notification_preferences(self, **kwargs) -> Dict[str, Any]:
        """Updates user notification preferences."""
        return self.client.update_notification_preferences(self.user_id, **kwargs)

    def register_push_device(
        self,
        endpoint: str,
        p256dh: Optional[str] = None,
        auth: Optional[str] = None,
        platform: str = "web",
        device_token: Optional[str] = None,
        device_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Registers a push notification device for the active user session."""
        return self.client.register_push_subscription(
            user_id=self.user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            platform=platform,
            device_token=device_token,
            device_name=device_name
        )

    def register_push_subscription(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Alias for register_push_device."""
        return self.register_push_device(endpoint=endpoint, **kwargs)

    def unregister_push_device(self, subscription_id: str) -> Dict[str, Any]:
        """Unregisters a push notification device for the active user session."""
        return self.client.unregister_push_subscription(subscription_id, user_id=self.user_id)

    def unregister_push_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Alias for unregister_push_device."""
        return self.unregister_push_device(subscription_id)

    def get_push_subscriptions(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Lists active push subscriptions for the current user."""
        return self.client.get_push_subscriptions(self.user_id, active_only=active_only)

    def list_push_subscriptions(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Alias for get_push_subscriptions."""
        return self.get_push_subscriptions(active_only=active_only)

    def get_dispatched_notifications(self) -> List[Dict[str, Any]]:
        """Retrieves notification dispatch logs for current user."""
        return self.client.get_dispatched_notifications(user_id=self.user_id)

    def search(self, query: str, search_type: str = "all", **filters) -> Dict[str, Any]:
        """Runs search scoped to viewer context."""
        return self.client.search(query=query, search_type=search_type, viewer_id=self.user_id, **filters)
