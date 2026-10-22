from scripts.run_bodyguards import BodyguardPoolManager
from tests.test_bodyguard_progress import _stored


def test_progress_above_one_is_out_of_range(tmp_path):
    manager = BodyguardPoolManager(tmp_path / "repo")
    manager.initialize_pool()
    assert (
        _stored(manager, 1.5),
        _stored(manager, 1.0),
    ) == (
        ("raised", "progress is out of range."),
        ("stored", 1.0),
    )
