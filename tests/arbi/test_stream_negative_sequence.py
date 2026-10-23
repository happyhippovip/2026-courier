from tests.arbi.test_stream_sequence import _apply


def test_negative_stream_sequence_does_not_change_the_book():
    assert (
        _apply(-1),
        _apply(7),
    ) == (
        ("raised", "sequence is out of range.", None, 0),
        ("applied", 1.5, 7),
    )
