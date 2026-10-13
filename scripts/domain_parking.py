"""Keep a registrar parking page out of the product website.

The live host can still be a parked domain. That cutover is not this module.
This check only refuses to treat a parking document as a product page.
"""

from __future__ import annotations

from pathlib import Path


# Marker observed on the STRATO placeholder. The rest of that page is not copied.
PARKING_TITLE = "STRATO - Domain reserved"


class ParkingError(ValueError):
    """A product page is a domain-parking document."""


def is_parking_document(html: str) -> bool:
    return PARKING_TITLE in html


def check_product_pages(src: Path, *, strict: bool = False) -> dict:
    """Every top-level HTML page must be a product page, not a parking document."""
    src = Path(src)
    pages = sorted(path.name for path in src.glob("*.html") if path.is_file())
    failures = [name for name in pages if is_parking_document((src / name).read_text(encoding="utf-8"))]
    if not pages:
        failures = ["<none>"]
    report = {"ok": bool(pages) and not failures, "failures": failures, "pages": pages}
    if strict and not report["ok"]:
        raise ParkingError("parking document in product pages: " + ", ".join(failures))
    return report
