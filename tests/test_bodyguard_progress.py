import math

from scripts.run_bodyguards import BodyguardPoolManager


def _stored(manager, progress):
    try:
        state = manager.update_progress("ALPHA", progress, "step", working=False)
    except ValueError as exc:
        return ("raised", str(exc))
    value = state["progress"]
    if isinstance(value, float) and math.isnan(value):
        return ("stored", "nan")
    return ("stored", value)


def test_nan_bodyguard_progress_is_not_a_number(tmp_path):
    manager = BodyguardPoolManager(tmp_path / "repo")
    manager.initialize_pool()
    assert (
        _stored(manager, float("nan")),
        _stored(manager, float("inf")),
        _stored(manager, 0.4),
    ) == (
        ("raised", "progress is not a number."),
        ("raised", "progress is not a number."),
        ("stored", 0.4),
    )
