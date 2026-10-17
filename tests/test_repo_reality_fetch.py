"""Offline tests for the public GitHub tarball fetch. No network."""

import email
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from courier_core import repo_reality_fetch as fetch
from courier_core.repo_reality_fetch import FetchError
from courier_core.repo_reality_report import main

ROOT = Path(__file__).resolve().parents[1]
SHA = "ab" * 20


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None):
        self._body = body
        self._offset = 0
        self.status = status
        self.headers = headers or {}

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = len(self._body) - self._offset
        chunk = self._body[self._offset:self._offset + n]
        self._offset += len(chunk)
        return chunk

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr(fetch, "urlopen", boom)


def _tar(entries: list[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info, payload in entries:
            archive.addfile(info, io.BytesIO(payload) if payload is not None else None)
    return buffer.getvalue()


def _file(name: str, payload: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    info.type = tarfile.REGTYPE
    return info, payload


def _symlink(name: str, target: str) -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    return info, None


def _hardlink(name: str, target: str) -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = tarfile.LNKTYPE
    info.linkname = target
    return info, None


def _device(name: str) -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = tarfile.CHRTYPE
    info.devmajor = 1
    info.devminor = 3
    return info, None


def _serve(payload: bytes):
    calls: list[tuple[str, int | None]] = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse(payload)

    opener.calls = calls
    return opener


def _track_temp(monkeypatch) -> list[str]:
    created: list[str] = []
    real = tempfile.mkdtemp

    def wrapped(*args, **kwargs):
        path = real(*args, **kwargs)
        created.append(path)
        return path

    monkeypatch.setattr(fetch.tempfile, "mkdtemp", wrapped)
    return created


def test_normal_tarball_records_evidence_and_cleans_up(tmp_path, monkeypatch):
    token = "ghp_" + "E" * 36
    prefix = f"widgets-{SHA}"
    payload = _tar(
        [
            _file(f"{prefix}/README.md", b"# Demo\n"),
            _file(f"{prefix}/src/app.py", b"raise SystemExit('customer-code-ran')\n"),
            _file(f"{prefix}/config/app.env", f'TOKEN = "{token}"\n'.encode()),
            _symlink(f"{prefix}/src/link", "app.py"),
        ]
    )
    opener = _serve(payload)
    monkeypatch.setattr(fetch, "urlopen", opener)
    created = _track_temp(monkeypatch)
    out = tmp_path / "report.md"
    pytest_json = tmp_path / "pytest.json"
    pytest_json.write_text(
        json.dumps({"summary": {"passed": 1, "failed": 0, "skipped": 2}}),
        encoding="utf-8",
    )
    assert main(["--github", "acme/widgets@main", "--pytest-json", str(pytest_json), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    assert text.startswith("# Repo Reality Check\n")
    assert "Source: github.com/acme/widgets@main" in text
    assert f"- Commit: {SHA}" in text
    assert f"- Tarball sha256: {digest}" in text
    assert text.index("- Tarball sha256:") < text.index("## Repositorygröße")
    assert "- README: present (README.md)" in text
    assert "- Passed: 1" in text
    assert "- Skipped: 2" in text
    assert token not in text
    assert "customer-code-ran" not in text
    assert "config/app.env" in text
    assert str(pytest_json) not in text
    assert created and all(not Path(path).exists() for path in created)
    assert created[0] not in text
    url, timeout = opener.calls[0]
    assert url == "https://codeload.github.com/acme/widgets/tar.gz/main"
    assert timeout == fetch.TIMEOUT_SECONDS
    assert len(opener.calls) == 1


def test_sha_comes_from_commit_api_when_directory_has_none(tmp_path, monkeypatch):
    sha = "cd" * 20
    leaked = "ghp_" + "F" * 36
    payload = _tar([_file("widgets-main/README.md", b"# Demo\n")])
    api = json.dumps({"sha": sha, "commit": {"message": leaked}}).encode()

    def opener(request, timeout):
        opener.urls.append(request.full_url)
        if "codeload.github.com" in request.full_url:
            return FakeResponse(payload)
        if "api.github.com" in request.full_url:
            return FakeResponse(api)
        raise AssertionError(request.full_url)

    opener.urls = []
    monkeypatch.setattr(fetch, "urlopen", opener)
    out = tmp_path / "report.md"
    assert main(["--github", "acme/widgets@main", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert f"- Commit: {sha}" in text
    assert leaked not in text
    assert any(url.endswith("/repos/acme/widgets/commits/main") for url in opener.urls)


def test_traversal_and_absolute_paths_are_rejected(tmp_path, monkeypatch):
    outside = tmp_path / "outside.txt"
    created = _track_temp(monkeypatch)
    monkeypatch.setattr(fetch, "urlopen", _serve(_tar([_file("../outside.txt", b"pwned\n")])))
    with pytest.raises(FetchError, match="escapes"):
        fetch.fetch_public("acme/widgets@main")
    assert not outside.exists()
    assert created and not Path(created[0]).exists()

    created.clear()
    monkeypatch.setattr(fetch, "urlopen", _serve(_tar([_file("/tmp/abs.txt", b"pwned\n")])))
    with pytest.raises(FetchError, match="absolute"):
        fetch.fetch_public("acme/widgets@main")
    assert not Path("/tmp/abs.txt").exists()
    assert created and not Path(created[-1]).exists()


def test_symlink_and_hardlink_escape_and_device_are_rejected(monkeypatch):
    prefix = f"widgets-{SHA}"
    cases = [
        _tar([_file(f"{prefix}/README.md", b"# Demo\n"), _symlink(f"{prefix}/escape", "/tmp/outside")]),
        _tar([_file(f"{prefix}/README.md", b"# Demo\n"), _symlink(f"{prefix}/escape", "../../../../tmp/outside")]),
        _tar([_file(f"{prefix}/README.md", b"# Demo\n"), _hardlink(f"{prefix}/hard", "../outside.txt")]),
        _tar([_file(f"{prefix}/README.md", b"# Demo\n"), _device(f"{prefix}/devnull")]),
    ]
    messages = ["link points outside", "link points outside", "link points outside", "device file"]
    created = _track_temp(monkeypatch)
    for payload, message in zip(cases, messages, strict=True):
        monkeypatch.setattr(fetch, "urlopen", _serve(payload))
        with pytest.raises(FetchError, match=message):
            fetch.fetch_public("acme/widgets@main")
    assert created and all(not Path(path).exists() for path in created)


def test_oversize_download_aborts_without_extracting(monkeypatch):
    monkeypatch.setattr(fetch, "MAX_BYTES", 32)
    monkeypatch.setattr(fetch, "urlopen", _serve(b"x" * 100))
    with pytest.raises(FetchError, match="byte cap"):
        fetch.fetch_public("acme/widgets@main")

    monkeypatch.setattr(
        fetch,
        "urlopen",
        lambda _request, timeout: FakeResponse(b"", headers={"Content-Length": "1000"}),
    )
    with pytest.raises(FetchError, match="byte cap"):
        fetch.fetch_public("acme/widgets@main")


def test_content_length_over_cap_does_not_read_the_body(monkeypatch):
    monkeypatch.setattr(fetch, "MAX_BYTES", 32)

    class Guard(FakeResponse):
        def read(self, n: int = -1) -> bytes:
            raise AssertionError("body was read")

    monkeypatch.setattr(
        fetch,
        "urlopen",
        lambda _request, timeout: Guard(b"", headers={"Content-Length": "1000"}),
    )
    with pytest.raises(FetchError, match="byte cap"):
        fetch.fetch_public("acme/widgets@main")


def test_file_cap_and_corrupt_archive(monkeypatch):
    prefix = f"widgets-{SHA}"
    payload = _tar(
        [
            _file(f"{prefix}/a.txt", b"a\n"),
            _file(f"{prefix}/b.txt", b"b\n"),
            _file(f"{prefix}/c.txt", b"c\n"),
        ]
    )
    monkeypatch.setattr(fetch, "MAX_MEMBERS", 2)
    monkeypatch.setattr(fetch, "urlopen", _serve(payload))
    with pytest.raises(FetchError, match="file cap"):
        fetch.fetch_public("acme/widgets@main")

    monkeypatch.setattr(fetch, "MAX_MEMBERS", 20_000)
    monkeypatch.setattr(fetch, "urlopen", _serve(b"this is not a gzip"))
    with pytest.raises(FetchError, match="could not be read"):
        fetch.fetch_public("acme/widgets@main")


def test_private_or_missing_repo_exits_2_without_leaking_body(capsys, monkeypatch):
    secret = b"secret-body-should-not-leak"

    def opener(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "Not Found",
            email.message.EmailMessage(),
            io.BytesIO(secret),
        )

    monkeypatch.setattr(fetch, "urlopen", opener)
    assert main(["--github", "acme/private@main"]) == 2
    err = capsys.readouterr().err
    assert "repository not found or not public" in err
    assert "secret-body" not in err
    assert "Not Found" not in err


def test_bad_spec_and_both_inputs_exit_2(tmp_path, capsys):
    assert main(["--github", "not a spec"]) == 2
    assert "owner/repo" in capsys.readouterr().err
    assert main(["--github", "acme/widgets@../secret"]) == 2
    assert "ref is not allowed" in capsys.readouterr().err
    repo = tmp_path / "local"
    repo.mkdir()
    assert main(["--github", "acme/widgets", str(repo)]) == 2
    assert "not both" in capsys.readouterr().err
    assert main([]) == 2


def test_download_url_must_be_allowlisted_https():
    with pytest.raises(FetchError, match="not allowed"):
        fetch._download("http://codeload.github.com/acme/widgets/tar.gz/main")
    with pytest.raises(FetchError, match="not allowed"):
        fetch._download("https://invalid.invalid/tar.gz")


def test_redirects_must_stay_on_allowlisted_https():
    handler = fetch._HttpsAllowlistRedirect()
    request = urllib.request.Request("https://codeload.github.com/acme/widgets/tar.gz/main")
    allowed = handler.redirect_request(
        request, None, 302, "Found", {}, "https://api.github.com/repos/acme/widgets/commits/main"
    )
    assert allowed.get_full_url().startswith("https://api.github.com/")
    with pytest.raises(FetchError, match="not allowed"):
        handler.redirect_request(request, None, 302, "Found", {}, "http://codeload.github.com/acme/widgets/tar.gz/main")
    with pytest.raises(FetchError, match="not allowed"):
        handler.redirect_request(request, None, 302, "Found", {}, "https://invalid.invalid/tar.gz")


def test_module_entrypoint_rejects_bad_spec_offline():
    proc = subprocess.run(
        [sys.executable, "-m", "courier_core.repo_reality_report", "--github", "nope"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "owner/repo" in proc.stderr


def test_docs_describe_public_fetch():
    doc = (ROOT / "docs" / "REPO_REALITY_CHECK.md").read_text(encoding="utf-8")
    assert "--github owner/repo[@ref]" in doc
    assert "codeload.github.com" in doc
    assert "50 MB" in doc
    assert "20,000" in doc
    assert "sha256" in doc
