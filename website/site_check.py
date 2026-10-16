"""Fail-closed checks for the static pilot site. No network."""
import re
from pathlib import Path

_HREF = re.compile(r'href="([^"]*)"')
_EXTERNAL = ("http://", "https://", "mailto:", "tel:")


def broken_internal_links(root):
    """Relative and site-root links that do not name a file inside root.

    A bare ``/`` is not index.html: the published tree has to name the file.
    Fragments are checked against id attributes of the target page.
    """
    root = Path(root)
    problems = []
    for page in sorted(root.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        for href in _HREF.findall(text):
            if href.startswith(_EXTERNAL) or href.startswith("#"):
                target = page
                fragment = href[1:] if href.startswith("#") else ""
            else:
                path, _, fragment = href.partition("#")
                if path.startswith("/"):
                    relative = path.lstrip("/")
                    candidate = root / relative if relative else root / ""
                else:
                    candidate = page.parent / path
                try:
                    candidate = candidate.resolve()
                    candidate.relative_to(root.resolve())
                except ValueError:
                    problems.append((str(page.relative_to(root)), href))
                    continue
                target = candidate
            if not target.is_file():
                problems.append((str(page.relative_to(root)), href))
                continue
            if fragment and not _has_id(target, fragment):
                problems.append((str(page.relative_to(root)), href))
    return problems


def _has_id(page, fragment):
    text = page.read_text(encoding="utf-8")
    return ('id="%s"' % fragment) in text or ("id='%s'" % fragment) in text


def resolve_request(root, request_path):
    """Map a request path to a file name inside root, or '404'.

    Unknown paths, escapes, and directories are 404. They are not index.html.
    """
    root = Path(root).resolve()
    raw = request_path.split("?", 1)[0].split("#", 1)[0]
    if raw in ("", "/"):
        relative = "index.html"
    else:
        relative = raw.lstrip("/")
    parts = Path(relative).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return "404"
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return "404"
    if candidate.is_file():
        return str(candidate.relative_to(root))
    return "404"


def not_found_home_href(html):
    """First href on the not-found page that navigates away. That is the way back home."""
    for match in _HREF.finditer(html):
        href = match.group(1)
        if not href.startswith("#"):
            return href
    return ""
