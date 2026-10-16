"""Product pages stay separate from a registrar parking document."""

from pathlib import Path

import pytest

from scripts.domain_parking import PARKING_TITLE, ParkingError, check_product_pages, is_parking_document


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "website" / "src"


def test_parking_marker_is_not_a_product_page(tmp_path):
    assert is_parking_document(f"<html><title>{PARKING_TITLE}</title></html>") is True
    assert is_parking_document("<html><title>Courier Symphony</title></html>") is False
    parked = tmp_path / "index.html"
    parked.write_text(f"<title>{PARKING_TITLE}</title>", encoding="utf-8")
    report = check_product_pages(tmp_path)
    assert report["ok"] is False
    assert report["failures"] == ["index.html"]
    with pytest.raises(ParkingError):
        check_product_pages(tmp_path, strict=True)


def test_shipped_pages_are_not_the_parking_document():
    report = check_product_pages(SRC)
    assert report["ok"] is True, report
    assert "index.html" in report["pages"]
    assert check_product_pages(SRC) == report
    public = check_product_pages(ROOT / "website" / "public")
    assert public["ok"] is True
    assert public["pages"] == report["pages"]
