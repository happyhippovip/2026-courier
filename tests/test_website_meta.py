"""Factual SEO titles and Open Graph tags for website/src pages."""

from pathlib import Path

import pytest

from scripts.website_meta import CatalogError, check_page, check_tree


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "website" / "src"
PUBLIC = ROOT / "website" / "public"

FACTUAL = """<!DOCTYPE html><html lang="de"><head>
<title>Impressum — Courier Symphony</title>
<meta name="description" content="Anbieterkennzeichnung von Courier Symphony.">
<meta property="og:title" content="Impressum — Courier Symphony">
<meta property="og:description" content="Anbieterkennzeichnung von Courier Symphony.">
<meta property="og:type" content="website">
<meta property="og:locale" content="de_DE">
</head><body></body></html>"""


def test_factual_page_passes_and_slogan_fails():
    assert check_page(FACTUAL) == []
    slogan = FACTUAL.replace(
        "<title>Impressum — Courier Symphony</title>",
        "<title>Nachweisbare Kontinuität für KI-Agenten</title>",
        1,
    )
    reasons = check_page(slogan)
    assert any("unfactual marker" in reason for reason in reasons)
    assert any("og:title differs" in reason for reason in reasons)
    missing = "<html><head><title>Nur Titel</title></head></html>"
    assert check_page(missing)
    with pytest.raises(CatalogError):
        check_tree(Path("/tmp/courier-website-meta-empty-does-not-exist"), strict=True)


def test_shipped_pages_are_factual_and_match_the_build():
    report = check_tree(SRC)
    assert report["ok"] is True, report["failures"]
    assert "index.html" in report["pages"]
    assert "bird.html" not in report["pages"]
    again = check_tree(SRC)
    assert again == report
    public = check_tree(PUBLIC)
    assert public["pages"] == report["pages"]
    assert public["ok"] is True, public["failures"]
