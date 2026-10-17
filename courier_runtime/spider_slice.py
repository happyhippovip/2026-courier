"""Spider minimum vertical slice (deterministic, no network).

REQUEST -> FETCH (through an injected, grant-checked fetcher) -> content-
addressed store -> quote anchor check -> conclusion with provenance ->
accepted fact. A conclusion is SUPPORTED only if the exact quote is present
as UTF-8 bytes in a body that was actually fetched from the approved origin.
offset and length index those raw bytes.

BLOCKED (nothing stored, no accepted fact) covers: a missing, empty, or
non-encodable quote, checked before any fetch; an origin that is not
approved; a body over the fetch cap; a declared content type outside the
contract; bytes that are not valid UTF-8. CONTRADICTED means the body was
accepted and the quote's UTF-8 bytes are absent. Invalid UTF-8 is never
searched, so a replacement character cannot be invented from a bad byte.
A real U+FFFD (UTF-8 EF BF BD) in a valid body is an ordinary exact match.
"""
import hashlib
from dataclasses import dataclass
from urllib.parse import urlsplit

from courier_runtime.continuation import AcceptedFact

# Prepared cap for one fetched body. Callers can pass a smaller max_bytes.
# This does not open a socket; the injected fetcher still has to stop reading.
MAX_FETCH_BYTES = 1_048_576
_MAX_CONTENT_TYPE_CHARS = 256
_ALLOWED_MEDIA = frozenset({
    "text/plain",
    "text/html",
    "application/xhtml+xml",
})
_ALLOWED_CHARSETS = frozenset({"utf-8", "utf8", "us-ascii", "ascii"})


class ContentStore:
    def __init__(self):
        self._blobs = {}

    def put(self, data):
        digest = hashlib.sha256(data).hexdigest()
        self._blobs[digest] = data
        return digest

    def get(self, digest):
        data = self._blobs[digest]
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("store tamper detected")
        return data


@dataclass(frozen=True)
class ResearchRequest:
    workkey: str
    url: str
    quote: str
    approved_origin: str          # scheme://host[:port] the grant covers


class FetchTooLarge(ValueError):
    """Raised when a fetched body would pass the prepared byte cap."""

    def __init__(self, max_bytes):
        self.max_bytes = max_bytes
        super().__init__(f"fetch body exceeds {max_bytes} bytes")


def take_bounded(chunks, max_bytes):
    """Join fetched chunks, refusing the whole body once max_bytes is exceeded.

    The overflow chunk is not appended. No network I/O happens here.
    """
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
        raise ValueError("max_bytes must be an integer >= 0")
    buf = bytearray()
    for chunk in chunks:
        if isinstance(chunk, str) or not isinstance(chunk, (bytes, bytearray)):
            raise TypeError("fetch chunk must be bytes")
        if len(chunk) > max_bytes - len(buf):
            raise FetchTooLarge(max_bytes)
        buf.extend(chunk)
    return bytes(buf)


def parse_content_type(value):
    """Return (media_type, charset or None). Fail closed on a messy header."""
    if not isinstance(value, str):
        raise ValueError("content type must be a string")
    if not value.strip() or len(value) > _MAX_CONTENT_TYPE_CHARS:
        raise ValueError("content type is empty or too long")
    parts = [part.strip() for part in value.split(";")]
    media = parts[0].lower()
    if media.count("/") != 1 or any(ch.isspace() for ch in media):
        raise ValueError("content type media is malformed")
    main, sub = media.split("/", 1)
    if not main or not sub:
        raise ValueError("content type media is malformed")
    charset = None
    seen = set()
    for param in parts[1:]:
        if "=" not in param:
            raise ValueError("content type parameter is malformed")
        key, raw = param.split("=", 1)
        key = key.strip().lower()
        raw = raw.strip()
        if not key or key in seen:
            raise ValueError("content type parameter is malformed")
        seen.add(key)
        if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            raw = raw[1:-1]
        if raw == "":
            raise ValueError("content type parameter is empty")
        if key == "charset":
            charset = raw.lower()
    return media, charset


def _blocked(reason):
    return {"conclusion": "BLOCKED", "reason": reason}


def _quote_needle(quote):
    """UTF-8 bytes of a real quote, or a fail-closed BLOCKED conclusion.

    Checked before any fetch. A lone surrogate cannot be encoded as UTF-8.
    """
    if not isinstance(quote, str):
        return None, _blocked("quote is missing")
    if quote == "":
        return None, _blocked("empty quote is not a claim")
    try:
        return quote.encode("utf-8"), None
    except UnicodeEncodeError:
        return None, _blocked("quote cannot be encoded as utf-8")


def _fetched_parts(fetched):
    if not isinstance(fetched, (tuple, list)):
        return None
    if len(fetched) == 2:
        return fetched[0], fetched[1], None
    if len(fetched) == 3:
        return fetched[0], fetched[1], fetched[2]
    return None


def check_claim(request, fetch, store, log, clock, max_bytes=MAX_FETCH_BYTES):
    """fetch(url) -> (final_url, bytes) or (final_url, bytes, content_type).

    Records an accepted fact only for SUPPORTED or CONTRADICTED. BLOCKED
    paths write nothing and do not keep the body in the store. offset and
    length are indexes into the stored raw bytes.
    """
    needle, rejected = _quote_needle(request.quote)
    if rejected:
        return rejected
    parts = urlsplit(request.url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if parts.scheme != "https" or origin != request.approved_origin:
        return _blocked(f"{origin} is not the approved origin")
    unpacked = _fetched_parts(fetch(request.url))
    if unpacked is None:
        return _blocked("fetcher returned an unexpected result")
    final_url, body, content_type = unpacked
    final = urlsplit(final_url)
    if f"{final.scheme}://{final.netloc}" != request.approved_origin:
        return _blocked("redirect left the approved origin")
    try:
        body = take_bounded((body,), max_bytes)
    except FetchTooLarge:
        return _blocked(f"fetch body exceeds {max_bytes} bytes")
    except TypeError:
        return _blocked("fetch body is not bytes")
    charset = None
    if content_type is not None:
        try:
            media, charset = parse_content_type(content_type)
        except ValueError:
            return _blocked("content type is outside the contract")
        if media not in _ALLOWED_MEDIA:
            return _blocked(f"{media} is outside the content-type contract")
        if charset is not None and charset not in _ALLOWED_CHARSETS:
            return _blocked(f"charset {charset} is outside the content-type contract")
    if charset in {"ascii", "us-ascii"} and any(byte > 127 for byte in body):
        return _blocked("body is not US-ASCII")
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        return _blocked("body is not valid UTF-8")
    digest = store.put(body)
    stored = store.get(digest)
    at = stored.find(needle)
    conclusion = "SUPPORTED" if at >= 0 else "CONTRADICTED"
    anchor = {"sha256": digest, "url": final_url, "offset": at if at >= 0 else None, "length": len(needle)}
    log.append(AcceptedFact(request.workkey, 0, f"{conclusion}: {request.quote!r} at {final_url}",
                            (f"content:{digest}",), "controller", clock()))
    return {"conclusion": conclusion, "anchor": anchor}
