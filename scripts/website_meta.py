"""Factual title and Open Graph checks for the public website pages.

The pages under website/src/*.html are the source. website/public is the
build copy. An animation fragment under assets/ is not a page.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


# Claims the current homepage used as a title or description while the page
# itself says the long-range vision is not an offer.
UNFACTUAL_MARKERS = (
    "Nachweisbare Kontinuität",
    "jedes Ergebnis mit prüfbarem Beleg",
    "revolution",
    "garantiert fehlerfrei",
    "Stop Copy-Pasting",
    "Living Agent",
    "Command Center",
)

PAGE_GLOB = "*.html"


class CatalogError(ValueError):
    """A page does not meet the factual title and Open Graph contract."""


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self._in_title = False
        self.description = ""
        self.og: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
            return
        if tag != "meta":
            return
        data = {key: value or "" for key, value in attrs}
        name = data.get("name", "").lower()
        prop = data.get("property", "").lower()
        content = data.get("content", "")
        if name == "description" and not self.description:
            self.description = content
        if prop.startswith("og:"):
            self.og.setdefault(prop, content)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def parse_meta(html: str) -> dict[str, str]:
    parser = _MetaParser()
    parser.feed(html)
    parser.close()
    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
    return {
        "title": title,
        "description": parser.description.strip(),
        "og:title": parser.og.get("og:title", "").strip(),
        "og:description": parser.og.get("og:description", "").strip(),
        "og:type": parser.og.get("og:type", "").strip(),
        "og:locale": parser.og.get("og:locale", "").strip(),
    }


def check_page(html: str) -> list[str]:
    """Return failure reasons. An empty list means the page matches the contract."""
    meta = parse_meta(html)
    failures: list[str] = []
    title = meta["title"]
    description = meta["description"]
    if not title:
        failures.append("missing title")
    if not description:
        failures.append("missing description")
    for marker in UNFACTUAL_MARKERS:
        if marker in title or marker in description:
            failures.append(f"unfactual marker {marker!r}")
    if meta["og:title"] != title:
        failures.append("og:title differs from title")
    if meta["og:description"] != description:
        failures.append("og:description differs from description")
    if meta["og:type"] != "website":
        failures.append("og:type is not website")
    if meta["og:locale"] != "de_DE":
        failures.append("og:locale is not de_DE")
    return failures


def check_tree(src: Path, *, strict: bool = False) -> dict:
    """Check every top-level HTML page. strict=True raises on the first tree failure."""
    src = Path(src)
    pages = sorted(path for path in src.glob(PAGE_GLOB) if path.is_file())
    failures: list[dict[str, str]] = []
    if not pages:
        failures.append({"page": "", "reason": "no html pages"})
    for page in pages:
        reasons = check_page(page.read_text(encoding="utf-8"))
        for reason in reasons:
            failures.append({"page": page.name, "reason": reason})
    report = {"ok": not failures, "failures": failures, "pages": [path.name for path in pages]}
    if strict and failures:
        raise CatalogError("; ".join(f"{item['page'] or '-'}: {item['reason']}" for item in failures))
    return report
