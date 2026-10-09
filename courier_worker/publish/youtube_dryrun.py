"""YouTube Data API upload request builder (dry run, lane L3).

Builds the ``videos.insert`` upload request as pure data. This module never
performs network I/O and never handles credentials: there is no API key,
OAuth token, or client-secret parameter anywhere in this file. Uploading is
always ``privacyStatus="private"``; any other requested visibility is refused
fail-closed instead of being silently downgraded.
"""

from __future__ import annotations

UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"
UPLOAD_PARTS = "snippet,status"
PRIVACY_STATUS = "private"
MAX_TITLE_LEN = 100


class DryRunRefused(ValueError):
    """The builder declined: bad metadata or a non-private visibility ask."""


def build_upload_request(
    *,
    title: str,
    file_path: str,
    description: str = "",
    category_id: str = "22",
    notify_subscribers: bool = False,
    visibility: str | None = None,
) -> dict:
    """Build the resumable ``videos.insert`` request for one local video file.

    ``file_path`` names the local file to upload; it is carried as data only
    and never opened, read, or stat'ed here. ``visibility``, when given, must
    be ``"private"``; anything else raises :class:`DryRunRefused`.
    """
    if not isinstance(title, str) or not title.strip():
        raise DryRunRefused("BAD_TITLE")
    if len(title) > MAX_TITLE_LEN:
        raise DryRunRefused("TITLE_TOO_LONG")
    if not isinstance(file_path, str) or not file_path:
        raise DryRunRefused("BAD_FILE_PATH")
    if not isinstance(description, str):
        raise DryRunRefused("BAD_DESCRIPTION")
    if not isinstance(category_id, str) or not category_id:
        raise DryRunRefused("BAD_CATEGORY_ID")
    if not isinstance(notify_subscribers, bool):
        raise DryRunRefused("BAD_NOTIFY_SUBSCRIBERS")
    if visibility is not None and visibility != PRIVACY_STATUS:
        raise DryRunRefused("VISIBILITY_MUST_BE_PRIVATE")
    return {
        "method": "POST",
        "url": UPLOAD_ENDPOINT,
        "params": {"part": UPLOAD_PARTS, "uploadType": "resumable"},
        "media": {"file_path": file_path},
        "body": {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": PRIVACY_STATUS,
                "embeddable": True,
                "notifySubscribers": notify_subscribers,
            },
        },
    }
