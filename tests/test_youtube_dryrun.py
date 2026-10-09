"""YouTube dry-run upload request builder: private-only, offline, credential-free."""

import inspect
import socket

import pytest

from courier_worker.publish.youtube_dryrun import (
    PRIVACY_STATUS,
    UPLOAD_ENDPOINT,
    DryRunRefused,
    build_upload_request,
)


def test_builds_videos_insert_request_shape():
    request = build_upload_request(title="Hello", file_path="vid.mp4")
    assert request["method"] == "POST"
    assert request["url"] == UPLOAD_ENDPOINT
    assert request["params"] == {"part": "snippet,status", "uploadType": "resumable"}
    assert request["body"]["snippet"]["title"] == "Hello"
    assert request["media"] == {"file_path": "vid.mp4"}


def test_visibility_is_always_private():
    assert PRIVACY_STATUS == "private"
    assert build_upload_request(title="T", file_path="v.mp4")["body"]["status"]["privacyStatus"] == "private"
    explicit = build_upload_request(title="T", file_path="v.mp4", visibility="private")
    assert explicit["body"]["status"]["privacyStatus"] == "private"


def test_non_private_visibility_refused_fail_closed():
    for visibility in ("public", "unlisted"):
        with pytest.raises(DryRunRefused):
            build_upload_request(title="T", file_path="v.mp4", visibility=visibility)


def test_bad_metadata_refused():
    with pytest.raises(DryRunRefused):
        build_upload_request(title="  ", file_path="v.mp4")
    with pytest.raises(DryRunRefused):
        build_upload_request(title="x" * 101, file_path="v.mp4")
    with pytest.raises(DryRunRefused):
        build_upload_request(title="T", file_path="")


def test_no_network_calls_even_with_socket_blocked(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    request = build_upload_request(title="T", file_path="v.mp4", description="d")
    assert request["url"] == UPLOAD_ENDPOINT


def test_no_credential_parameters_in_signature():
    params = set(inspect.signature(build_upload_request).parameters)
    assert not {p for p in params if any(
        word in p for word in ("key", "token", "secret", "credential", "auth", "password"))}
