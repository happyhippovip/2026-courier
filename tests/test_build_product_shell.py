import os
from pathlib import Path
from unittest.mock import patch

from scripts.build_product_shell import (
    build_product_shell,
    declaration_has_authoritative_j1_unlock,
    skeleton_report_lines,
)


def _repo_at(tmp_path):
    return patch(
        "scripts.build_product_shell.Path.resolve",
        return_value=tmp_path / "scripts" / "build_product_shell.py",
    )


def _write_declaration(tmp_path, text):
    gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
    gate_file.parent.mkdir(parents=True, exist_ok=True)
    gate_file.write_text(text, encoding="utf-8")
    return gate_file


def test_gate_locked_file_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with _repo_at(tmp_path):
        assert build_product_shell() != 0


def test_gate_locked_file_present_no_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with _repo_at(tmp_path):
        _write_declaration(tmp_path, "Some other content without the flag")
        assert build_product_shell() != 0


def test_stuffed_yes_without_j1_stays_locked(tmp_path, monkeypatch, capsys):
    """Unstructured, negated, or stuffed YES is not J-1 proof and stays LOCKED.

    This is the fail-open regression: a YES token anywhere in the declaration
    used to unlock. Missing pilot, freeze, and owner evidence must not.
    """
    monkeypatch.chdir(tmp_path)
    fixtures = (
        "Stuff... PRODUCT_SHELL_UNLOCKED=YES ... stuff",
        "Do not treat PRODUCT_SHELL_UNLOCKED=YES as authorized.",
        "PRODUCT_SHELL_UNLOCKED=YES is absent; the token above is a quote in prose.",
        "PRODUCT_SHELL_UNLOCKED: YES\n",
        "PRODUCT_SHELL_UNLOCKED=YES\n",
        "- **PRODUCT_SHELL_UNLOCKED**: `YES` (declaration field without J-1 proof)\n",
        (
            "PRODUCT_SHELL_UNLOCKED=YES\n"
            "GREEN signal: yes\n"
            "core freeze: yes\n"
            "cohort: alpha\n"
            "human unlock: owner\n"
        ),
    )

    for text in fixtures:
        _write_declaration(tmp_path, text)
        with _repo_at(tmp_path):
            code = build_product_shell()
        captured = capsys.readouterr()
        assert code != 0, text
        assert "(READY)" not in captured.out
        assert "BUILD GATE LOCKED" in captured.out


def test_undecodable_declaration_stays_locked(tmp_path, monkeypatch):
    """The live declaration is not UTF-8. A decode failure must stay LOCKED."""
    monkeypatch.chdir(tmp_path)
    gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
    gate_file.parent.mkdir(parents=True, exist_ok=True)
    gate_file.write_bytes(
        b"Status: notes \x97 PRODUCT_SHELL_UNLOCKED=YES stuffed in a cp1252 file\n"
    )

    with _repo_at(tmp_path):
        assert build_product_shell() != 0


def test_yes_token_is_not_authoritative_j1_proof():
    samples = (
        "",
        "PRODUCT_SHELL_UNLOCKED=YES",
        "PRODUCT_SHELL_UNLOCKED: YES",
        "- **PRODUCT_SHELL_UNLOCKED**: `YES`",
        "not PRODUCT_SHELL_UNLOCKED=YES",
        "GREEN signal yes\ncore freeze yes\ncohort alpha\nhuman unlock owner\n",
    )
    for sample in samples:
        assert declaration_has_authoritative_j1_unlock(sample) is False


def test_skeleton_listing_is_not_installer_ready():
    text = "\n".join(skeleton_report_lines())
    assert "PREP/SKELETON" in text
    assert "READY" not in text
    assert "No installer was produced" in text
    assert "Product shell remains unbuilt" in text


def test_real_declaration_is_not_set_to_yes():
    repo_root = Path(__file__).resolve().parents[1]
    declaration = repo_root / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
    raw = declaration.read_bytes()
    assert b"PRODUCT_SHELL_UNLOCKED=YES" not in raw
    assert b"PRODUCT_SHELL_UNLOCKED: YES" not in raw
    text = raw.decode("cp1252")
    assert "**PRODUCT_SHELL_UNLOCKED**: `NO`" in text


def test_main_stuffed_yes_stays_locked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("sys.argv", ["build_product_shell.py"]):
        with patch("pathlib.Path.resolve") as mock_resolve:
            mock_resolve.return_value = tmp_path / "scripts" / "build_product_shell.py"

            gate_file = tmp_path / "ops" / "ai" / "PILOT_READINESS_DECLARATION.md"
            gate_file.parent.mkdir(parents=True, exist_ok=True)
            gate_file.write_text(
                "Stuff... PRODUCT_SHELL_UNLOCKED=YES ... stuff",
                encoding="utf-8",
            )

            import runpy

            script = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "scripts",
                "build_product_shell.py",
            )
            try:
                runpy.run_path(script, run_name="__main__")
            except SystemExit as exc:
                assert exc.code not in (0, None)
            else:
                raise AssertionError("expected SystemExit from a locked gate")
