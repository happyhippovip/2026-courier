import json

from scripts.notice_draft import draft, main, pick

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


def _report(where):
    return {
        "sha": "b" * 40,
        "findings": [finding("curl_pipe_shell", "high", "supply", where)],
    }


def test_report_does_not_follow_a_symlink(tmp_path, capsys):
    outside = tmp_path / "outside-report.json"
    outside.write_text(json.dumps(_report("SECRET-NOTICE-PATH")), encoding="utf-8")
    linked = tmp_path / "linked-report.json"
    linked.symlink_to(outside)
    parent_real = tmp_path / "parent-real"
    parent_real.mkdir()
    nested = parent_real / "report.json"
    nested.write_text(json.dumps(_report("SECRET-PARENT-PATH")), encoding="utf-8")
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent_real)
    plain = tmp_path / "plain-report.json"
    plain.write_text(json.dumps(_report("PLAIN-NOTICE-PATH")), encoding="utf-8")

    code_link = main([str(linked)])
    out_link = capsys.readouterr().out
    code_parent = main([str(parent_link / "report.json")])
    out_parent = capsys.readouterr().out
    code_plain = main([str(plain)])
    out_plain = capsys.readouterr().out
    assert (
        code_link == 2 and "SECRET-NOTICE-PATH" not in out_link
        and code_parent == 2 and "SECRET-PARENT-PATH" not in out_parent
        and code_plain == 0 and "PLAIN-NOTICE-PATH" in out_plain
        and linked.is_symlink() and parent_link.is_symlink()
    ), (
        code_link, "SECRET-NOTICE-PATH" in out_link,
        code_parent, "SECRET-PARENT-PATH" in out_parent,
        code_plain, "PLAIN-NOTICE-PATH" in out_plain,
    )
