"""Redaction for the customer diagnostics record.

The support record is what a person saves and sends. It keeps the failure
and the ids that tie a controller event to a worker. Credentials are masked.
User-profile paths are rewritten to ``<HOME>``-relative paths, so the file
can still be found without publishing the account name.
"""

from __future__ import annotations

import re

_SECRET_ASSIGN = re.compile(
    r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key|credential|oauth)\s*[:=]\s*)(\S+)"
)
_BEARER = re.compile(r"(?i)(\bBearer\s+)(\S+)")
_TOKEN_SHAPE = re.compile(
    r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"AIza[0-9A-Za-z\-_]{35}|AKIA[0-9A-Z]{16}"
)
_PROFILE = re.compile(
    r"(?i)(?:[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+|/(?:home|Users)/[^/\s]+)"
)
_PATH_TAIL = re.compile(r"(?:[\\/][^\\/\r\n]+)+")


def _rewrite_user_paths(text: str) -> str:
    """Replace a profile prefix and keep the rest of that path."""
    pieces: list[str] = []
    cursor = 0
    for match in _PROFILE.finditer(text):
        if match.start() < cursor:
            continue
        pieces.append(text[cursor:match.start()])
        tail = ""
        end = match.end()
        tail_match = _PATH_TAIL.match(text, end)
        if tail_match:
            raw_tail = tail_match.group(0)
            parts = re.split(r"[\\/]", raw_tail)
            last = parts[-1]
            trimmed = re.split(r"\s+(?=[a-z(])", last, maxsplit=1)[0]
            trimmed = trimmed.rstrip(").,;:\"'")
            prefix_len = len(raw_tail) - len(last)
            tail = "/".join(parts[:-1] + [trimmed])
            end += prefix_len + len(trimmed)
        pieces.append("<HOME>" + tail)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def redact_diagnostics_text(value: str) -> str:
    """Mask credentials and rewrite user-profile paths. Leave the failure readable.

    A second call returns the same text. Ids and ordinary sentences are unchanged.
    """
    if not isinstance(value, str) or not value:
        return value
    text = _rewrite_user_paths(value)
    text = _SECRET_ASSIGN.sub(r"\1***REDACTED***", text)
    text = _BEARER.sub(r"\1***REDACTED***", text)
    text = _TOKEN_SHAPE.sub("***REDACTED***", text)
    return text


def diagnostic_evidence_name(path: str) -> str:
    """Label for one artifact in a support record.

    A relative artifact path stays a file name. A user-profile path is kept
    as a ``<HOME>``-relative path so support can see which file failed.
    """
    raw = str(path)
    shown = redact_diagnostics_text(raw)
    if shown != raw:
        return shown
    return raw.replace("\\", "/").rsplit("/", 1)[-1]
