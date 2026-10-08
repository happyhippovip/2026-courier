import os
import pytest
from pathlib import Path

from scripts.spreadsheet_cleanup_sample import main
from courier_runtime.workbook import read_cells


def test_spreadsheet_cleanup_sample_execution(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    # Run the cleanup sample
    main()

    out, err = capsys.readouterr()
    assert "Planned changes: 8 cells need cleanup." in out
    assert "Applying changes via courier_runtime.workbook..." in out
    assert "Receipt:" in out
    assert "untouched_cells_verified" in out
    assert "Done!" in out

    # Verify messy_sample.xlsx was cleaned up at the end of the script
    assert not (tmp_path / "messy_sample.xlsx").exists()
