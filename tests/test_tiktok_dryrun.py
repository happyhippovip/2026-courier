"""TikTok dry-run inbox-draft request builder: draft-only, offline, credential-free."""

import inspect
import socket

import pytest

from courier_worker.publish.tiktok_dryrun import (
    POST_INIT_ENDPOINT,
    PRIVACY_LEVEL,
    DryRunRefused,
    build_inbox_draft_request,
)


def test_builds_inbox_init_request_shape():
    request = build_inbox_draft_request(title="Hello", file_path="vid.mp4", video_size=8000,
                                        chunk_size=4000)
    assert request["method"] == "POST"
    assert request["url"] == POST_INIT_ENDPOINT
    assert request["body"]["post_info"]["title"] == "Hello"
    assert request["body"]["post_info"]["privacy_level"] == "SELF_ONLY"
    assert request["body"]["source_info"] == {
        "source": "FILE_UPLOAD",
        "video_size": 8000,
        "chunk_size": 4000,
        "total_chunk_count": 2,
    }
    assert request["media"] == {"file_path": "vid.mp4"}


def test_draft_is_always_self_only():
    assert PRIVACY_LEVEL == "SELF_ONLY"
    default = build_inbox_draft_request(title="T", file_path="v.mp4", video_size=10, chunk_size=10)
    assert default["body"]["post_info"]["privacy_level"] == "SELF_ONLY"
    explicit = build_inbox_draft_request(title="T", file_path="v.mp4", video_size=10, chunk_size=10,
                                         visibility="SELF_ONLY")
    assert explicit["body"]["post_info"]["privacy_level"] == "SELF_ONLY"


def test_non_draft_visibility_refused_fail_closed():
    for visibility in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR"):
        with pytest.raises(DryRunRefused):
            build_inbox_draft_request(title="T", file_path="v.mp4", video_size=10, chunk_size=10,
                                      visibility=visibility)


def test_bad_metadata_refused():
    with pytest.raises(DryRunRefused):
        build_inbox_draft_request(title="  ", file_path="v.mp4", video_size=10, chunk_size=10)
    with pytest.raises(DryRunRefused):
        build_inbox_draft_request(title="x" * 2201, file_path="v.mp4", video_size=10,
                                  chunk_size=10)
    with pytest.raises(DryRunRefused):
        build_inbox_draft_request(title="T", file_path="", video_size=10, chunk_size=10)
    with pytest.raises(DryRunRefused):
        build_inbox_draft_request(title="T", file_path="v.mp4", video_size=0, chunk_size=10)
    with pytest.raises(DryRunRefused):
        build_inbox_draft_request(title="T", file_path="v.mp4", video_size=10, chunk_size=-1)
    with pytest.raises(DryRunRefused):
        build_inbox_draft_request(title="T", file_path="v.mp4", video_size=10, chunk_size=10,
                                  disable_duet="yes")


def test_local_file_is_never_touched(tmp_path):
    missing = str(tmp_path / "no-such-video.mp4")
    request = build_inbox_draft_request(title="T", file_path=missing, video_size=10, chunk_size=10)
    assert request["media"] == {"file_path": missing}


def test_no_network_calls_even_with_socket_blocked(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    request = build_inbox_draft_request(title="T", file_path="v.mp4", video_size=10, chunk_size=10,
                                        description="d")
    assert request["url"] == POST_INIT_ENDPOINT


def test_no_credential_parameters_in_signature():
    params = set(inspect.signature(build_inbox_draft_request).parameters)
    assert not {p for p in params if any(
        word in p for word in ("key", "token", "secret", "credential", "auth", "password"))}
