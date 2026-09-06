import json
import urllib.parse
import urllib.request
import urllib.error
import uuid
from typing import Dict, List, Optional, Any, Union


class ClientError(Exception):
    """Base exception for client errors."""
    pass


class APIError(ClientError):
    """Raised when the REST API returns a non-2xx status code."""
    def __init__(self, message: str, status_code: int = 500, data: Optional[Any] = None):
        super().__init__(f"API Error ({status_code}): {message}")
        self.message = message
        self.status_code = status_code
        self.data = data


class NotFoundError(APIError):
    """Raised when a requested resource is not found (HTTP 404)."""
    pass


class ValidationError(APIError):
    """Raised when request payload or parameters fail validation (HTTP 400)."""
    pass


class ForbiddenError(APIError):
    """Raised when an action is forbidden due to permissions or privacy (HTTP 403)."""
    pass


class AuthenticationError(APIError):
    """Raised when authentication fails (HTTP 401)."""
    pass


class SocialPlatformClient:
    """
    HTTP REST API Client for the Social Platform.
    Enables complete programmatic interaction with all server endpoints.
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 10.0, handler_caller=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.handler_caller = handler_caller

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Any:
        """Executes an HTTP request to the API."""
        if headers is None:
            headers = {}

        # Handle in-process caller for testing if provided
        if self.handler_caller:
            return self.handler_caller(method, path, params=params, body=json_data)

        # Build URL query params
        query_string = ""
        if params:
            clean_params = {}
            for k, v in params.items():
                if v is not None:
                    if isinstance(v, bool):
                        clean_params[k] = "true" if v else "false"
                    elif isinstance(v, (list, tuple)):
                        clean_params[k] = [str(item) for item in v]
                    else:
                        clean_params[k] = str(v)
            if clean_params:
                query_string = "?" + urllib.parse.urlencode(clean_params, doseq=True)

        url = f"{self.base_url}/{path.lstrip('/')}{query_string}"

        data_bytes = None
        if json_data is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(json_data).encode("utf-8")

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method.upper())

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.status
                resp_data = resp.read().decode("utf-8")
                if resp_data:
                    try:
                        return json.loads(resp_data)
                    except json.JSONDecodeError:
                        return resp_data
                return None
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            error_data = None
            err_msg = str(e.reason)
            try:
                error_data = json.loads(err_body)
                if isinstance(error_data, dict) and "error" in error_data:
                    err_msg = error_data["error"]
            except Exception:
                err_msg = err_body or str(e.reason)

            if e.code == 404:
                raise NotFoundError(err_msg, status_code=404, data=error_data) from e
            elif e.code == 400:
                raise ValidationError(err_msg, status_code=400, data=error_data) from e
            elif e.code == 403:
                raise ForbiddenError(err_msg, status_code=403, data=error_data) from e
            elif e.code == 401:
                raise AuthenticationError(err_msg, status_code=401, data=error_data) from e
            else:
                raise APIError(err_msg, status_code=e.code, data=error_data) from e
        except urllib.error.URLError as e:
            raise ClientError(f"Failed to connect to server at {url}: {e.reason}") from e

    # --------------------------------------------------------------------------
    # User & Profile Operations
    # --------------------------------------------------------------------------

    def create_user(
        self,
        username: str,
        user_id: Optional[str] = None,
        bio: str = "",
        school: str = "",
        university: str = "",
        class_year: str = "",
        interests: Optional[List[str]] = None,
        is_publicly_discoverable: bool = False,
        visibility: str = "public",
        dm_privacy: str = "everyone"
    ) -> Dict[str, Any]:
        """Registers a new user on the platform."""
        payload = {
            "id": user_id or str(uuid.uuid4()),
            "username": username,
            "bio": bio,
            "school": school,
            "university": university,
            "class_year": class_year,
            "interests": interests or [],
            "is_publicly_discoverable": is_publicly_discoverable,
            "visibility": visibility,
            "dm_privacy": dm_privacy
        }
        return self._request("POST", "/users", json_data=payload)

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Retrieves user details by user ID."""
        return self._request("GET", f"/users/{user_id}")

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        """Retrieves a user profile."""
        return self._request("GET", f"/users/{user_id}/profile")

    def update_profile(self, user_id: str, **fields) -> Dict[str, Any]:
        """Updates user profile information."""
        return self._request("PUT", f"/users/{user_id}", json_data=fields)

    def search_users(
        self,
        query: str = "",
        school: Optional[str] = None,
        university: Optional[str] = None,
        class_year: Optional[str] = None,
        interest: Optional[str] = None,
        interests: Optional[List[str]] = None,
        public_only: bool = False,
        viewer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches for users with filters."""
        params = {
            "q": query,
            "school": school,
            "university": university,
            "class_year": class_year,
            "interest": interest,
            "interests": interests,
            "public_only": public_only,
            "viewer_id": viewer_id
        }
        return self._request("GET", "/users", params=params)

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Exports full user data bundle for portability."""
        return self._request("GET", f"/users/{user_id}/export")

    def get_user_dossier(
        self,
        user_id: str,
        format: str = "markdown",
        dossier_type: str = "user_archive",
        style: str = "standard",
        anonymize_pii: bool = False,
        redact_private_messages: bool = False
    ) -> Dict[str, Any]:
        """Generates structured content transformation dossier for a user."""
        params = {
            "format": format,
            "type": dossier_type,
            "style": style,
            "anonymize": anonymize_pii,
            "redact_dms": redact_private_messages
        }
        return self._request("GET", f"/users/{user_id}/dossier", params=params)

    def create_export_package(
        self,
        user_id: str,
        format: str = "zip"
    ) -> Dict[str, Any]:
        """Creates complete multi-dossier export package archive."""
        params = {"format": format}
        return self._request("GET", f"/users/{user_id}/export/package", params=params)

    def download_export_package(
        self,
        user_id: str,
        output_path: Optional[str] = None,
        format: str = "zip"
    ) -> str:
        """Downloads export package archive and writes bytes to local path."""
        import base64
        pkg = self.create_export_package(user_id, format=format)
        target_path = output_path or pkg.get("filename") or f"export_{user_id}.{format}"
        b64_data = pkg.get("archive_base64", "")
        if b64_data:
            data_bytes = base64.b64decode(b64_data)
            with open(target_path, "wb") as f:
                f.write(data_bytes)
        return target_path

    def get_discussion_dossier(
        self,
        discussion_id: str,
        format: str = "markdown",
        style: str = "standard",
        anonymize_pii: bool = False
    ) -> Dict[str, Any]:
        """Generates formatted discussion thread dossier."""
        params = {"format": format, "style": style, "anonymize": anonymize_pii}
        return self._request("GET", f"/discussions/{discussion_id}/dossier", params=params)

    def get_community_dossier(
        self,
        community_id: str,
        format: str = "markdown",
        style: str = "standard",
        anonymize_pii: bool = False
    ) -> Dict[str, Any]:
        """Generates formatted community knowledge digest dossier."""
        params = {"format": format, "style": style, "anonymize": anonymize_pii}
        return self._request("GET", f"/communities/{community_id}/dossier", params=params)

    def transform_content(
        self,
        content: str,
        target_format: str = "markdown",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Transforms arbitrary content between formats with verification."""
        body = {"content": content, "target_format": target_format, "options": options or {}}
        return self._request("POST", "/content/transform", json_data=body)

    def get_export_formats(self) -> Dict[str, Any]:
        """Gets supported dossier and export package formats."""
        return self._request("GET", "/export/formats")

    def get_privacy_settings(self, user_id: str) -> Dict[str, Any]:
        """Gets user privacy controls."""
        return self._request("GET", f"/users/{user_id}/privacy")

    def update_privacy(
        self,
        user_id: str,
        visibility: Optional[str] = None,
        dm_privacy: Optional[str] = None,
        is_publicly_discoverable: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Updates user privacy and discoverability settings."""
        payload = {}
        if visibility is not None:
            payload["visibility"] = visibility
        if dm_privacy is not None:
            payload["dm_privacy"] = dm_privacy
        if is_publicly_discoverable is not None:
            payload["is_publicly_discoverable"] = is_publicly_discoverable
        if is_active is not None:
            payload["is_active"] = is_active
        return self._request("PUT", f"/users/{user_id}/privacy", json_data=payload)

    def deactivate_account(self, user_id: str) -> Dict[str, Any]:
        """Deactivates a user account."""
        return self._request("POST", f"/users/{user_id}/deactivate")

    def reactivate_account(self, user_id: str) -> Dict[str, Any]:
        """Reactivates a deactivated user account."""
        return self._request("POST", f"/users/{user_id}/reactivate")

    def get_user_discussions(self, user_id: str, viewer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves discussions authored by a user."""
        params = {"viewer_id": viewer_id} if viewer_id else None
        return self._request("GET", f"/users/{user_id}/discussions", params=params)

    def get_user_replies(self, user_id: str, viewer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves replies authored by a user."""
        params = {"viewer_id": viewer_id} if viewer_id else None
        return self._request("GET", f"/users/{user_id}/replies", params=params)

    # --------------------------------------------------------------------------
    # Connections & Social Graph
    # --------------------------------------------------------------------------

    def follow(self, follower_id: str, followed_id: str) -> Dict[str, Any]:
        """Creates a follow relationship between users."""
        payload = {"follower_id": follower_id, "followed_id": followed_id}
        return self._request("POST", "/connections", json_data=payload)

    def unfollow(self, follower_id: str, followed_id: str) -> Dict[str, Any]:
        """Removes a follow relationship between users."""
        return self._request("DELETE", f"/connections/{follower_id}/{followed_id}")

    def get_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """Gets all following connections for a user."""
        return self._request("GET", f"/users/{user_id}/connections")

    def block_user(self, blocker_id: str, blocked_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Blocks another user."""
        payload = {"blocker_id": blocker_id, "blocked_id": blocked_id, "reason": reason}
        return self._request("POST", "/blocks", json_data=payload)

    def unblock_user(self, blocker_id: str, blocked_id: str) -> Dict[str, Any]:
        """Unblocks a previously blocked user."""
        return self._request("DELETE", f"/blocks/{blocker_id}/{blocked_id}")

    def get_blocked_users(self, user_id: str) -> List[Dict[str, Any]]:
        """Lists users blocked by the given user."""
        return self._request("GET", f"/users/{user_id}/blocks")

    def is_blocked(self, blocker_id: str, blocked_id: str) -> bool:
        """Checks if a user is blocked."""
        resp = self._request("GET", f"/users/{blocker_id}/blocks/{blocked_id}")
        return bool(resp.get("is_blocked", False))

    def can_dm(self, sender_id: str, recipient_id: str) -> bool:
        """Checks if sender is permitted to direct message recipient."""
        resp = self._request("GET", f"/users/{sender_id}/can_message/{recipient_id}")
        return bool(resp.get("can_message", False))

    def can_view_profile(self, viewer_id: str, target_id: str) -> bool:
        """Checks if viewer is permitted to view target profile."""
        resp = self._request("GET", f"/users/{viewer_id}/can_view/{target_id}")
        return bool(resp.get("can_view", False))

    # --------------------------------------------------------------------------
    # Discussions & Feeds
    # --------------------------------------------------------------------------

    def create_discussion(
        self,
        author_id: str,
        content: str,
        discussion_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        visibility: str = "public",
        content_warnings: Optional[List[str]] = None,
        alt_text: Optional[str] = None,
        community_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        course_id: Optional[str] = None,
        study_group_id: Optional[str] = None,
        media: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """Publishes a new discussion / post."""
        payload = {
            "id": discussion_id or str(uuid.uuid4()),
            "author_id": author_id,
            "content": content,
            "tags": tags or [],
            "visibility": visibility,
            "content_warnings": content_warnings or [],
            "alt_text": alt_text,
            "community_id": community_id,
            "channel_id": channel_id,
            "course_id": course_id,
            "study_group_id": study_group_id,
            "media": media or []
        }
        return self._request("POST", "/discussions", json_data=payload)

    def get_discussion(self, discussion_id: str) -> Dict[str, Any]:
        """Retrieves a single discussion by ID."""
        return self._request("GET", f"/discussions/{discussion_id}")

    def get_all_discussions(self) -> List[Dict[str, Any]]:
        """Retrieves all public discussions."""
        return self._request("GET", "/discussions")

    def endorse_discussion(
        self,
        discussion_id: str,
        user_id: str,
        weight: Optional[float] = None,
        domain: Optional[str] = None,
        value_category: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Endorses a discussion with optional domain reputation weighting and category metadata."""
        payload = {
            "user_id": user_id,
            "weight": weight,
            "domain": domain,
            "value_category": value_category,
            "comment": comment
        }
        return self._request("POST", f"/discussions/{discussion_id}/endorse", json_data=payload)

    def get_discussion_endorsements(self, discussion_id: str) -> List[Dict[str, Any]]:
        """Gets all weighted endorsements for a discussion."""
        return self._request("GET", f"/discussions/{discussion_id}/endorsements")

    def reply(
        self,
        parent_id: str,
        author_id: str,
        content: str,
        reply_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        content_warnings: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Replies to an existing discussion."""
        payload = {
            "id": reply_id or str(uuid.uuid4()),
            "parent_id": parent_id,
            "author_id": author_id,
            "content": content,
            "tags": tags or [],
            "content_warnings": content_warnings or []
        }
        return self._request("POST", f"/discussions/{parent_id}/replies", json_data=payload)

    def get_replies(self, discussion_id: str) -> List[Dict[str, Any]]:
        """Gets all replies for a discussion."""
        return self._request("GET", f"/discussions/{discussion_id}/replies")

    def get_feed(
        self,
        user_id: str,
        mode: str = "chronological",
        community_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        interests: Optional[List[str]] = None,
        domain: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieves personalized feed for a user."""
        params = {
            "mode": mode,
            "community_id": community_id,
            "channel_id": channel_id,
            "interests": interests,
            "domain": domain,
            "limit": limit,
            "offset": offset,
            "include_hidden": include_hidden
        }
        return self._request("GET", f"/users/{user_id}/feed", params=params)

    def get_following_feed(self, user_id: str, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gets chronological feed of followed connections."""
        return self.get_feed(user_id=user_id, mode="following", limit=limit, offset=offset)

    def get_interest_feed(self, user_id: str, interests: Optional[List[str]] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gets feed tailored to user interests."""
        return self.get_feed(user_id=user_id, mode="interest_matched", interests=interests, limit=limit, offset=offset)

    def get_community_feed(self, user_id: str, community_id: str, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gets feed scoped to a community."""
        return self.get_feed(user_id=user_id, mode="community_scoped", community_id=community_id, limit=limit, offset=offset)

    def get_weighted_feed(self, user_id: str, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gets feed ranked by weighted value endorsements and peer validation."""
        return self.get_feed(user_id=user_id, mode="weighted_value", limit=limit, offset=offset)

    def get_domain_feed(self, user_id: str, domain: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gets feed ranked by domain expertise and author reputation."""
        return self.get_feed(user_id=user_id, mode="domain_reputation", domain=domain, limit=limit, offset=offset)

    # --------------------------------------------------------------------------
    # Communities & Channels
    # --------------------------------------------------------------------------

    def create_community(
        self,
        name: str,
        creator_id: str,
        description: str = "",
        is_private: bool = False,
        community_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new community space."""
        payload = {
            "id": community_id or str(uuid.uuid4()),
            "name": name,
            "creator_id": creator_id,
            "description": description,
            "is_private": is_private
        }
        return self._request("POST", "/communities", json_data=payload)

    def get_community(self, community_id: str) -> Dict[str, Any]:
        """Gets community metadata."""
        return self._request("GET", f"/communities/{community_id}")

    def get_all_communities(self) -> List[Dict[str, Any]]:
        """Lists all communities."""
        return self._request("GET", "/communities")

    def join_community(self, community_id: str, user_id: str) -> Dict[str, Any]:
        """Joins a public community."""
        return self._request("POST", f"/communities/{community_id}/join", json_data={"user_id": user_id})

    def leave_community(self, community_id: str, user_id: str) -> Dict[str, Any]:
        """Leaves a community."""
        return self._request("POST", f"/communities/{community_id}/leave", json_data={"user_id": user_id})

    def get_community_members(self, community_id: str, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists members of a community."""
        params = {"role": role} if role else None
        return self._request("GET", f"/communities/{community_id}/members", params=params)

    def request_join_community(self, community_id: str, user_id: str, message: str = "") -> Dict[str, Any]:
        """Requests to join a private community."""
        payload = {"user_id": user_id, "message": message}
        return self._request("POST", f"/communities/{community_id}/join_requests", json_data=payload)

    def get_community_join_requests(self, community_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists pending or reviewed join requests for a community."""
        params = {"status": status} if status else None
        return self._request("GET", f"/communities/{community_id}/join_requests", params=params)

    def get_user_join_requests(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists join requests created by a user."""
        params = {"status": status} if status else None
        return self._request("GET", f"/users/{user_id}/join_requests", params=params)

    def review_join_request(self, request_id: str, admin_id: str, action: str = "approve", message: str = "") -> Dict[str, Any]:
        """Approves or rejects a community join request."""
        payload = {"admin_id": admin_id, "action": action, "message": message}
        return self._request("POST", f"/join_requests/{request_id}/review", json_data=payload)

    def create_channel(
        self,
        community_id: str,
        name: str,
        description: str = "",
        channel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a channel inside a community."""
        payload = {
            "id": channel_id or str(uuid.uuid4()),
            "community_id": community_id,
            "name": name,
            "description": description
        }
        return self._request("POST", f"/communities/{community_id}/channels", json_data=payload)

    def get_channels(self, community_id: str) -> List[Dict[str, Any]]:
        """Lists channels in a community."""
        return self._request("GET", f"/communities/{community_id}/channels")

    def get_channel(self, channel_id: str) -> Dict[str, Any]:
        """Gets channel details."""
        return self._request("GET", f"/channels/{channel_id}")

    def get_channel_discussions(self, channel_id: str) -> List[Dict[str, Any]]:
        """Lists discussions within a channel."""
        return self._request("GET", f"/channels/{channel_id}/discussions")

    def create_community_invite(
        self,
        community_id: str,
        inviter_id: str,
        invitee_id: Optional[str] = None,
        max_uses: int = 1,
        expires_in_days: int = 7
    ) -> Dict[str, Any]:
        """Creates an invite link / token for a community."""
        payload = {
            "inviter_id": inviter_id,
            "invitee_id": invitee_id,
            "max_uses": max_uses,
            "expires_in_days": expires_in_days
        }
        return self._request("POST", f"/communities/{community_id}/invites", json_data=payload)

    # --------------------------------------------------------------------------
    # Academic Spaces & Courses
    # --------------------------------------------------------------------------

    def create_course(
        self,
        code: str,
        title: str,
        institution: str,
        term: str = "",
        instructor: str = "",
        description: str = "",
        course_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a verified course academic space."""
        payload = {
            "id": course_id or str(uuid.uuid4()),
            "code": code,
            "title": title,
            "institution": institution,
            "term": term,
            "instructor": instructor,
            "description": description
        }
        return self._request("POST", "/courses", json_data=payload)

    def get_course(self, course_id_or_code: str) -> Dict[str, Any]:
        """Gets course details."""
        return self._request("GET", f"/courses/{course_id_or_code}")

    def get_courses(
        self,
        institution: Optional[str] = None,
        term: Optional[str] = None,
        query: Optional[str] = None,
        code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists courses with optional institution/term filters."""
        params = {"institution": institution, "term": term, "query": query, "code": code}
        return self._request("GET", "/courses", params=params)

    def enroll_course(self, course_id: str, user_id: str, role: str = "student", verified: bool = True) -> Dict[str, Any]:
        """Enrolls a student into a course."""
        payload = {"user_id": user_id, "role": role, "is_verified": verified}
        return self._request("POST", f"/courses/{course_id}/enroll", json_data=payload)

    def get_course_enrollments(self, course_id: str, verified_only: bool = False, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Gets enrollments for a course."""
        params = {"verified_only": verified_only, "role": role}
        return self._request("GET", f"/courses/{course_id}/enrollments", params=params)

    def get_user_courses(self, user_id: str) -> List[Dict[str, Any]]:
        """Gets all courses enrolled by a user."""
        return self._request("GET", f"/users/{user_id}/courses")

    def get_verified_classmates(self, course_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists verified classmates in a course."""
        params = {"user_id": user_id} if user_id else None
        return self._request("GET", f"/courses/{course_id}/classmates", params=params)

    def add_course_resource(
        self,
        course_id: str,
        uploader_id: str,
        title: str,
        url: str,
        resource_type: str = "note",
        tag: Optional[str] = None,
        resource_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Uploads or links an academic study resource to a course."""
        payload = {
            "id": resource_id or str(uuid.uuid4()),
            "course_id": course_id,
            "uploader_id": uploader_id,
            "title": title,
            "url": url,
            "resource_type": resource_type,
            "tag": tag
        }
        return self._request("POST", f"/courses/{course_id}/resources", json_data=payload)

    def get_course_resources(self, course_id: str, resource_type: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists study resources for a course."""
        params = {"type": resource_type, "tag": tag}
        return self._request("GET", f"/courses/{course_id}/resources", params=params)

    def create_study_group(
        self,
        course_id: str,
        name: str,
        creator_id: str,
        institution: str = "",
        description: str = "",
        group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates an academic study group."""
        payload = {
            "id": group_id or str(uuid.uuid4()),
            "course_id": course_id,
            "name": name,
            "creator_id": creator_id,
            "institution": institution,
            "description": description
        }
        return self._request("POST", "/study_groups", json_data=payload)

    def get_study_groups(
        self,
        course_id: Optional[str] = None,
        institution: Optional[str] = None,
        user_id: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists study groups matching filters."""
        params = {"course_id": course_id, "institution": institution, "user_id": user_id, "query": query}
        return self._request("GET", "/study_groups", params=params)

    def join_study_group(self, study_group_id: str, user_id: str, role: str = "member") -> Dict[str, Any]:
        """Joins an academic study group."""
        payload = {"user_id": user_id, "role": role}
        return self._request("POST", f"/study_groups/{study_group_id}/join", json_data=payload)

    def get_study_group_members(self, study_group_id: str) -> List[Dict[str, Any]]:
        """Lists members of a study group."""
        return self._request("GET", f"/study_groups/{study_group_id}/members")

    def endorse_resource(
        self,
        resource_id: str,
        user_id: str,
        weight: Optional[float] = None,
        domain: Optional[str] = None,
        value_category: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Endorses an academic study resource with optional domain reputation weighting."""
        payload = {
            "user_id": user_id,
            "weight": weight,
            "domain": domain,
            "value_category": value_category,
            "comment": comment
        }
        return self._request("POST", f"/resources/{resource_id}/endorse", json_data=payload)

    def get_resource_endorsements(self, resource_id: str) -> List[Dict[str, Any]]:
        """Gets all weighted endorsements for a resource."""
        return self._request("GET", f"/resources/{resource_id}/endorsements")

    def get_course_reputation(self, course_id: str) -> Dict[str, Any]:
        """Gets aggregated domain reputation and endorsement metrics for a course."""
        return self._request("GET", f"/courses/{course_id}/reputation")

    def get_study_group_reputation(self, study_group_id: str) -> Dict[str, Any]:
        """Gets aggregated domain reputation and endorsement metrics for a study group."""
        return self._request("GET", f"/study_groups/{study_group_id}/reputation")

    # --------------------------------------------------------------------------
    # Direct Messages & Conversations
    # --------------------------------------------------------------------------

    def send_dm(self, sender_id: str, recipient_id: str, content: str, message_id: Optional[str] = None) -> Dict[str, Any]:
        """Sends a private direct message."""
        payload = {
            "id": message_id or str(uuid.uuid4()),
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "content": content
        }
        return self._request("POST", "/dms", json_data=payload)

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Lists all DM conversations for a user."""
        return self._request("GET", f"/users/{user_id}/conversations")

    def get_messages(self, user1: str, user2: str) -> List[Dict[str, Any]]:
        """Gets direct message thread between two users."""
        return self._request("GET", f"/users/{user1}/conversations/{user2}")

    def get_unread_message_count(self, user_id: str) -> int:
        """Gets unread message count."""
        resp = self._request("GET", f"/users/{user_id}/messages/count")
        return int(resp.get("unread_count", 0))

    def mark_message_read(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """Marks a direct message as read."""
        return self._request("POST", f"/dms/{message_id}/read", json_data={"user_id": user_id})

    # --------------------------------------------------------------------------
    # Moderation, Reports & Appeals
    # --------------------------------------------------------------------------

    def report_content(
        self,
        reporter_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        category: str = "general",
        report_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submits a moderation report for inappropriate content."""
        payload = {
            "id": report_id or str(uuid.uuid4()),
            "reporter_id": reporter_id,
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason,
            "category": category
        }
        return self._request("POST", "/reports", json_data=payload)

    def get_reports(self, status: Optional[str] = None, target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists moderation reports."""
        params = {"status": status, "target_type": target_type}
        return self._request("GET", "/reports", params=params)

    def get_report(self, report_id: str) -> Dict[str, Any]:
        """Gets report details."""
        return self._request("GET", f"/reports/{report_id}")

    def resolve_report(
        self,
        report_id: str,
        admin_id: str,
        action: str = "hide",
        reason: str = ""
    ) -> Dict[str, Any]:
        """Resolves a moderation report with a designated action."""
        payload = {"admin_id": admin_id, "action": action, "reason": reason}
        return self._request("POST", f"/reports/{report_id}/resolve", json_data=payload)

    def appeal(
        self,
        appellant_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        appeal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submits an appeal against a moderation decision."""
        payload = {
            "id": appeal_id or str(uuid.uuid4()),
            "appellant_id": appellant_id,
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason
        }
        return self._request("POST", "/appeals", json_data=payload)

    def get_appeals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists moderation appeals."""
        params = {"status": status} if status else None
        return self._request("GET", "/appeals", params=params)

    def get_appeal(self, appeal_id: str) -> Dict[str, Any]:
        """Gets appeal details."""
        return self._request("GET", f"/appeals/{appeal_id}")

    def resolve_appeal(
        self,
        appeal_id: str,
        admin_id: str,
        action: str = "approve",
        note: str = ""
    ) -> Dict[str, Any]:
        """Reviews and resolves a moderation appeal."""
        payload = {"admin_id": admin_id, "action": action, "note": note}
        return self._request("POST", f"/appeals/{appeal_id}/resolve", json_data=payload)

    # --------------------------------------------------------------------------
    # Notifications, Preferences & Push Subscriptions
    # --------------------------------------------------------------------------

    def get_notifications(self, user_id: str, unread_only: bool = False) -> List[Dict[str, Any]]:
        """Gets notifications for a user."""
        params = {"unread_only": unread_only}
        return self._request("GET", f"/users/{user_id}/notifications", params=params)

    def get_unread_notification_count(self, user_id: str) -> int:
        """Gets the number of unread notifications for a user."""
        resp = self._request("GET", f"/users/{user_id}/notifications/count")
        return int(resp.get("unread_count", 0))

    def mark_notification_read(self, notification_id: str) -> Dict[str, Any]:
        """Marks a notification as read."""
        return self._request("POST", f"/notifications/{notification_id}/read")

    def mark_all_notifications_read(self, user_id: str) -> Dict[str, Any]:
        """Marks all notifications as read for a user."""
        return self._request("POST", f"/users/{user_id}/notifications/read_all")

    def get_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        """Gets user notification preferences."""
        return self._request("GET", f"/users/{user_id}/notification_preferences")

    def update_notification_preferences(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Updates user notification preferences."""
        return self._request("POST", f"/users/{user_id}/notification_preferences", json_data=kwargs)

    def register_push_subscription(
        self,
        user_id: str,
        endpoint: str,
        p256dh: Optional[str] = None,
        auth: Optional[str] = None,
        platform: str = "web",
        device_token: Optional[str] = None,
        device_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Registers a push notification device subscription."""
        payload = {
            "user_id": user_id,
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "platform": platform,
            "device_token": device_token,
            "device_name": device_name
        }
        return self._request("POST", f"/users/{user_id}/push_subscriptions", json_data=payload)

    def register_push_device(self, user_id: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Alias for register_push_subscription."""
        return self.register_push_subscription(user_id=user_id, endpoint=endpoint, **kwargs)

    def unregister_push_subscription(self, subscription_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Unregisters/deletes a push subscription."""
        if user_id:
            return self._request("DELETE", f"/users/{user_id}/push_subscriptions/{subscription_id}")
        return self._request("DELETE", f"/push_subscriptions/{subscription_id}")

    def unregister_push_device(self, subscription_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Alias for unregister_push_subscription."""
        return self.unregister_push_subscription(subscription_id, user_id=user_id)

    def get_push_subscriptions(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Lists push device subscriptions for a user."""
        params = {"active_only": active_only}
        return self._request("GET", f"/users/{user_id}/push_subscriptions", params=params)

    def get_push_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Gets a push subscription by ID."""
        return self._request("GET", f"/push_subscriptions/{subscription_id}")

    def dispatch_notification(
        self,
        user_id: str,
        type: str,
        actor_id: str,
        target_id: str,
        content: str = "",
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        weight: float = 0.0
    ) -> Dict[str, Any]:
        """Dispatches an event notification honoring preferences and push delivery."""
        payload = {
            "user_id": user_id,
            "type": type,
            "actor_id": actor_id,
            "target_id": target_id,
            "content": content,
            "title": title,
            "metadata": metadata or {},
            "weight": weight
        }
        return self._request("POST", f"/users/{user_id}/notifications/dispatch", json_data=payload)

    def get_dispatched_notifications(self, user_id: Optional[str] = None, notification_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves push notification dispatch delivery logs."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        if notification_id:
            params["notification_id"] = notification_id
        if user_id:
            return self._request("GET", f"/users/{user_id}/notifications/dispatches", params=params)
        return self._request("GET", "/notifications/dispatches", params=params)

    # --------------------------------------------------------------------------
    # Discovery & Search
    # --------------------------------------------------------------------------

    def search(
        self,
        query: str,
        search_type: str = "all",
        school: Optional[str] = None,
        university: Optional[str] = None,
        class_year: Optional[str] = None,
        interest: Optional[str] = None,
        viewer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Unified discovery search across discussions, communities, courses, groups, and users."""
        params = {
            "q": query,
            "type": search_type,
            "school": school,
            "university": university,
            "class_year": class_year,
            "interest": interest,
            "viewer_id": viewer_id
        }
        return self._request("GET", "/search", params=params)

    def search_discussions(self, query: str, viewer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches specifically for discussions matching query."""
        params = {"q": query, "viewer_id": viewer_id}
        return self._request("GET", "/search/discussions", params=params)

    def search_communities(self, query: str, viewer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches specifically for communities matching query."""
        params = {"q": query, "viewer_id": viewer_id}
        return self._request("GET", "/search/communities", params=params)

    def search_courses(self, query: str, institution: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches courses."""
        params = {"q": query, "school": institution}
        return self._request("GET", "/search/courses", params=params)

    def search_study_groups(self, query: str, institution: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches study groups."""
        params = {"q": query, "school": institution}
        return self._request("GET", "/search/study_groups", params=params)

    # --------------------------------------------------------------------------
    # Accessibility & Content Filters
    # --------------------------------------------------------------------------

    def get_accessibility_settings(self, user_id: str) -> Dict[str, Any]:
        """Gets user accessibility settings."""
        return self._request("GET", f"/users/{user_id}/accessibility")

    def update_accessibility_settings(self, user_id: str, **settings) -> Dict[str, Any]:
        """Updates user accessibility settings."""
        return self._request("PUT", f"/users/{user_id}/accessibility", json_data=settings)

    def get_content_filters(self, user_id: str) -> Dict[str, Any]:
        """Gets content filter preferences for user."""
        return self._request("GET", f"/users/{user_id}/content_filtering")

    def update_content_filters(self, user_id: str, **filters) -> Dict[str, Any]:
        """Updates content filter preferences."""
        return self._request("PUT", f"/users/{user_id}/content_filtering", json_data=filters)

    def add_mute_keyword(self, user_id: str, keyword: str) -> Dict[str, Any]:
        """Adds a keyword to user muted keyword list."""
        return self._request("POST", f"/users/{user_id}/mute_keywords", json_data={"keyword": keyword})

    def remove_mute_keyword(self, user_id: str, keyword: str) -> Dict[str, Any]:
        """Removes a keyword from user muted keyword list."""
        return self._request("DELETE", f"/users/{user_id}/mute_keywords/{urllib.parse.quote(keyword)}")

    # --------------------------------------------------------------------------
    # Reputation & Endorsements
    # --------------------------------------------------------------------------

    def get_user_reputation(self, user_id: str, domain: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Gets user domain reputation score(s)."""
        if domain:
            return self._request("GET", f"/users/{user_id}/reputation/{domain}")
        return self._request("GET", f"/users/{user_id}/reputation")

    def get_domain_reputation(self, user_id: str, domain: str) -> Dict[str, Any]:
        """Gets user domain reputation for a specific domain."""
        return self._request("GET", f"/users/{user_id}/reputation/{domain}")

    def get_domain_leaderboard(self, domain: str = "general", limit: int = 20) -> List[Dict[str, Any]]:
        """Gets the top contributors for a specific domain."""
        return self._request("GET", f"/reputation/leaderboard/{domain}?limit={limit}")

    def get_user_reputation_summary(self, user_id: str) -> Dict[str, Any]:
        """Gets a summary of a user's reputation across all domains."""
        return self._request("GET", f"/reputation/summary/{user_id}")

    def create_endorsement(
        self,
        target_type: str,
        target_id: str,
        user_id: str,
        weight: Optional[float] = None,
        domain: Optional[str] = None,
        value_category: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a weighted value endorsement on a discussion or study resource."""
        payload = {
            "target_type": target_type,
            "target_id": target_id,
            "user_id": user_id,
            "weight": weight,
            "domain": domain,
            "value_category": value_category,
            "comment": comment
        }
        return self._request("POST", "/endorsements", json_data=payload)

    # --------------------------------------------------------------------------
    # User Session Helper
    # --------------------------------------------------------------------------

    def session(self, user_id: str) -> "UserSession":
        """Creates an active user workflow session."""
        from .session import UserSession
        return UserSession(client=self, user_id=user_id)


# Alias
SocialClient = SocialPlatformClient
