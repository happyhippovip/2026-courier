from scripts.run_bodyguards import BodyguardPoolManager


def _state(root, working):
    manager = BodyguardPoolManager(root)
    manager.initialize_pool()
    updated = manager.update_progress("ALPHA", 0.4, "step", working=working)
    return updated["state"]


def test_text_false_working_does_not_start(tmp_path):
    assert (
        _state(tmp_path / "text-false", "false"),
        _state(tmp_path / "text-zero", "0"),
        _state(tmp_path / "real-false", False),
        _state(tmp_path / "one", 1),
        _state(tmp_path / "real-true", True),
    ) == (
        "STANDBY",
        "STANDBY",
        "STANDBY",
        "STANDBY",
        "WORKING",
    )
