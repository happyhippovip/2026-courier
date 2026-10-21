"""Static contract for the Magic Composer goal surface."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "product" / "magic-composer"


def _read(name: str) -> str:
    return (PAGE / name).read_text(encoding="utf-8")


def test_goal_field_offers_the_example_and_the_send_path():
    html = _read("index.html")
    assert 'lang="de"' in html
    assert "Magic Composer" in html
    assert 'placeholder="Erstelle mir einen Bericht aus diesen Dateien."' in html
    assert "Auftrag prüfen" in html
    assert ">Absenden<" in html
    assert 'id="file-button"' in html
    assert 'id="voice-button"' in html
    assert ">Sprache<" in html
    assert html.index("Datei") < html.index('id="goal"')
    assert "Ausführung" in html
    assert "Berechtigung" in html
    assert "Task-ID" in html
    assert 'class="aurora"' in html
    assert 'id="task-id"' in html


def test_glass_edge_and_aurora_sit_with_a_generous_field():
    css = _read("composer.css")
    assert "backdrop-filter: blur(18px)" in css
    assert ".aurora" in css
    assert "bottom: -18px" in css
    assert "aurora-drift" in css
    assert "min-height: 148px" in css
    assert ".glass::after" in css
    assert "prefers-reduced-motion" in css


def test_composer_assigns_a_task_id_without_calling_the_network():
    script = _read("composer.mjs")
    assert "createTaskId" in script
    assert "fetch(" not in script
    assert "XMLHttpRequest" not in script
    assert "WebSocket" not in script
