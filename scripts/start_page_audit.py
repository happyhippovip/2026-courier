"""Audit the public start page. Pure, no network.

verified is true only when the HTML is a page, states no placeholder and no
test checkout, keeps every nav link reachable on a narrow viewport, and does
not clip the hero. Codes are the evidence. The raw HTML is not copied out.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_KNOWN = frozenset({
    "PLACEHOLDER_PROMISE",
    "TEST_CHECKOUT",
    "MOBILE_LINK_HIDDEN",
    "MOBILE_MENU_MISSING",
    "FIRST_SCREEN_CLIPPED",
    "VISION_UNMARKED",
    "NOT_HTML",
})

_PLACEHOLDER = re.compile(r"\[(?:PLATZHALTER|LÖSCHFRIST)[^\]]*\]", re.IGNORECASE)
_TEST_CHECKOUT = re.compile(r"stripe\.com/test|buy\.stripe\.com/test_|/test_beta\b", re.IGNORECASE)
_HIDDEN_OPT = re.compile(r"a\.opt\s*\{[^}]*display\s*:\s*none", re.IGNORECASE)
_MEDIA = re.compile(r"@media\s*\(\s*max-width\s*:\s*720px\s*\)\s*\{", re.IGNORECASE)
_HERO_RULE = re.compile(r"\.hero\s*\{([^}]*)\}", re.IGNORECASE)
_VISION_LINK = re.compile(
    r"<a\b[^>]*href=[\"'](?:index\.html)?#vision[\"'][^>]*>",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Verdict:
    codes: frozenset[str]
    verified: bool

    def to_record(self) -> dict:
        return {"codes": sorted(self.codes), "verified": self.verified is True}

    def to_json(self) -> str:
        return json.dumps(self.to_record(), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Verdict":
        try:
            data = json.loads(text)
            raw = data["codes"]
            if not isinstance(raw, list) or any(item not in _KNOWN for item in raw):
                return _unknown()
            codes = frozenset(raw)
            verified = data.get("verified") is True and len(codes) == 0
            return cls(codes, verified)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _unknown()


def _unknown() -> Verdict:
    return Verdict(frozenset({"NOT_HTML"}), False)


def _block_after(match: re.Match[str], text: str) -> str:
    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    return text[start:index - 1] if depth == 0 else ""


def _mobile_css(html: str) -> str:
    match = _MEDIA.search(html)
    if match is None:
        return ""
    return _block_after(match, html)


def _hero_declares(block: str, *needles: str) -> bool:
    for rule in _HERO_RULE.finditer(block):
        body = rule.group(1).lower().replace(" ", "")
        if all(needle.replace(" ", "") in body for needle in needles):
            return True
    return False


def audit_page(html: object, require_hero: bool = True) -> Verdict:
    """Return a fail-closed verdict. Never raises."""
    try:
        if not isinstance(html, str) or "<html" not in html.lower():
            return _unknown()
        codes: set[str] = set()
        if _PLACEHOLDER.search(html):
            codes.add("PLACEHOLDER_PROMISE")
        if _TEST_CHECKOUT.search(html):
            codes.add("TEST_CHECKOUT")
        if _HIDDEN_OPT.search(html):
            codes.add("MOBILE_LINK_HIDDEN")
        if "<nav" in html.lower():
            mobile = _mobile_css(html)
            has_toggle = 'id="nav-toggle"' in html and "nav-toggle-label" in html
            opens = ".nav-toggle:checked" in mobile.replace(" ", "") and "~.links" in mobile.replace(" ", "")
            if not (has_toggle and opens):
                codes.add("MOBILE_MENU_MISSING")
            for link in _VISION_LINK.finditer(html):
                if re.search(r"\bclass\s*=\s*[\"'][^\"']*\bopt\b", link.group(0), re.IGNORECASE):
                    codes.add("MOBILE_LINK_HIDDEN")
        if require_hero or 'class="hero"' in html:
            mobile = _mobile_css(html)
            if not _hero_declares(mobile, "overflow:visible", "align-items:flex-start"):
                codes.add("FIRST_SCREEN_CLIPPED")
            if 'class="hero"' in html and ("<h1" not in html.lower() or 'href="#angebote"' not in html):
                codes.add("FIRST_SCREEN_CLIPPED")
        if 'id="vision"' in html and "kein Leistungsversprechen" not in html:
            codes.add("VISION_UNMARKED")
        return Verdict(frozenset(codes), len(codes) == 0)
    except Exception:
        return _unknown()
