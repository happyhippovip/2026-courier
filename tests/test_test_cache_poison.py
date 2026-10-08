import runpy
from pathlib import Path
import scripts.poison_test as poison_test


def test_poison_test_get_state():
    assert poison_test.get_state() == "V2_STATE"


def test_test_cache_poison_capsys(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    script_path = Path(__file__).parent.parent / "scripts" / "test_cache_poison.py"

    runpy.run_path(str(script_path))
    captured = capsys.readouterr()
    assert "Resulting State: V2_STATE" in captured.out
    assert (tmp_path / "poison_test.py").exists()
