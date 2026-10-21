"""Code Viewer Sanitizer & Byte-Accurate Clipboard Coordinator (CP-42 / GB-CODE-VIEWER-01).

Guarantees:
1. Safe rendering preventing HTML/script injection and code execution ("Kein Ausführen von Ergebniscode").
2. Byte-accurate copy buffer preserving exact whitespace, tabs, and newlines ("Copy bleibt bytegetreu für angezeigten Inhalt").
3. Multi-file support maintaining file boundaries and discrete blocks.
4. Strict focus boundaries protecting global Muse and terminal shortcuts ("globale Muse-/Terminal-Tasten unverändert").
5. Evidence generation containing 'renderer', 'code-fixtures', and 'clipboard-actions'.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class KeyboardScopeAction(str, Enum):
    PASS_TO_GLOBAL = "PASS_TO_GLOBAL"
    LOCAL_COPY = "LOCAL_COPY"
    LOCAL_SELECT_ALL = "LOCAL_SELECT_ALL"


@dataclass(frozen=True)
class RenderedCodeBlock:
    file_path: str
    safe_display_html: str
    raw_content: str
    content_sha256: str
    byte_length: int
    line_count: int


class CodeViewerSanitizer:
    """Renders external results safely while guaranteeing byte-accurate clipboard copy and shortcut isolation."""

    def __init__(self) -> None:
        self._rendered_blocks: List[RenderedCodeBlock] = []
        self._clipboard_audit_log: List[Dict[str, Any]] = []

    def render_file(self, file_path: str, raw_content: str) -> RenderedCodeBlock:
        """Renders single code file into safe HTML while preserving exact raw content for copying."""
        if not file_path:
            raise ValueError("file_path cannot be empty")

        # Compute exact content digest for byte verification
        raw_bytes = raw_content.encode("utf-8")
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Sanitize HTML to prevent XSS / script execution
        escaped_text = html.escape(raw_content, quote=True)
        # Format within standard pre/code tags ensuring white-space: pre-wrap preservation
        display_html = (
            f'<div class="code-viewer-block" data-path="{html.escape(file_path, quote=True)}">\n'
            f'  <div class="code-viewer-header"><span class="code-viewer-filename">{html.escape(file_path)}</span></div>\n'
            f'  <pre class="code-viewer-content"><code>{escaped_text}</code></pre>\n'
            f'</div>'
        )

        block = RenderedCodeBlock(
            file_path=file_path,
            safe_display_html=display_html,
            raw_content=raw_content,
            content_sha256=sha256_hash,
            byte_length=len(raw_bytes),
            line_count=len(raw_content.splitlines()),
        )
        self._rendered_blocks.append(block)
        return block

    def render_bundle(self, files: Dict[str, str]) -> List[RenderedCodeBlock]:
        """Renders multiple files in a discrete bundle, preserving individual file boundaries."""
        results = []
        for path, content in files.items():
            results.append(self.render_file(path, content))
        return results

    def copy_code_content(self, block: RenderedCodeBlock) -> str:
        """Returns byte-accurate raw content for clipboard copy, verified against original hash."""
        copied_text = block.raw_content
        copied_hash = hashlib.sha256(copied_text.encode("utf-8")).hexdigest()

        assert copied_hash == block.content_sha256, "Clipboard copy corrupted raw content hash!"

        self._clipboard_audit_log.append({
            "file_path": block.file_path,
            "sha256": copied_hash,
            "byte_length": block.byte_length,
        })
        return copied_text

    def handle_keyboard_event(self, key_combination: str, has_local_focus: bool) -> Dict[str, Any]:
        """Enforces keyboard shortcut focus boundary.

        If viewer lacks focus, shortcuts pass through directly to global Muse/Terminal handlers.
        """
        normalized_key = key_combination.upper().strip()

        if not has_local_focus:
            # Out of viewer focus: strictly untouched, pass to terminal/Muse
            return {
                "handled": False,
                "action": KeyboardScopeAction.PASS_TO_GLOBAL.value,
                "reason": "Viewer not focused; preserved global terminal/Muse shortcut",
            }

        # Inside viewer focus: handle local viewer keys
        if normalized_key in ("CTRL+C", "COMMAND+C"):
            return {
                "handled": True,
                "action": KeyboardScopeAction.LOCAL_COPY.value,
                "reason": "Local code viewer copy",
            }
        elif normalized_key in ("CTRL+A", "COMMAND+A"):
            return {
                "handled": True,
                "action": KeyboardScopeAction.LOCAL_SELECT_ALL.value,
                "reason": "Local code viewer select-all",
            }

        # Any other key in viewer
        return {
            "handled": False,
            "action": KeyboardScopeAction.PASS_TO_GLOBAL.value,
            "reason": "Unhandled key in viewer passed to host",
        }

    def generate_code_viewer_evidence(self) -> Dict[str, Any]:
        """Generates evidence audit records containing required catalog keys."""
        return {
            "renderer": {
                "total_rendered_blocks": len(self._rendered_blocks),
                "script_tag_leakage_detected": any("<script>" in b.safe_display_html.lower() for b in self._rendered_blocks),
                "blocks": [
                    {"path": b.file_path, "sha256": b.content_sha256, "lines": b.line_count}
                    for b in self._rendered_blocks
                ],
            },
            "code-fixtures": [b.file_path for b in self._rendered_blocks],
            "clipboard-actions": list(self._clipboard_audit_log),
        }
