"""Spider minimum vertical slice (deterministic, no network).

REQUEST -> FETCH (through an injected, grant-checked fetcher) -> content-
addressed store -> quote anchor check -> conclusion with provenance ->
accepted fact. A conclusion is SUPPORTED only if the exact quote is present
in bytes that were actually fetched from the approved origin; otherwise
CONTRADICTED (fetched, quote absent) or BLOCKED (origin not approved).
"""
import hashlib
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from courier_runtime.continuation import AcceptedFact


def normalize_origin(url_or_origin: str) -> str:
    """Normalize origin to scheme://host[:port] with lowercase host and default port stripped."""
    parts = urlsplit(url_or_origin)
    scheme = parts.scheme.lower() if parts.scheme else "https"
    hostname = (parts.hostname or "").lower().rstrip(".")
    port = parts.port
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        port = None
    netloc = f"{hostname}:{port}" if port is not None else hostname
    return f"{scheme}://{netloc}"


def canonicalize_url(url: str) -> str:
    """Canonicalize URL by normalizing origin, collapsing redundant slashes, and sorting query params."""
    parts = urlsplit(url)
    origin = normalize_origin(url)
    origin_parts = urlsplit(origin)
    path = parts.path
    if not path:
        path = "/"
    else:
        # Collapse multiple slashes
        while "//" in path:
            path = path.replace("//", "/")
    # Deterministic query params sort
    if parts.query:
        query_pairs = sorted(parse_qsl(parts.query, keep_blank_values=True))
        query = urlencode(query_pairs)
    else:
        query = ""
    return urlunsplit((origin_parts.scheme, origin_parts.netloc, path, query, ""))


def compute_fetch_effect_key(url: str, approved_origin: str, policy_epoch: int = 1) -> str:
    """Deterministic hash of policy epoch, normalized origin, and canonical URL."""
    payload = f"epoch={policy_epoch}|origin={normalize_origin(approved_origin)}|url={canonicalize_url(url)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    max_hops: int = 5
    policy_epoch: int = 1


def check_claim(request, fetch, store, log, clock):
    """fetch(url) -> (final_url, bytes) or (final_url, body, hop_chain).

    Returns the conclusion dict and records it if decided.
    """
    parts = urlsplit(request.url)
    if parts.scheme.lower() != "https":
        return {"conclusion": "BLOCKED", "reason": f"scheme {parts.scheme!r} is not https"}

    norm_origin = normalize_origin(request.url)
    approved_origin = normalize_origin(request.approved_origin)
    if norm_origin != approved_origin:
        return {"conclusion": "BLOCKED", "reason": f"{norm_origin} is not the approved origin"}

    fetch_res = fetch(request.url)
    if len(fetch_res) >= 3:
        final_url, body, raw_hops = fetch_res[0], fetch_res[1], list(fetch_res[2])
    else:
        final_url, body = fetch_res[0], fetch_res[1]
        raw_hops = [request.url, final_url] if final_url != request.url else [request.url]

    # Hop chain validation & loop detection
    seen_hops = set()
    for hop in raw_hops:
        canon_hop = canonicalize_url(hop)
        if canon_hop in seen_hops:
            return {"conclusion": "BLOCKED", "reason": f"redirect loop detected at {hop}", "hops": raw_hops}
        seen_hops.add(canon_hop)

        hop_parts = urlsplit(hop)
        if hop_parts.scheme.lower() != "https":
            return {"conclusion": "BLOCKED", "reason": f"redirect hop {hop} used insecure scheme", "hops": raw_hops}
        if normalize_origin(hop) != approved_origin:
            return {"conclusion": "BLOCKED", "reason": f"redirect hop {hop} left the approved origin", "hops": raw_hops}

    if len(raw_hops) > request.max_hops:
        return {
            "conclusion": "BLOCKED",
            "reason": f"redirect hop limit exceeded: {len(raw_hops)} > {request.max_hops}",
            "hops": raw_hops,
        }

    final_norm = normalize_origin(final_url)
    if final_norm != approved_origin:
        return {"conclusion": "BLOCKED", "reason": "redirect left the approved origin", "hops": raw_hops}

    digest = store.put(body)
    text = store.get(digest).decode("utf-8", errors="replace")
    at = text.find(request.quote)
    conclusion = "SUPPORTED" if at >= 0 else "CONTRADICTED"
    effect_key = compute_fetch_effect_key(request.url, request.approved_origin, request.policy_epoch)
    anchor = {
        "sha256": digest,
        "url": final_url,
        "canonical_url": canonicalize_url(final_url),
        "offset": at if at >= 0 else None,
        "length": len(request.quote),
        "hops": raw_hops,
        "effect_key": effect_key,
        "policy_epoch": request.policy_epoch,
    }
    log.append(AcceptedFact(
        request.workkey,
        0,
        f"{conclusion}: {request.quote!r} at {final_url}",
        (f"content:{digest}", f"effect:{effect_key}"),
        "controller",
        clock(),
    ))
    return {"conclusion": conclusion, "anchor": anchor}
