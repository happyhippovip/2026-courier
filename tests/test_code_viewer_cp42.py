"""Tests for CP-42 / CQ-42 / GB-CODE-VIEWER-01: Code Viewer Sanitizer & Byte-Accurate Clipboard.

Verifies:
1. Zero execution of result code & neutralization of HTML/script injection ("Kein Ausführen von Ergebniscode").
2. Byte-accurate copy buffer preserving whitespace, tabs, and newlines ("Copy bleibt bytegetreu für angezeigten Inhalt").
3. Multi-file rendering with individual discrete blocks.
4. Local focus boundary ensuring global Muse/terminal shortcuts remain untouched ("globale Muse-/Terminal-Tasten unverändert").
5. Evidence generation containing ['renderer', 'code-fixtures', 'clipboard-actions'].
"""

import hashlib
import pytest

from courier_core.code_viewer_sanitizer import (
    CodeViewerSanitizer,
    KeyboardScopeAction,
    RenderedCodeBlock,
)


def test_xss_injection_neutralized_in_display_html():
    """Script tags and hostile event handlers are safely HTML escaped in display, preventing code execution."""
    sanitizer = CodeViewerSanitizer()

    malicious_code = (
        'def test():\n'
        '    # <script>alert("pwned")</script>\n'
        '    x = "<img src=x onerror=alert(1)>"\n'
        '    return x'
    )

    block = sanitizer.render_file("src/exploit_demo.py", malicious_code)

    assert "<script>" not in block.safe_display_html.lower()
    assert "&lt;script&gt;" in block.safe_display_html
    assert "&lt;img" in block.safe_display_html
    assert block.raw_content == malicious_code


def test_raw_copy_is_byte_accurate_preserving_whitespace_and_tabs():
    """Copying code produces byte-for-byte exact unescaped content, matching SHA256 digest."""
    sanitizer = CodeViewerSanitizer()

    indented_source = (
        "\tdef compute(a, b):\n"
        "        # Four spaces & tabs mixed\n"
        "\t\tif a > 0 and b < 100:\n"
        "            return a & b\n"
        "    return None\r\n"
    )

    block = sanitizer.render_file("lib/math_utils.py", indented_source)
    copied = sanitizer.copy_code_content(block)

    # Byte-level equality and SHA-256 match
    assert copied == indented_source
    assert hashlib.sha256(copied.encode("utf-8")).hexdigest() == block.content_sha256
    assert "&amp;" not in copied  # No entity encoding in clipboard


def test_multi_file_bundle_rendering():
    """Multiple files in a result bundle render distinct blocks with correct metadata."""
    sanitizer = CodeViewerSanitizer()

    bundle = {
        "services/auth.py": "class AuthService:\n    pass\n",
        "services/db.py": "def get_conn():\n    return None\n",
    }

    blocks = sanitizer.render_bundle(bundle)
    assert len(blocks) == 2
    assert blocks[0].file_path == "services/auth.py"
    assert blocks[1].file_path == "services/db.py"
    assert blocks[0].line_count == 2
    assert blocks[1].line_count == 2


def test_unfocused_keyboard_shortcuts_pass_to_global_muse_terminal():
    """When code viewer is not focused, keyboard shortcuts are never hijacked and pass to global terminal."""
    sanitizer = CodeViewerSanitizer()

    # Out of focus tests
    for key in ("CTRL+C", "CTRL+A", "CTRL+V", "COMMAND+C"):
        event = sanitizer.handle_keyboard_event(key, has_local_focus=False)
        assert event["handled"] is False
        assert event["action"] == KeyboardScopeAction.PASS_TO_GLOBAL.value


def test_focused_keyboard_shortcuts_handled_locally():
    """When code viewer has focus, copy and select-all operate locally without polluting host."""
    sanitizer = CodeViewerSanitizer()

    copy_event = sanitizer.handle_keyboard_event("CTRL+C", has_local_focus=True)
    assert copy_event["handled"] is True
    assert copy_event["action"] == KeyboardScopeAction.LOCAL_COPY.value

    select_event = sanitizer.handle_keyboard_event("CTRL+A", has_local_focus=True)
    assert select_event["handled"] is True
    assert select_event["action"] == KeyboardScopeAction.LOCAL_SELECT_ALL.value


def test_evidence_generation():
    """Validates required catalog evidence keys: ['renderer', 'code-fixtures', 'clipboard-actions']."""
    sanitizer = CodeViewerSanitizer()
    block = sanitizer.render_file("main.py", "print('hello')\n")
    sanitizer.copy_code_content(block)

    evidence = sanitizer.generate_code_viewer_evidence()

    assert "renderer" in evidence
    assert "code-fixtures" in evidence
    assert "clipboard-actions" in evidence

    assert evidence["renderer"]["total_rendered_blocks"] == 1
    assert evidence["renderer"]["script_tag_leakage_detected"] is False
    assert "main.py" in evidence["code-fixtures"]
    assert len(evidence["clipboard-actions"]) == 1
    assert evidence["clipboard-actions"][0]["file_path"] == "main.py"
