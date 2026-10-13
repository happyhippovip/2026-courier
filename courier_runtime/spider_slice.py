"""Spider minimum vertical slice (deterministic, no network).

REQUEST -> FETCH (through an injected, grant-checked fetcher) -> content-
addressed store -> quote anchor check -> conclusion with provenance ->
accepted fact. A conclusion is SUPPORTED only if the exact quote is present
in bytes that were actually fetched from the approved origin; otherwise
CONTRADICTED (fetched, quote absent) or BLOCKED (origin not approved, or the
quote itself is missing, empty, or not encodable as UTF-8).

The quote is matched as its raw UTF-8 bytes. Invalid body bytes are not
replaced, so a Unicode replacement character cannot invent a match.
"""
import hashlib
from dataclasses import dataclass
from urllib.parse import urlsplit

from courier_runtime.continuation import AcceptedFact


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


def _quote_needle(quote):
    """UTF-8 bytes of a real quote, or a fail-closed BLOCKED conclusion."""
    if not isinstance(quote, str):
        return None, {"conclusion": "BLOCKED", "reason": "quote is missing"}
    if quote == "":
        return None, {"conclusion": "BLOCKED", "reason": "empty quote is not a claim"}
    try:
        return quote.encode("utf-8"), None
    except UnicodeEncodeError:
        return None, {"conclusion": "BLOCKED", "reason": "quote cannot be encoded as utf-8"}


def check_claim(request, fetch, store, log, clock):
    """fetch(url) -> (final_url, bytes). Returns the conclusion dict and records it if decided."""
    needle, rejected = _quote_needle(request.quote)
    if rejected:
        return rejected
    parts = urlsplit(request.url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if parts.scheme != "https" or origin != request.approved_origin:
        return {"conclusion": "BLOCKED", "reason": f"{origin} is not the approved origin"}
    final_url, body = fetch(request.url)
    final = urlsplit(final_url)
    if f"{final.scheme}://{final.netloc}" != request.approved_origin:
        return {"conclusion": "BLOCKED", "reason": "redirect left the approved origin"}
    digest = store.put(body)
    stored = store.get(digest)
    at = stored.find(needle)
    conclusion = "SUPPORTED" if at >= 0 else "CONTRADICTED"
    anchor = {"sha256": digest, "url": final_url, "offset": at if at >= 0 else None, "length": len(needle)}
    log.append(AcceptedFact(request.workkey, 0, f"{conclusion}: {request.quote!r} at {final_url}",
                            (f"content:{digest}",), "controller", clock()))
    return {"conclusion": conclusion, "anchor": anchor}
