"""The one plain-language sentence of what a customer receives."""

from __future__ import annotations

import re
from pathlib import Path


ELEMENT_ID = "kundennutzen"
BANNED = ("Journal", "Checkpoint", "Verifier", "Workkey", "Lane", "Prompt", "Append-only")
REQUIRED = ("Prüfbericht", "festen Preis")


class BenefitError(ValueError):
    """The customer-benefit sentence is missing or not plain."""


def benefit_text(html: str) -> str:
    match = re.search(
        rf'id="{ELEMENT_ID}"[^>]*>(.*?)</p>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    return re.sub(r"\s+", " ", text).strip()


def check_benefit(html: str) -> list[str]:
    text = benefit_text(html)
    failures: list[str] = []
    if not text:
        failures.append("missing kundennutzen")
        return failures
    if not (40 <= len(text) <= 220):
        failures.append("benefit length out of range")
    for word in REQUIRED:
        if word not in text:
            failures.append(f"missing {word}")
    for word in BANNED:
        if word.lower() in text.lower():
            failures.append(f"internal word {word}")
    return failures


def check_page(path: Path, *, strict: bool = False) -> dict:
    path = Path(path)
    if not path.is_file():
        report = {"ok": False, "failures": ["missing file"], "text": ""}
        if strict:
            raise BenefitError("missing file")
        return report
    html = path.read_text(encoding="utf-8")
    failures = check_benefit(html)
    report = {"ok": not failures, "failures": failures, "text": benefit_text(html)}
    if strict and failures:
        raise BenefitError("; ".join(failures))
    return report
