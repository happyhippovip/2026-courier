"""Catalog 2326-2350: precise image text, linked form labels, understandable errors.

Static files plus the pure pilot field check. No network and no spend.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
BIRD_TEXT = (
    "Dekorative Animation: ein Vogel trägt Umschläge zwischen Agenten. "
    "Keine Auftragsdaten und kein Status."
)
PILOT = ROOT / "pilot" / "index.html"
FORM_JS = ROOT / "pilot" / "pilot_form.js"
HOME = ROOT / "website" / "src" / "index.html"
BIRD = ROOT / "website" / "src" / "assets" / "bird" / "bird.html"
STUDIO = ROOT / "studio" / "index.html"


def _html(path):
    return path.read_text(encoding="utf-8")


def _label_targets(html):
    return set(re.findall(r"<label\b[^>]*\bfor=\"([^\"]+)\"", html))


def test_bird_description_names_the_scene_and_not_the_canvas():
    home = _html(HOME)
    iframe = re.search(r"<iframe\b[^>]*>", home)
    assert iframe, "hero iframe missing"
    tag = iframe.group(0)
    assert f'title="{BIRD_TEXT}"' in tag
    assert "aria-hidden" not in tag
    bird = _html(BIRD)
    assert BIRD_TEXT in bird
    canvases = re.findall(r"<canvas\b[^>]*>", bird)
    assert len(canvases) >= 2
    assert all("aria-hidden=\"true\"" in tag for tag in canvases)


def test_bird_description_is_the_same_after_a_second_read():
    assert _html(BIRD).count(BIRD_TEXT) == _html(BIRD).count(BIRD_TEXT) == 1


def test_pilot_inputs_have_matching_labels():
    html = _html(PILOT)
    targets = _label_targets(html)
    for field in ("goal-text", "ai-provider", "api-key"):
        assert field in targets
        assert f'id="{field}"' in html


def test_studio_directive_has_a_matching_label():
    html = _html(STUDIO)
    assert "human-idea-input" in _label_targets(html)
    assert 'id="human-idea-input"' in html


def test_pilot_field_errors_name_the_missing_fields(tmp_path):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = r"""
const target = process.argv[2] || process.argv[1];
const { missingPilotFields, pilotFieldError } = require(target);
function check(goal, key) {
  const missing = missingPilotFields(goal, key);
  return JSON.stringify({ ids: missing.map(m => m.id), text: pilotFieldError(missing) });
}
const cases = [
  ["", ""],
  ["  ", "secret"],
  ["ship the report", ""],
  ["ship the report", "secret"],
];
for (const [goal, key] of cases) console.log(check(goal, key));
"""
    runner = tmp_path / "runner.js"
    runner.write_text(script, encoding="utf-8")
    use_shell = sys.platform == "win32"
    out = subprocess.run(
        ["node", str(runner), str(FORM_JS)],
        check=True, capture_output=True, text=True, shell=use_shell,
    )
    lines = out.stdout.splitlines()
    assert "goal-text" in lines[0] and "api-key" in lines[0]
    assert "what you want to do" in lines[0] and "connection API key" in lines[0]
    assert "goal-text" in lines[1] and "api-key" not in lines[1]
    assert "api-key" in lines[2] and "goal-text" not in lines[2]
    assert lines[3] == '{"ids":[],"text":""}'
    again = subprocess.run(
        ["node", str(runner), str(FORM_JS)],
        check=True, capture_output=True, text=True, shell=use_shell,
    )
    assert again.stdout == out.stdout


def test_pilot_page_reports_errors_without_alert():
    html = _html(PILOT)
    assert "alert(" not in html
    assert 'id="setup-error"' in html
    assert 'role="alert"' in html
    assert "aria-invalid" in html
    assert "pilotFieldError" in html
    assert "missingPilotFields" in html
