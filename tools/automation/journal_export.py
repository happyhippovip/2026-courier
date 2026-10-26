"""Deterministic, read-only status export of the Courier journal.

The hash-chained SQLite journal (courier_core/journal.py) is the only event
source. This module reads it, refuses to export when the chain is broken, and
writes one JSON line per event (sorted keys, journal order, journal
timestamps only, no export time, no randomness), so exporting the same journal
twice yields byte-identical output.

It is not a second database, a scheduler or a model call: it opens the file
read-only, makes no network call and writes nothing but the export itself.

    python -m tools.automation.journal_export <courier.db> [--out FILE]
                                          [--only-transitions] [--allow-partial]

Exit codes: 0 exported · 2 usage · 3 journal missing/unreadable ·
4 hash chain broken (no export; with --allow-partial the verified prefix is
exported and the exit code stays 4) · 5 event stream does not fold through the
state machine · 6 output could not be written. Exit 2 is also used when --out
would overwrite the journal or one of its -wal/-shm/-journal files (checked after
resolving symlinks and hard links). Text that is not valid UTF-8 counts as a damaged
chain (exit 4). Memory use is O(tasks), not O(events): output is streamed after a
first pass has verified the chain and checked the state-machine fold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Callable, Iterator

from courier_core.events import SYSTEM_EVENTS, Event
from courier_core.journal import Journal, JournalError
from courier_core.state_machine import apply as apply_state

FORMAT = "courier-journal-status-export/1"
EXIT_OK, EXIT_USAGE, EXIT_UNREADABLE, EXIT_BAD_CHAIN, EXIT_BAD_FOLD, EXIT_WRITE = 0, 2, 3, 4, 5, 6


class ExportError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _readonly_uri(path: Path, immutable_ok: bool = True) -> str:
    """Always `mode=ro`. An idle WAL database (no -wal/-shm/-journal beside it) is
    additionally opened `immutable=1`, because even a mode=ro reader would create the
    -wal/-shm files there. When those files exist (a live writer or an unclean stop),
    plain mode=ro is used so committed WAL content is part of the snapshot."""
    base = Path(os.path.abspath(path)).as_uri()
    sidecars = (Path(f"{path}-wal"), Path(f"{path}-shm"), Path(f"{path}-journal"))
    if immutable_ok and not any(p.exists() for p in sidecars):
        return f"{base}?mode=ro&immutable=1"
    return f"{base}?mode=ro"


def _signature(path: Path):
    """What an immutable open assumes never changes: the file itself and the absence of sidecars."""
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, tuple(Path(f"{path}{s}").exists() for s in ("-wal", "-shm", "-journal")))


def _classify(path, exc: Exception) -> ExportError:
    text = str(exc)
    if "decode" in text.lower():  # stored text is not valid UTF-8: the content is damaged
        return ExportError(EXIT_BAD_CHAIN, f"{path}: stored journal text is not valid UTF-8: {text}")
    return ExportError(EXIT_UNREADABLE, f"{path}: cannot read journal: {text}")


def resolve_journal(path: str | os.PathLike) -> Path:
    """Follow symlinks first, so sidecar detection and the SQLite URI refer to the real file."""
    real = Path(os.path.realpath(path))
    if not real.is_file():
        raise ExportError(EXIT_UNREADABLE, f"{path}: no journal file")
    return real


def open_readonly(path: str | os.PathLike, immutable_ok: bool = True) -> Journal:
    path = resolve_journal(path)
    uri = _readonly_uri(path, immutable_ok)
    try:
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")  # one read snapshot for verification and export
        conn.execute("SELECT 1 FROM events LIMIT 1").fetchall()
    except sqlite3.Error as exc:
        raise _classify(path, exc) from exc
    journal = Journal(path, readonly=True)
    journal._conn = conn  # hand the existing verifier a connection that cannot write
    journal.immutable_open = "immutable=1" in uri
    return journal


def _record(event: Event, payload_text: str, before: str | None, after: str | None) -> dict:
    return {
        "attempt": event.attempt,
        "dispatch_id": event.dispatch_id,
        "event_id": event.event_id,
        "from_status": before,
        "hash": event.hash,
        "payload_sha256": hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
        "prev_hash": event.prev_hash,
        "record": "event",
        "result_id": event.result_id,
        "seq": event.seq,
        "task_id": event.task_id,
        "to_status": after,
        "transition": before != after,
        "ts_utc": event.ts_utc,
        "type": event.type.value,
        "worker_id": event.worker_id,
    }


def _rows(journal: Journal, limit: int) -> Iterator[tuple[Event, str]]:
    columns = "seq, event_id, schema_v, type, task_id, attempt, dispatch_id, worker_id, result_id, " \
              "dedupe_key, ts_utc, payload, prev_hash, hash"
    for row in journal.conn.execute(f"SELECT {columns} FROM events ORDER BY seq LIMIT ?", (limit,)):
        yield Event.from_row(row), row["payload"]


def _dumps(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _walk(journal: Journal, count: int, only_transitions: bool) -> Iterator[str]:
    """One pass over the verified prefix; memory is O(tasks), never O(events)."""
    statuses: dict[str, object] = {}
    try:
        for event, payload_text in _rows(journal, count):
            before = after = None
            if event.type not in SYSTEM_EVENTS:
                state = statuses.get(event.task_id)
                before = state.status.value if state is not None else None
                state = apply_state(state, event)
                statuses[event.task_id] = state
                after = state.status.value if state is not None else None
            if only_transitions and before == after:
                continue
            yield _dumps(_record(event, payload_text, before, after))
    except ValueError as exc:
        raise ExportError(EXIT_BAD_FOLD, f"event stream does not fold: {exc}") from exc
    except sqlite3.Error as exc:
        raise _classify("journal", exc) from exc


def export_stream(path: str | os.PathLike, only_transitions: bool = False,
                  allow_partial: bool = False) -> tuple[Iterator[str], int, Callable[[], None]]:
    """Verify, then return (line iterator, exit code, close function).

    Everything that can fail (open, chain check, state-machine fold) happens BEFORE the first
    line is handed out, so a refused export never produces output. The returned iterator reads a
    second time inside the same read snapshot, one event at a time (constant memory)."""
    journal = None
    for immutable_ok in (True, False):
        journal = open_readonly(path, immutable_ok)
        real = Path(journal.path)
        before = _signature(real)
        try:
            report = journal.verify_chain()
            if not report.ok and not allow_partial:
                raise ExportError(EXIT_BAD_CHAIN, f"{path}: hash chain broken at seq {report.first_bad_seq}: {report.reason}")
            for _ in _walk(journal, report.count, only_transitions):  # pass 1: fold check, no output
                pass
        except sqlite3.Error as exc:
            journal.close()
            raise _classify(path, exc) from exc
        except BaseException:
            journal.close()
            raise
        # An immutable open assumed nobody writes. If the file or its sidecars changed meanwhile
        # (a writer started), discard the result and read again through a normal read-only open.
        if journal.immutable_open and _signature(real) != before:
            journal.close()
            continue
        break
    header = {"chain_ok": report.ok, "event_count": report.count, "first_bad_seq": report.first_bad_seq,
              "format": FORMAT, "head_hash": report.head_hash, "head_seq": report.head_seq,
              "only_transitions": only_transitions, "partial": not report.ok, "record": "header"}

    def lines() -> Iterator[str]:
        yield _dumps(header)
        yield from _walk(journal, report.count, only_transitions)  # pass 2: emit

    return lines(), (EXIT_OK if report.ok else EXIT_BAD_CHAIN), journal.close


def export_lines(path: str | os.PathLike, only_transitions: bool = False,
                 allow_partial: bool = False) -> tuple[list[str], int]:
    """Convenience for tests and small journals: the whole export in memory."""
    stream, code, close = export_stream(path, only_transitions, allow_partial)
    try:
        return list(stream), code
    finally:
        close()


def _same_file_as_journal(out: Path, journal: Path) -> bool:
    guarded = [journal] + [Path(f"{journal}{s}") for s in ("-wal", "-shm", "-journal")]
    out_real = Path(os.path.realpath(out))
    for item in guarded:
        if out_real == Path(os.path.realpath(item)):
            return True
        try:
            if out.exists() and item.exists() and os.path.samefile(out, item):
                return True
        except OSError:
            pass
    return False


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(prog="tools.automation.journal_export", description=__doc__.split("\n\n")[0])
    parser.add_argument("journal", help="path to courier.db (opened read-only)")
    parser.add_argument("--out", help="write the export to this file instead of stdout")
    parser.add_argument("--only-transitions", action="store_true", help="skip events that do not change a task status")
    parser.add_argument("--allow-partial", action="store_true",
                        help="on a broken chain export the verified prefix (exit code stays 4)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    try:
        real = resolve_journal(args.journal)
        if args.out and _same_file_as_journal(Path(args.out), real):
            raise ExportError(EXIT_USAGE, f"--out {args.out} is the journal (or one of its files); refusing to overwrite it")
        stream, code, close = export_stream(args.journal, args.only_transitions, args.allow_partial)
    except ExportError as exc:
        print(f"JOURNAL_EXPORT_ERROR code={exc.code} {exc}", file=stderr)
        return exc.code
    tmp = None
    try:
        try:
            if args.out:
                out = Path(args.out)
                tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
                with open(tmp, "wb") as handle:
                    for line in stream:
                        handle.write(line.encode("utf-8") + b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, out)
                tmp = None
            else:
                sink = getattr(stdout, "buffer", None)
                for line in stream:
                    if sink is not None:
                        sink.write(line.encode("utf-8") + b"\n")
                    else:
                        stdout.write(line + "\n")
                if sink is not None:
                    sink.flush()
        except OSError as exc:
            print(f"JOURNAL_EXPORT_ERROR code={EXIT_WRITE} cannot write export: {exc}", file=stderr)
            return EXIT_WRITE
        except ExportError as exc:  # state-machine/read problem found while emitting
            print(f"JOURNAL_EXPORT_ERROR code={exc.code} {exc}", file=stderr)
            return exc.code
    finally:
        close()
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    if code:
        print(f"JOURNAL_EXPORT_PARTIAL code={code} chain broken; exported the verified prefix only", file=stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
