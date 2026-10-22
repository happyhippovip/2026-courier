"""Controller boot must not create a journal through a symlinked home."""

import pytest

from courier_core.controller import Controller
from courier_core.journal import JournalError


def test_boot_refuses_a_symlinked_home(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "home"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(JournalError, match="symlink"):
        Controller(link).boot()
    assert list(outside.iterdir()) == []
