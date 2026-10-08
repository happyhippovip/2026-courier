from scripts.notice_draft import draft, pick

BASE = {"sha": "a" * 40}


def finding(rule, severity, area, where="x.py:1"):
    return {"rule": rule, "severity": severity, "area": area, "where": where, "detail": "d"}


def test_picks_most_severe_then_fastest_area():
    fs = [finding("timeout", "medium", "workflows"), finding("curl_pipe_shell", "high", "supply"),
          finding("action_pinned_by_tag", "low", "supply")]
    assert pick(fs)["rule"] == "curl_pipe_shell"
    assert pick([finding("action_pinned_by_tag", "low", "supply")]) is None


def test_notice_is_calm_free_and_only_waits_for_a_human():
    text, problems = draft({**BASE, "findings": [finding("curl_pipe_shell", "high", "supply", "ci.yml:7")]})
    assert "ci.yml:7" in text and "€" not in text and "aaaaaaaaaaaa" in text
    assert problems == ["needs a human approval id before sending"]


def test_secret_notice_names_place_never_value():
    text, problems = draft({**BASE, "findings": [finding("github_token", "high", "secrets", "config.py:3")]})
    assert "config.py:3" in text and "will not share it" in text
    assert problems == ["needs a human approval id before sending"]


def test_secret_value_never_reaches_draft_even_if_report_carries_it():
    fake = "ghp_" + "A" * 36
    secret_finding = finding("github_token", "high", "secrets", "config.py:3")
    secret_finding.update({"detail": "matched value " + fake, "value": fake,
                           "secret": fake, "match": fake})
    text, _ = draft({**BASE, "findings": [secret_finding]})
    assert fake not in text
