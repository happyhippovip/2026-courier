"""Catalog 2301-2325: keyboard, contrast, and the hero description.

The pilot pages live in website/src and are copied to website/public.
These checks read that HTML. They do not open a browser or a network connection.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "website" / "src"
PUBLIC = ROOT / "website" / "public"
CHROME = (
    "index.html",
    "agb.html",
    "widerruf.html",
    "datenschutz.html",
    "impressum.html",
    "404.html",
)
FIXED_NAV = ("index.html",)
HERO_SENTENCE = "Ein Vogel trägt einen Auftrag vom Dispatcher zu einem Empfänger"
BIRD_TEXT = "Dekorative Animation: ein Vogel trägt Umschläge zwischen Agenten. Keine Auftragsdaten und kein Status."


def _lin(channel):
    value = channel / 255
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _luminance(color):
    hex_color = color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(channel * 2 for channel in hex_color)
    red = int(hex_color[0:2], 16)
    green = int(hex_color[2:4], 16)
    blue = int(hex_color[4:6], 16)
    return 0.2126 * _lin(red) + 0.7152 * _lin(green) + 0.0722 * _lin(blue)


def contrast(foreground, background):
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _nav_worst_case_background(page):
    """Composite the nav paint over white, the brightest hero pixel."""
    match = re.search(r"nav\{[^}]*background:\s*([^;}]+)", page)
    if not match:
        match = re.search(r":root\{[^}]*--bg-color:\s*([^;}]+)", page)
        if match:
            return match.group(1).strip()
    assert match, "nav background missing"
    paint = match.group(1).strip()
    solid = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", paint)
    if solid:
        return paint
    rgba = re.fullmatch(
        r"rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*(0?\.\d+|1(?:\.0+)?)\s*\)",
        paint,
    )
    if rgba:
        alpha = float(rgba.group(1))
        channel = round(255 * (1 - alpha))
        return f"#{channel:02x}{channel:02x}{channel:02x}"
    return "#000000"


def test_skip_link_is_first_and_focus_is_visible():
    for name in CHROME:
        for tree in (SRC, PUBLIC):
            page = (tree / name).read_text(encoding="utf-8")
            body = page.split("<body>", 1)[1]
            first = body.find("href=")
            assert first != -1, f"no href in {name}"
            assert body[first:first + len('href="#inhalt"')] == 'href="#inhalt"', f"skip link not first in {name}"
            assert 'id="inhalt"' in page, f"id inhalt missing in {name}"
            assert ":focus-visible" in page, f"focus-visible missing in {name}"


def test_fixed_nav_anchors_clear_the_bar():
    for name in FIXED_NAV:
        for tree in (SRC, PUBLIC):
            page = (tree / name).read_text(encoding="utf-8")
            assert "scroll-margin-top" in page


def test_nav_muted_text_keeps_contrast_over_a_bright_hero():
    for name in FIXED_NAV:
        for tree in (SRC, PUBLIC):
            page = (tree / name).read_text(encoding="utf-8")
            muted_match = re.search(r"--mut:\s*(#[0-9a-fA-F]{6})", page) or re.search(r"--text-muted:\s*(#[0-9a-fA-F]{6})", page)
            assert muted_match, "muted color missing"
            muted = muted_match.group(1)
            surface = _nav_worst_case_background(page)
            assert contrast(muted, surface) >= 4.5


def test_error_page_footer_text_meets_contrast():
    for tree in (SRC, PUBLIC):
        page = (tree / "404.html").read_text(encoding="utf-8")
        footer = re.search(r"<footer[^>]*color:\s*(#[0-9a-fA-F]{6})", page).group(1)
        assert contrast(footer, "#ffffff") >= 4.5


def test_hero_description_is_precise_and_stays_out_of_tab_order():
    for tree in (SRC, PUBLIC):
        page = (tree / "index.html").read_text(encoding="utf-8")
        iframe = re.search(r"<iframe\b[^>]*>", page).group(0)
        assert 'tabindex="-1"' in iframe
        assert "aria-hidden" not in iframe
        assert (HERO_SENTENCE in iframe or BIRD_TEXT in iframe)
        bird = (tree / "assets" / "bird" / "bird.html").read_text(encoding="utf-8")
        assert (f'aria-label="{HERO_SENTENCE}' in bird or BIRD_TEXT in bird)
