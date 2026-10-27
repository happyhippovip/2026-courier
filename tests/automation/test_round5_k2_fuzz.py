"""[DRUIDE | ACCOUNT 2] K2: seeded property/fuzz tests of tools/automation/journal_export.py.

Deterministic: every case is derived from `random.Random(seed)` with seeds 0..N-1 (N = 40, override with FUZZ_SEEDS); a failing seed is
printed in the test id and reproduces exactly. No network, no clock-dependent value in the generated journals.
"""

import io
import json
import os
import random
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core_builders import Attempt, created, stable  # noqa: E402
from courier_core.events import Event, EventType  # noqa: E402
from courier_core.journal import Journal  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402

SEEDS = range(int(os.environ.get("FUZZ_SEEDS", "40")))
TEXTS = ["ok", "line\nbreak", 'quote " and \\ backslash', "ünï-cödé", "日本語", "emoji \U0001F680", "sep \u2028 \u2029", "tab\tx", "", "a" * 300,
         "</script>", "\x7f del", "nul-free \x01 ctrl"]


def history(rng):
    """A legal random history: several tasks (golden / retried / killed-worker / cut off), interleaved, with hostile payload texts."""
    lanes = []
    for n in range(rng.randint(1, 4)):
        task = f"t{n}"
        events = [created(task, max_attempts=3)]
        for attempt in range(1, rng.randint(1, 3) + 1):
            a = Attempt(task, attempt, worker_id=f"w{rng.randint(1, 3)}")
            events += [a.claimed(), a.started()]
            events += [a.progress(rng.choice(TEXTS)) for _ in range(rng.randint(0, 3))]
            last = attempt >= 3 or rng.random() < 0.5
            if not last and rng.random() < 0.25:
                events += [a.lease_expired(), a.retry_scheduled()]
            elif last:
                events += [a.result_ready(), a.accepted(), a.complete()]
                break
            else:
                events += [a.result_ready(outcome="failure"), a.rejected(), a.retry_scheduled()]
        events = events[: rng.randint(2, len(events))] if rng.random() < 0.3 else events
        lanes.append(events)
    merged = [Event(**stable(type=EventType.CONTROLLER_STARTED))] if rng.random() < 0.5 else []
    while any(lanes):
        lane = rng.choice([l for l in lanes if l])
        merged.append(lane.pop(0))
    return merged


def build(tmp_path, seed):
    rng = random.Random(seed)
    events = history(rng)
    path = tmp_path / "courier.db"
    with Journal(path) as journal:
        for event in events:
            journal.append(event)
    return path, len(events), rng


def export(path, *flags):
    out, err = io.StringIO(), io.StringIO()
    code = je.main([str(path), *flags], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def head_of(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()[0]
    finally:
        conn.close()


def edit(path, *statements):
    conn = sqlite3.connect(str(path))
    conn.execute("DROP TRIGGER events_no_update")
    conn.execute("DROP TRIGGER events_no_delete")
    for statement in statements:
        conn.execute(statement)
    conn.commit()
    conn.close()


@pytest.mark.parametrize("seed", SEEDS)
def test_k2_export_is_deterministic_complete_and_the_out_file_equals_stdout(tmp_path, seed):
    path, count, _ = build(tmp_path, seed)
    code, out, err = export(path)
    assert code == 0 and err == "", err
    header, *events = [json.loads(line) for line in out.splitlines()]
    assert header["record"] == "header" and header["chain_ok"] is True and header["event_count"] == count
    assert header["head_hash"] == head_of(path) and header["head_seq"] == count and header["partial"] is False
    assert [e["seq"] for e in events] == list(range(1, count + 1)) and all(e["record"] == "event" for e in events)
    assert all(a["hash"] == b["prev_hash"] for a, b in zip(events, events[1:]))
    assert export(path) == (0, out, "")  # second run: byte-identical
    target = tmp_path / "export.jsonl"
    assert export(path, "--out", str(target))[0] == 0
    assert target.read_bytes() == out.encode("utf-8")
    assert [p.name for p in tmp_path.iterdir() if ".tmp" in p.name] == []


@pytest.mark.parametrize("seed", SEEDS)
def test_k2_only_transitions_is_an_in_order_subset_of_the_full_export(tmp_path, seed):
    path, _, _ = build(tmp_path, seed)
    full = export(path)[1].splitlines()[1:]
    code, out, _ = export(path, "--only-transitions")
    assert code == 0
    header, *subset = out.splitlines()
    assert json.loads(header)["only_transitions"] is True and json.loads(header)["event_count"] == len(full)
    it = iter(full)
    assert all(any(line == other for other in it) for line in subset)  # in order, no invention


@pytest.mark.parametrize("seed", SEEDS)
def test_k2_expect_head_hash_accepts_the_real_head_in_any_spelling_and_refuses_everything_else(tmp_path, seed):
    path, _, rng = build(tmp_path, seed)
    head = head_of(path)
    spelled = "".join(c.upper() if rng.random() < 0.5 else c for c in head)
    spelled = " " * rng.randint(0, 2) + spelled + "\t\n"[: rng.randint(0, 2)]
    assert export(path, "--expect-head-hash", spelled)[0] == 0
    other = "".join(rng.choice("0123456789abcdef") for _ in range(64))
    assert export(path, "--expect-head-hash", other)[0] == (0 if other == head else 8)
    for bad in (head[:-1], head + "0", head[:-1] + "g", "", "0x" + head[2:], head.replace(head[0], "\u0661", 1)):
        code, out, _ = export(path, "--expect-head-hash", bad)
        assert code == 2 and out == "", (bad, code)


COLUMNS = ["event_id", "schema_v", "type", "task_id", "attempt", "dispatch_id", "worker_id", "result_id", "ts_utc", "payload", "prev_hash", "hash"]


@pytest.mark.parametrize("seed", SEEDS)
def test_k2_any_single_cell_edit_is_either_caught_with_exit_4_and_no_output_or_changes_nothing(tmp_path, seed):
    path, count, rng = build(tmp_path, seed)
    original = export(path)[1]
    original_events = original.splitlines()[1:]
    shutil.copy(path, tmp_path / "orig.db")
    seq, column = rng.randint(1, count), rng.choice(COLUMNS)
    value = rng.choice(["x", "", "0", "1" * 64, "evil\nvalue", "\u202e"])
    edit(path, f"UPDATE events SET {column} = {sqlite3.connect(':memory:').execute('SELECT quote(?)', (value,)).fetchone()[0]} WHERE seq = {seq}")
    code, out, err = export(path)
    changed = sqlite3.connect(str(path)).execute(f"SELECT {column} FROM events WHERE seq = {seq}").fetchone()[0]
    was = sqlite3.connect(str(tmp_path / "orig.db")).execute(f"SELECT {column} FROM events WHERE seq = {seq}").fetchone()[0]
    if str(changed) == str(was):
        assert (code, out) == (0, original)
    else:
        assert code in (4, 5) and out == "", (column, seq, code, err)
        code2, partial_out, _ = export(path, "--allow-partial")
        assert code2 == code
        header, *partial = partial_out.splitlines()
        info = json.loads(header)
        assert info["partial"] is True and info["chain_ok"] is False and info["first_bad_seq"] <= seq
        assert partial == original_events[: len(partial)] and len(partial) < info["first_bad_seq"]  # a verified prefix, never the bad row


@pytest.mark.parametrize("seed", SEEDS)
def test_k2_a_cut_off_tail_is_exit_8_with_the_expected_head_and_a_valid_prefix_without_it(tmp_path, seed):
    path, count, rng = build(tmp_path, seed)
    if count < 2:
        pytest.skip("SKIPPED, NOT PASSED: generated journal has a single event (nothing to cut)")
    original = export(path)[1].splitlines()[1:]
    head = head_of(path)
    keep = rng.randint(1, count - 1)
    edit(path, f"DELETE FROM events WHERE seq > {keep}")
    code, out, _ = export(path)
    assert code == 0 and out.splitlines()[1:] == original[:keep]  # the documented limit: a cut tail is a valid shorter chain
    code, out, _ = export(path, "--expect-head-hash", head)
    assert code == 8 and out == ""


@pytest.mark.parametrize("seed", SEEDS)
def test_k2_random_byte_flips_in_the_database_file_never_crash_and_never_change_an_exit_0_output(tmp_path, seed):
    path, _, rng = build(tmp_path, seed)
    original = export(path)
    data = bytearray(path.read_bytes())
    for _ in range(rng.randint(1, 4)):
        data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
    path.write_bytes(bytes(data))
    code, out, err = export(path)  # an exception here is a finding
    assert code in (0, 3, 4, 5, 7), (code, err)
    if code == 0:
        assert out == original[1]  # a flip in unused space is fine; one that changes the data must not pass
    else:
        assert out == "" and err.startswith("JOURNAL_EXPORT_ERROR")


@pytest.mark.parametrize("seed", SEEDS)
def test_k2_truncated_or_random_files_never_crash_and_never_export_different_data(tmp_path, seed):
    path, _, rng = build(tmp_path, seed)
    original = export(path)[1]
    data = path.read_bytes()
    if seed % 2:  # cut anywhere: a cut that only removes index/free pages still exports exactly the original (checked below)
        path.write_bytes(data[: rng.randrange(len(data))])
        allowed = (0, 3, 4, 5)
    else:
        path.write_bytes(bytes(rng.randrange(256) for _ in range(rng.randint(0, 4096))))
        allowed = (3, 4)
    code, out, err = export(path)
    assert code in allowed and "Traceback" not in err, (code, err)
    assert out == (original if code == 0 else "")
