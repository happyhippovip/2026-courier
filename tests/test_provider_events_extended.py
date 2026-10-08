import pytest
from courier_runtime.provider_events import parse_line, read_new_lines, OUTCOMES


def test_parse_line_blank_and_whitespace():
    assert parse_line("") == (None, {}, "")
    assert parse_line("   ") == (None, {}, "")
    assert parse_line(None) == (None, {}, "")


def test_parse_line_grammar_variations():
    # Idle line
    kind, fields, raw = parse_line("IDLE")
    assert kind == "IDLE" and fields == {} and raw == ""

    # Output line
    kind, fields, raw = parse_line("OUTPUT raw provider stream content with tokens")
    assert kind == "OUTPUT" and raw == "raw provider stream content with tokens"

    # Turn ended with checkpoint
    kind, fields, raw = parse_line("TURN_ENDED outcome=DONE checkpoint=milestone 1 verified")
    assert kind == "TURN_ENDED"
    assert fields["outcome"] == "DONE"
    assert fields["checkpoint"] == "milestone 1 verified"

    # Turn ended with reason
    kind, fields, raw = parse_line("TURN_ENDED outcome=BLOCKED reason=API rate limit hit")
    assert kind == "TURN_ENDED"
    assert fields["outcome"] == "BLOCKED"
    assert fields["reason"] == "API rate limit hit"

    # Heartbeat line
    kind, fields, raw = parse_line("HEARTBEAT progress=1 checkpoint=mid-step")
    assert kind == "HEARTBEAT"
    assert fields["progress"] == "1"
    assert fields["checkpoint"] == "mid-step"


def test_read_new_lines_incremental(tmp_path):
    p = tmp_path / "events.log"
    p.write_text("LINE 1\nLINE 2\n", encoding="utf-8")

    lines, offset = read_new_lines(str(p), 0)
    assert lines == ["LINE 1", "LINE 2"]

    # Append new lines
    with open(str(p), "a", encoding="utf-8") as f:
        f.write("LINE 3\n")

    new_lines, new_offset = read_new_lines(str(p), offset)
    assert new_lines == ["LINE 3"]
    assert new_offset > offset
