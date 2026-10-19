"""Download one public GitHub tarball for a Repo Reality Check.

Stdlib urllib only. HTTPS, 30 second timeout, 50 MB download cap.
The archive is extracted into a fresh temporary directory. Absolute paths,
``..`` paths, device files, and links that point outside that directory are
rejected. Links that stay inside are not written. Nothing in the archive is
executed. The caller removes the temp directory.

Public repositories only. A missing or private repository is a FetchError.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 50 * 1024 * 1024
MAX_EXTRACT_BYTES = 200 * 1024 * 1024
MAX_MEMBERS = 20_000
TIMEOUT_SECONDS = 30
ALLOWED_HOSTS = frozenset({"api.github.com", "codeload.github.com"})

_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_REF = re.compile(r"^[A-Za-z0-9._/-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIR_SHA = re.compile(r"-([0-9a-f]{40})$")
_METADATA_TYPES = frozenset(
    {
        tarfile.GNUTYPE_LONGNAME,
        tarfile.GNUTYPE_LONGLINK,
        tarfile.XGLTYPE,
        tarfile.XHDTYPE,
    }
)


class FetchError(Exception):
    """The public tarball could not be downloaded or extracted safely."""


@dataclass(frozen=True)
class FetchedRepo:
    root: Path
    temp_dir: Path
    owner: str
    repo: str
    ref: str
    sha: str
    tarball_sha256: str


class _HttpsAllowlistRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_allowed(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def urlopen(request, timeout):
    """Open an allowlisted HTTPS URL. Tests replace this function."""
    opener = urllib.request.build_opener(_HttpsAllowlistRedirect)
    return opener.open(request, timeout=timeout)


def parse_spec(spec: str) -> tuple[str, str, str]:
    """Return owner, repo, and ref. Ref defaults to HEAD."""
    text = spec.strip()
    if "@" in text:
        slug, ref = text.split("@", 1)
    else:
        slug, ref = text, "HEAD"
    if slug.count("/") != 1:
        raise FetchError("github spec must be owner/repo or owner/repo@ref")
    owner, repo = slug.split("/", 1)
    if not _OWNER.fullmatch(owner) or not _REPO.fullmatch(repo) or repo in {".", ".."}:
        raise FetchError("github spec must be owner/repo or owner/repo@ref")
    if not ref or len(ref) > 255 or not _REF.fullmatch(ref):
        raise FetchError("ref is not allowed")
    if any(part in {"", ".", ".."} for part in ref.split("/")):
        raise FetchError("ref is not allowed")
    return owner, repo, ref


def tarball_url(owner: str, repo: str, ref: str) -> str:
    quoted = urllib.parse.quote(ref, safe="/")
    return f"https://codeload.github.com/{owner}/{repo}/tar.gz/{quoted}"


def api_commit_url(owner: str, repo: str, ref: str) -> str:
    quoted = urllib.parse.quote(ref, safe="/")
    return f"https://api.github.com/repos/{owner}/{repo}/commits/{quoted}"


def fetch_public(spec: str) -> FetchedRepo:
    """Download and safely extract ``spec``. Caller deletes ``temp_dir``."""
    owner, repo, ref = parse_spec(spec)
    payload = _download(tarball_url(owner, repo, ref))
    digest = hashlib.sha256(payload).hexdigest()
    temp_dir = Path(tempfile.mkdtemp(prefix="repo-reality-"))
    try:
        root = _extract(payload, temp_dir)
        sha = _resolve_sha(owner, repo, ref, root.name)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return FetchedRepo(
        root=root,
        temp_dir=temp_dir,
        owner=owner,
        repo=repo,
        ref=ref,
        sha=sha,
        tarball_sha256=digest,
    )


def _download(url: str) -> bytes:
    _require_allowed(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "courier-repo-reality-check",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        response = urlopen(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise FetchError("repository not found or not public") from exc
        raise FetchError("tarball download failed") from exc
    except urllib.error.URLError as exc:
        raise FetchError("tarball download failed") from exc
    with response:
        status = getattr(response, "status", None) or response.getcode()
        if status in (401, 403, 404):
            raise FetchError("repository not found or not public")
        if status != 200:
            raise FetchError("tarball download failed")
        headers = getattr(response, "headers", None)
        declared = _content_length(headers)
        if declared is not None and declared > MAX_BYTES:
            raise FetchError("tarball exceeds the byte cap")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = response.read(64 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_BYTES:
                raise FetchError("tarball exceeds the byte cap")
            chunks.append(block)
    return b"".join(chunks)


def _content_length(headers) -> int | None:
    if headers is None:
        return None
    raw = headers.get("Content-Length")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _require_allowed(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise FetchError("download URL is not allowed")


def _resolve_sha(owner: str, repo: str, ref: str, top_dir: str) -> str:
    if _SHA.fullmatch(ref):
        return ref
    found = _DIR_SHA.search(top_dir)
    if found:
        return found.group(1)
    return _sha_from_api(owner, repo, ref)


def _sha_from_api(owner: str, repo: str, ref: str) -> str:
    raw = _download(api_commit_url(owner, repo, ref))
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FetchError("could not resolve commit") from exc
    sha = data.get("sha") if isinstance(data, dict) else None
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise FetchError("could not resolve commit")
    return sha


def _extract(payload: bytes, dest: Path) -> Path:
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz")
    except tarfile.TarError as exc:
        raise FetchError("tarball could not be read") from exc
    try:
        with archive:
            members = archive.getmembers()
            if len(members) > MAX_MEMBERS:
                raise FetchError("tarball exceeds the file cap")
            files: list[tuple[tarfile.TarInfo, str]] = []
            directories: list[str] = []
            total = 0
            for member in members:
                kind, relative = _classify(member)
                if kind == "file":
                    total += member.size
                    if total > MAX_EXTRACT_BYTES:
                        raise FetchError("tarball exceeds the extract cap")
                    files.append((member, relative))
                elif kind == "dir":
                    directories.append(relative)
            if not files and not directories:
                raise FetchError("tarball layout is not a single checkout")
            names = [relative for _member, relative in files] + directories
            top = _single_top(names)
            for relative in sorted(directories, key=len):
                _mkdir(dest, relative)
            for member, relative in files:
                _write_file(archive, member, dest, relative)
    except FetchError:
        raise
    except tarfile.TarError as exc:
        raise FetchError("tarball could not be read") from exc
    root = dest / top
    if not root.is_dir():
        raise FetchError("tarball layout is not a single checkout")
    return root


def _classify(member: tarfile.TarInfo) -> tuple[str, str]:
    if member.type in _METADATA_TYPES:
        return "skip", ""
    relative = _safe_relative(member.name)
    if member.isdev() or member.isfifo():
        raise FetchError("tarball contains a device file")
    if member.issym() or member.islnk():
        if not _link_inside(relative, member.linkname or "", symlink=member.issym()):
            raise FetchError("tarball link points outside the checkout")
        return "link", relative
    if member.isdir():
        return "dir", relative
    if member.isfile():
        if member.size < 0 or member.size > MAX_EXTRACT_BYTES:
            raise FetchError("tarball exceeds the extract cap")
        return "file", relative
    raise FetchError("tarball contains an unsupported entry")


def _safe_relative(name: str) -> str:
    text = name[2:] if name.startswith("./") else name
    if not text or "\\" in text or "\x00" in text:
        raise FetchError("tarball path escapes the checkout")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise FetchError("tarball path is absolute")
    parts = [part for part in text.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise FetchError("tarball path escapes the checkout")
    relative = "/".join(parts)
    if len(relative) > 1024:
        raise FetchError("tarball path escapes the checkout")
    return relative


def _link_inside(member_name: str, linkname: str, symlink: bool) -> bool:
    if not linkname or "\\" in linkname or "\x00" in linkname:
        return False
    if linkname.startswith("/") or re.match(r"^[A-Za-z]:", linkname):
        return False
    if symlink:
        combined = posixpath.normpath(posixpath.join(posixpath.dirname(member_name), linkname))
    else:
        combined = posixpath.normpath(linkname)
    if combined in {"", "."} or combined == ".." or combined.startswith("../") or posixpath.isabs(combined):
        return False
    return True


def _single_top(names: list[str]) -> str:
    tops = {name.split("/", 1)[0] for name in names if name}
    if len(tops) != 1:
        raise FetchError("tarball layout is not a single checkout")
    return next(iter(tops))


def _mkdir(dest: Path, relative: str) -> None:
    target = dest.joinpath(*relative.split("/"))
    target.mkdir(parents=True, exist_ok=True)
    if not target.resolve().is_relative_to(dest.resolve()):
        raise FetchError("tarball path escapes the checkout")


def _write_file(archive: tarfile.TarFile, member: tarfile.TarInfo, dest: Path, relative: str) -> None:
    target = dest.joinpath(*relative.split("/"))
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    if not parent.resolve().is_relative_to(dest.resolve()):
        raise FetchError("tarball path escapes the checkout")
    source = archive.extractfile(member)
    if source is None:
        raise FetchError("tarball could not be extracted")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o644)
    except OSError as exc:
        raise FetchError("tarball could not be extracted") from exc
    remaining = MAX_EXTRACT_BYTES
    try:
        with source, os.fdopen(fd, "wb") as handle:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                remaining -= len(block)
                if remaining < 0:
                    raise FetchError("tarball exceeds the extract cap")
                handle.write(block)
    except FetchError:
        raise
    except OSError as exc:
        raise FetchError("tarball could not be extracted") from exc
