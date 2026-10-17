"""TikTok Content Posting API inbox-draft request builder (dry run, lane L3).

Builds the ``POST /v2/post/publish/inbox/video/init/`` request as pure data.
This module never performs network I/O, never opens the local video file, and
never handles credentials: there is no API key, access token, or client-secret
parameter anywhere in this file. Drafts stay ``privacy_level="SELF_ONLY"``;
any other requested visibility is refused fail-closed instead of being
silently sent anywhere.
"""

from __future__ import annotations

POST_INIT_ENDPOINT = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
PRIVACY_LEVEL = "SELF_ONLY"
POST_MODE = "DIRECT_POST"
MEDIA_TYPE = "VIDEO"
SOURCE = "FILE_UPLOAD"
MAX_TITLE_LEN = 2200


class DryRunRefused(ValueError):
    """The builder declined: bad metadata or a non-draft visibility ask."""


def build_inbox_draft_request(
    *,
    title: str,
    file_path: str,
    video_size: int,
    chunk_size: int,
    description: str = "",
    disable_duet: bool = False,
    disable_comment: bool = False,
    disable_stitch: bool = False,
    visibility: str | None = None,
) -> dict:
    """Build the inbox ``video/init`` request for one local video file.

    ``file_path`` names the local file to upload; it is carried as data only
    and never opened, read, or stat'ed here. ``video_size`` and ``chunk_size``
    are positive byte counts; the chunk count is derived. ``visibility``, when
    given, must be ``"SELF_ONLY"``; anything else raises
    :class:`DryRunRefused`.
    """
    if not isinstance(title, str) or not title.strip():
        raise DryRunRefused("BAD_TITLE")
    if len(title) > MAX_TITLE_LEN:
        raise DryRunRefused("TITLE_TOO_LONG")
    if not isinstance(file_path, str) or not file_path:
        raise DryRunRefused("BAD_FILE_PATH")
    if not isinstance(description, str):
        raise DryRunRefused("BAD_DESCRIPTION")
    for name, value in (("video_size", video_size), ("chunk_size", chunk_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise DryRunRefused(f"BAD_{name.upper()}")
    for name, value in (("disable_duet", disable_duet),
                        ("disable_comment", disable_comment),
                        ("disable_stitch", disable_stitch)):
        if not isinstance(value, bool):
            raise DryRunRefused(f"BAD_{name.upper()}")
    if visibility is not None and visibility != PRIVACY_LEVEL:
        raise DryRunRefused("VISIBILITY_MUST_BE_SELF_ONLY")
    total_chunk_count = -(-video_size // chunk_size)
    return {
        "method": "POST",
        "url": POST_INIT_ENDPOINT,
        "headers": {"Content-Type": "application/json; charset=UTF-8"},
        "media": {"file_path": file_path},
        "body": {
            "post_mode": POST_MODE,
            "media_type": MEDIA_TYPE,
            "post_info": {
                "title": title,
                "description": description,
                "privacy_level": PRIVACY_LEVEL,
                "disable_duet": disable_duet,
                "disable_comment": disable_comment,
                "disable_stitch": disable_stitch,
            },
            "source_info": {
                "source": SOURCE,
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            },
        },
    }
