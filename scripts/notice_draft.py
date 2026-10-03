#!/usr/bin/env python3
"""First-contact notice from a Repo Reality Check report.

Picks the single most useful finding, writes a calm, specific, free notice
(no price, no pitch, never a secret value) for the project's own security
contact, and runs it through courier_runtime.legal_guard. Nothing is sent:
the output is a draft a human reviews, approves and sends.

Usage: python scripts/notice_draft.py <report.json>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from courier_runtime.legal_guard import check_outward  # noqa: E402
from scripts.repo_reality_check import GUIDE  # noqa: E402

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
# what a maintainer can act on fastest, per area, when severities tie
AREA_RANK = {"secrets": 0, "supply": 1, "safety": 2, "hygiene": 3, "workflows": 4}
SECRET_RULES = {"github_token", "aws_access_key", "private_key_block", "slack_token", "openai_style_key"}


def pick(findings):
    useful = [f for f in findings if f["severity"] != "low"]
    if not useful:
        return None
    return min(useful, key=lambda f: (SEVERITY_RANK[f["severity"]], AREA_RANK.get(f["area"], 9)))


def draft(report):
    finding = pick(report["findings"])
    if finding is None:
        return None, []
    is_secret = finding["rule"] in SECRET_RULES
    meaning, fix, _ = GUIDE.get(finding["rule"], ("", "", ""))
    what = (f"what looks like a {finding['rule'].replace('_', ' ')} in {finding['where']} "
            "(I have not used it and will not share it)" if is_secret
            else f"{(meaning[0].lower() + meaning[1:]).rstrip('.') if meaning else finding['rule']} "
                 f"({finding['where']}).")
    text = (f"Hi,\n\nwhile reading your public repository at commit {report.get('sha', '?')[:12]} I noticed {what}\n\n"
            f"{fix}\n\nI am reporting this privately so it can be fixed quietly. Happy to explain if useful.\n")
    return text, check_outward(text, "security_contact", finding_is_secret=is_secret)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    text, problems = draft(json.loads(Path(argv[0]).read_text(encoding="utf-8")))
    if text is None:
        print("nothing worth a notice (only low findings)")
        return 0
    print(text)
    print("legal guard:", "; ".join(problems) if problems else "no known problem")
    return 0


if __name__ == "__main__":
    sys.exit(main())
