"""Spider minimum vertical slice (deterministic, no network).

REQUEST -> FETCH (through an injected, grant-checked fetcher) -> content-
addressed store -> quote anchor check -> conclusion with provenance ->
accepted fact. A conclusion is SUPPORTED only if the exact quote is present
in bytes that were actually fetched from the approved origin; otherwise
CONTRADICTED (fetched, quote absent) or BLOCKED (origin not approved).
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


def check_claim(request, fetch, store, log, clock):
    """fetch(url) -> (final_url, bytes). Returns the conclusion dict and records it if decided."""
    parts = urlsplit(request.url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if parts.scheme != "https" or origin != request.approved_origin:
        return {"conclusion": "BLOCKED", "reason": f"{origin} is not the approved origin"}
    final_url, body = fetch(request.url)
    final = urlsplit(final_url)
    if f"{final.scheme}://{final.netloc}" != request.approved_origin:
        return {"conclusion": "BLOCKED", "reason": "redirect left the approved origin"}
    digest = store.put(body)
    text = store.get(digest).decode("utf-8", errors="replace")
    at = text.find(request.quote)
    conclusion = "SUPPORTED" if at >= 0 else "CONTRADICTED"
    anchor = {"sha256": digest, "url": final_url, "offset": at if at >= 0 else None, "length": len(request.quote)}
    log.append(AcceptedFact(request.workkey, 0, f"{conclusion}: {request.quote!r} at {final_url}",
                            (f"content:{digest}",), "controller", clock()))
    return {"conclusion": conclusion, "anchor": anchor}
