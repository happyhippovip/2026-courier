from scripts.run_bodyguards import BodyguardPoolManager
from tests.test_bodyguard_progress import _stored


def test_negative_bodyguard_progress_is_out_of_range(tmp_path):
    manager = BodyguardPoolManager(tmp_path / "repo")
    manager.initialize_pool()
    assert (
        _stored(manager, -0.1),
        _stored(manager, 0.4),
    ) == (
        ("raised", "progress is out of range."),
        ("stored", 0.4),
    )
