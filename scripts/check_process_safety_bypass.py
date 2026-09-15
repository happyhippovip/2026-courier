"""Reject unreviewed production process-creation bypasses."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ALLOWED_LEGACY_CALLS = {
    "launch_visual_studio.py": {43},
    "render_godot_movie.py": {88, 97, 102},
    "run_codex_bridge.py": {247, 306},
    "run_context_sync.py": {96},
    "run_content_production_pipeline.py": {99, 111, 275},
    "run_chief_relay_cycle.py": {120, 288, 290, 291, 294},
    "run_snitch_watchdog.py": {862},
}
FORBIDDEN = {
    ("subprocess", "Popen"), ("subprocess", "run"), ("subprocess", "call"),
    ("subprocess", "check_call"), ("subprocess", "check_output"),
    ("asyncio", "create_subprocess_exec"), ("asyncio", "create_subprocess_shell"),
    ("os", "system"), ("os", "popen"),
}


def violations(root: Path) -> list[str]:
    found: list[str] = []
    for path in sorted((root / "scripts").glob("*.py")):
        if path.name in {"heavy_process_supervisor.py", "check_process_safety_bypass.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if isinstance(node.func.value, ast.Name) and (node.func.value.id, node.func.attr) in FORBIDDEN:
                if node.lineno not in ALLOWED_LEGACY_CALLS.get(path.name, set()):
                    found.append(f"{path.relative_to(root)}:{node.lineno}:{node.func.value.id}.{node.func.attr}")
    return found


def main() -> None:
    failures = violations(Path(__file__).resolve().parents[1])
    if failures:
        raise SystemExit("PROCESS_SAFETY_BYPASS:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
