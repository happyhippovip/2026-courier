#!/usr/bin/env python3
"""Build the static preview and fail closed on broken links or invented claims."""

from __future__ import annotations

import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
PAGES = ("index.html", "404.html", "impressum.html", "datenschutz.html", "agb.html", "widerruf.html")
IMAGES = (
    "01-talk-dashboard.jpg",
    "02-talk-variant.jpg",
    "03-autonomous-workflows.jpg",
    "04-choose-model.jpg",
    "05-community-collab.jpg",
    "06-multi-device.jpg",
    "07-project-base.jpg",
    "08-reality-check.jpg",
    "09-voice-lounge.jpg",
    "10-landing-play-smarter.jpg",
    "11-hero-infinity.jpg",
    "12-hero-platform.jpg",
    "13-verified-results.jpg",
    "14-live-constellation.jpg",
)
DOORS = ("Portal betreten", "Gruppe entdecken", "Taverne besuchen", "Geheimnis entdecken")
BANNED = (
    "Reality Check Avenue",
    "Courier Symphony LLC",
    "contact@couriersymphony.com",
    "buy.stripe.com",
    "500K",
    "4.9/5",
    "4,9/5",
    "12.46",
    "12,46",
    "12.4k",
    "12,4k",
    "99.7",
    "1.4M",
    "+12%",
    "hobbiejanssen",
    "SchülerVZ",
    "SchuelerVZ",
    "fehlerfrei",
    "Get Started Free",
    "vierzehn Tagen",
)


class Finder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.ids: set[str] = set()
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if tag == "a":
            self.hrefs.append(data.get("href", ""))
        if tag in {"img", "script", "link"} and data.get("src") or (tag == "link" and data.get("href")):
            if tag == "img":
                self.srcs.append(data.get("src", ""))
            elif tag == "script":
                self.srcs.append(data.get("src", ""))
            elif data.get("rel") == "stylesheet":
                self.srcs.append(data.get("href", ""))
        if data.get("id"):
            self.ids.add(data["id"])

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    subprocess.run(["sh", str(ROOT / "build_site.sh")], check=True, cwd=ROOT)
    if "COURIER_CONTACT_EMAIL" not in __import__("os").environ:
        for name in ("index.html", "site.css", "site.js"):
            src = (ROOT / "src" / name).read_text(encoding="utf-8")
            built = (PUBLIC / name).read_text(encoding="utf-8")
            if src != built:
                fail(f"source/public drift: {name}")

    for page in PAGES:
        if not (PUBLIC / page).is_file():
            fail(f"missing page {page}")
    for image in IMAGES:
        if not (PUBLIC / "media" / image).is_file():
            fail(f"missing image {image}")

    index = (PUBLIC / "index.html").read_text(encoding="utf-8")
    css = (PUBLIC / "site.css").read_text(encoding="utf-8")
    script = (PUBLIC / "site.js").read_text(encoding="utf-8")
    for door in DOORS:
        if door not in index:
            fail(f"missing door {door}")
    for needed in ("#portal", "#gruppe", "#taverne", "#geheimnis", "prefers-reduced-motion", "Illustrativ", "Bald verfügbar", "DEMO"):
        blob = index + css + script
        if needed not in blob:
            fail(f"missing {needed}")
    if "Courier Bird" not in index:
        fail("missing Courier Bird")
    if "id=\"nav-check\"" not in index:
        fail("missing mobile menu control")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC.rglob("*.html"))
    combined += "\n" + css + "\n" + script
    for banned in BANNED:
        if banned.lower() in combined.lower():
            fail(f"banned claim present: {banned}")
    if "website-v45-founder-refs" in combined:
        fail("founder reference screenshot was copied into the site")

    parser = Finder()
    parser.feed(index)
    for href in parser.hrefs:
        if href in {"", "#"}:
            fail(f"dead link {href!r}")
        if href.startswith("#"):
            anchor = href[1:]
            if anchor not in parser.ids:
                fail(f"missing anchor {href}")
            continue
        if href.startswith("http"):
            if href != "https://github.com/happyhippovip/2026-courier/issues":
                fail(f"unexpected external link {href}")
            continue
        target = (PUBLIC / href).resolve()
        if not target.is_file():
            fail(f"broken link {href}")
    for src in parser.srcs:
        if src.startswith("http"):
            fail(f"external asset {src}")
        if not (PUBLIC / src).is_file():
            fail(f"missing asset {src}")
    for image in IMAGES:
        if f"media/{image}" not in index:
            fail(f"image not used on the page: {image}")

    illustrative = len(re.findall(r"Illustrativ", index))
    if illustrative < 7:
        fail(f"expected illustrative labels on the group cards, found {illustrative}")
    print("website check ok")


if __name__ == "__main__":
    main()
