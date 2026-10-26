"""Deterministic, read-only status export of the Courier journal.

The hash-chained SQLite journal (courier_core/journal.py) is the only event
source. This module reads it, refuses to export when the chain is broken, and
writes one JSON line per event (sorted keys, journal order, journal
timestamps only, no export time, no randomness), so exporting the same journal
twice yields byte-identical output.

It is not a second database, a scheduler or a model call: it opens the file
read-only (SQLite `mode=ro`, `PRAGMA query_only=ON`), makes no network call and
never writes to the journal database or its -wal file. What it DOES touch, honestly:
* SQLite itself may create or update the `-shm` (shared-memory index) and, for an idle
  WAL database on a writable medium, create empty `-wal`/`-shm` files beside the journal
  (that is what a `mode=ro` reader of a WAL database does; the database file's bytes and
  mtime stay unchanged). Nothing is ever deleted.
* The export itself (`--out`, written atomically via a temp file next to it: data fsync, rename, then a best-effort fsync of the
  output directory on POSIX so the rename survives a power cut; Windows skips the directory step).

Open mode: always `mode=ro`, so the reader works on a consistent snapshot even while the
controller appends. `immutable=1` (no locking, no snapshot) is used ONLY when the medium is
read-only (directory not writable or read-only mount) and no -wal/-shm/-journal exists:
then no writer can exist. If the file or its sidecars change while such an immutable read is
running, the export fails with exit 7 instead of returning torn data.

    python -m tools.automation.journal_export <courier.db> [--out FILE]
                                          [--only-transitions] [--allow-partial]
                                          [--expect-head-hash HEX]

Exit codes: 0 exported · 2 usage (also: --out would overwrite the journal or its files) ·
3 journal missing/unreadable (also: an open that SQLite refuses, e.g. a database that needs
a writable directory) · 4 hash chain broken or stored text not valid UTF-8 (no export; with
--allow-partial the verified prefix is exported and the exit code stays 4) · 5 event stream
does not fold through the state machine · 6 output could not be written · 7 journal changed
while it was being read (the run is not trustworthy; run again; with --out nothing replaces
the old file; on stdout lines already written must be discarded) · 8 head differs from
--expect-head-hash (journal shorter, newer or replaced).

Completeness: a hash chain proves that what is there is intact, NOT that nothing was cut off
at the end (a deleted last event, a truncated WAL). The header carries head_seq/head_hash and
`head_checked`: false unless the caller supplied --expect-head-hash. Compare the header with a
head you know from another source before treating an export as complete.

Operating notes (read before wiring this into a script):
* Run it as the user that runs the controller. On a writable medium a `mode=ro` reader of a WAL journal may create
  the -wal/-shm sidecars, and they get the owner and permissions of whoever exports: sidecars owned by another user
  (for example root) can stop the controller from opening its own journal afterwards.
* The export holds one read snapshot from the first check until the last line is written. While it is open SQLite cannot
  checkpoint past that snapshot, so the WAL grows (and an explicit `wal_checkpoint(TRUNCATE)` of a writer waits).
  Prefer `--out FILE` (the stream is written at file speed) and do not stall the consumer of stdout for long.
* With `--out` a failed run (exit 6, 7, 8 ...) never replaces the previous export file. On stdout the lines that were
  already written cannot be taken back: when exit 7 is reported they are not trustworthy, so the consumer must check the
  exit code and discard what it read whenever the code is not 0 (or 4 with --allow-partial).
* `--expect-head-hash` takes the 64 hex digits of the head hash; upper case and surrounding whitespace are normalised, anything
  else is a usage error (exit 2).

Memory use is O(tasks), not O(events): output is streamed after a first pass has verified the
chain and checked the state-machine fold, and a second pass in the same read snapshot checks
that exactly the verified events were emitted.
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
(EXIT_OK, EXIT_USAGE, EXIT_UNREADABLE, EXIT_BAD_CHAIN, EXIT_BAD_FOLD, EXIT_WRITE, EXIT_CHANGED,
 EXIT_HEAD_MISMATCH) = 0, 2, 3, 4, 5, 6, 7, 8
SIDECARS = ("-wal", "-shm", "-journal")


class ExportError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _sidecars_exist(path: Path) -> bool:
    return any(Path(f"{path}{suffix}").exists() for suffix in SIDECARS)


def medium_is_read_only(path: Path) -> bool:
    """True when nothing can be created beside the journal: directory not writable, or a read-only mount.
    (Not detectable on every platform: then False, i.e. the safe default mode=ro is used.)"""
    parent = Path(path).parent
    try:
        if not os.access(parent, os.W_OK):
            return True
        flags = os.statvfs(parent).f_flag
        return bool(flags & getattr(os, "ST_RDONLY", 1))
    except (AttributeError, OSError):
        return False


def _readonly_uri(path: Path, immutable_ok: bool = True) -> str:
    """Always `mode=ro` (a snapshot reader that tolerates a live writer). `immutable=1` only on a
    read-only medium with no -wal/-shm/-journal: nothing can then write, and SQLite could not create
    the sidecars a WAL reader needs."""
    base = Path(os.path.abspath(path)).as_uri()
    if immutable_ok and medium_is_read_only(path) and not _sidecars_exist(path):
        return f"{base}?mode=ro&immutable=1"
    return f"{base}?mode=ro"


def _signature(path: Path):
    """What an immutable open assumes never changes: the file itself and the absence of sidecars."""
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, tuple(Path(f"{path}{s}").exists() for s in SIDECARS))


def _classify(path, exc: Exception) -> ExportError:
    text = str(exc)
    if "decode" in text.lower():  # stored text is not valid UTF-8: the content is damaged
        return ExportError(EXIT_BAD_CHAIN, f"{path}: stored journal text is not valid UTF-8: {text}")
    return ExportError(EXIT_UNREADABLE, f"{path}: cannot read journal: {text}")


def normalize_head_hash(value: str | None) -> str | None:
    """Lower-case 64-hex head hash, or ExportError(2) for anything else (None stays None)."""
    if value is None:
        return None
    if not isinstance(value, str):  # library callers: int/bytes/... are a usage error, not an AttributeError/TypeError
        raise ExportError(EXIT_USAGE, f"--expect-head-hash must be a string of 64 hex digits, got {type(value).__name__}")
    text = value.strip().lower()
    if len(text) != 64 or not text.isascii() or any(ch not in "0123456789abcdef" for ch in text):
        raise ExportError(EXIT_USAGE, f"--expect-head-hash must be 64 hex digits (the head_hash of an earlier export), got {value[:80]!r}")
    return text


def resolve_journal(path: str | os.PathLike) -> Path:
    """Follow symlinks first, so sidecar detection and the SQLite URI refer to the real file."""
    real = Path(os.path.realpath(path))
    if not real.is_file():
        raise ExportError(EXIT_UNREADABLE, f"{path}: no journal file")
    return real


def open_readonly(path: str | os.PathLike, immutable_ok: bool = True) -> Journal:
    path = resolve_journal(path)
    signature = _signature(path)  # taken BEFORE the open mode is chosen, so a change afterwards is seen
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
    journal.signature_before = signature
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


def _walk(journal: Journal, count: int, only_transitions: bool, head_hash: str | None = None) -> Iterator[str]:
    """One pass over the verified prefix; memory is O(tasks), never O(events).

    At the end the pass proves it saw exactly the verified events (row count and, when the chain is
    intact, the head hash): a snapshot that silently differs from the verified one is exit 7."""
    statuses: dict[str, object] = {}
    rows, last_hash = 0, None
    try:
        for event, payload_text in _rows(journal, count):
            rows += 1
            last_hash = event.hash
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
    if rows != count or (head_hash is not None and count and last_hash != head_hash):
        raise ExportError(EXIT_CHANGED, f"journal changed while it was being exported: verified {count} events, "
                                        f"read {rows} (head hash {'equal' if last_hash == head_hash else 'differs'})")


def export_stream(path: str | os.PathLike, only_transitions: bool = False, allow_partial: bool = False,
                  expect_head_hash: str | None = None) -> tuple[Iterator[str], int, Callable[[], None]]:
    """Verify, then return (line iterator, exit code, close function).

    Everything that can fail (open, chain check, state-machine fold, expected head) happens BEFORE the
    first line is handed out, so a refused export never produces output. The returned iterator reads a
    second time inside the same read snapshot, one event at a time (constant memory), and raises
    ExportError(7) at its end if what it read is not what pass 1 verified."""
    expect_head_hash = normalize_head_hash(expect_head_hash)  # before anything is opened
    journal = open_readonly(path)
    real = Path(journal.path)
    try:
        report = journal.verify_chain()
        if not report.ok and not allow_partial:
            raise ExportError(EXIT_BAD_CHAIN, f"{path}: hash chain broken at seq {report.first_bad_seq}: {report.reason}")
        head_hash = report.head_hash if report.ok else None
        for _ in _walk(journal, report.count, only_transitions, head_hash):  # pass 1: fold check, no output
            pass
        if journal.immutable_open and _signature(real) != journal.signature_before:
            raise ExportError(EXIT_CHANGED, f"{path}: file changed during an immutable (read-only medium) read")
        if expect_head_hash is not None and report.ok and report.head_hash != expect_head_hash:
            raise ExportError(EXIT_HEAD_MISMATCH, f"{path}: head hash {report.head_hash} differs from expected "
                                                  f"{expect_head_hash} (journal shorter, newer or replaced)")
        if expect_head_hash is not None and not report.ok:
            raise ExportError(EXIT_BAD_CHAIN, f"{path}: head cannot be checked on a broken chain")
    except sqlite3.Error as exc:
        journal.close()
        raise _classify(path, exc) from exc
    except BaseException:
        journal.close()
        raise
    header = {"chain_ok": report.ok, "event_count": report.count, "first_bad_seq": report.first_bad_seq,
              "format": FORMAT, "head_checked": expect_head_hash is not None, "head_hash": report.head_hash,
              "head_seq": report.head_seq, "only_transitions": only_transitions, "partial": not report.ok,
              "record": "header"}

    def lines() -> Iterator[str]:
        yield _dumps(header)
        yield from _walk(journal, report.count, only_transitions, head_hash)  # pass 2: emit
        if journal.immutable_open and _signature(real) != journal.signature_before:
            raise ExportError(EXIT_CHANGED, f"{path}: file changed during an immutable (read-only medium) read")

    return lines(), (EXIT_OK if report.ok else EXIT_BAD_CHAIN), journal.close


def export_lines(path: str | os.PathLike, only_transitions: bool = False, allow_partial: bool = False,
                 expect_head_hash: str | None = None) -> tuple[list[str], int]:
    """Convenience for tests and small journals: the whole export in memory."""
    stream, code, close = export_stream(path, only_transitions, allow_partial, expect_head_hash)
    try:
        return list(stream), code
    finally:
        close()


def _same_file_as_journal(out: Path, journal: Path) -> bool:
    guarded = [journal] + [Path(f"{journal}{s}") for s in SIDECARS]
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


def _fsync_dir(directory: Path) -> None:
    """fsync the output directory after os.replace so a power cut cannot bring the old export back. Best effort:
    some filesystems refuse it; skipped on Windows. A failure here never changes the exit code (the file is complete)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(
        prog="tools.automation.journal_export", description=__doc__.split("\n\n")[0],
        epilog="Always check the exit code: with stdout the lines written before a failure (exit 7) must be discarded. "
               "Use --out to keep the previous export on failure. Run as the user that runs the controller.")
    parser.add_argument("journal", help="path to courier.db (opened read-only)")
    parser.add_argument("--out", help="write the export to this file instead of stdout")
    parser.add_argument("--only-transitions", action="store_true", help="skip events that do not change a task status")
    parser.add_argument("--allow-partial", action="store_true",
                        help="on a broken chain export the verified prefix (exit code stays 4)")
    parser.add_argument("--expect-head-hash", metavar="HEX",
                        help="head hash (64 hex digits, case-insensitive) known from another source; malformed = exit 2, a "
                             "different head = exit 8 (detects a cut-off tail)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    try:
        real = resolve_journal(args.journal)
        if args.out and _same_file_as_journal(Path(args.out), real):
            raise ExportError(EXIT_USAGE, f"--out {args.out} is the journal (or one of its files); refusing to overwrite it")
        stream, code, close = export_stream(args.journal, args.only_transitions, args.allow_partial,
                                            args.expect_head_hash)
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
                _fsync_dir(out.resolve().parent)  # make the rename itself durable (POSIX, best effort)
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
        except ExportError as exc:  # state-machine/read problem or a changed journal found while emitting
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
