#!/usr/bin/env python3
"""Per-message hop report for the slack-connector's opt-in hop trace (#28433).

Run the daemon (its lanes inherit the variable) with SLACK_CONNECTOR_TRACE_HOPS=1,
send a few messages, then:

    python3 hop_report.py [--state-dir DIR] [--sessions DIR] [--last N] [--json]

Reads <state_dir>/hops.jsonl (state dir: --state-dir, else $SLACK_CONNECTOR_STATE_DIR,
else $XDG_DATA_HOME/muse/connectors/slack) and prints one row per (message, listener):

  cli     server accept (accepted_at_ms) -> the connector read the CLI's line
  admit   that read -> the conversation feed line was written (state lock, load, append)
  tail    feed written -> a coordinator's scoped tail read it (conversation rows only)
  print   the previous stamp -> the line was printed to the Monitor
          (the daemon's print includes its state persist)
  queue   printed -> the session's inbox_item_queued (needs --sessions)
  total   accepted -> the last stamp the row has

--sessions walks <dir>/**/session.jsonl (default: $XDG_DATA_HOME/muse/sessions, else
~/.local/share/muse/sessions, when it exists) for runtime.session `inbox_item_queued`
events and joins them to rows by the printed line's HEADER line: the Monitor queues
one body per stdout line, verbatim, and the `at=` stamp makes that line unique. A
header the Monitor truncated does not join (`queue` prints `-`). Stdlib only,
read-only.
"""
import argparse
import json
import os
import pathlib
import statistics
import sys
from datetime import datetime, timezone

HOPS_FILE_NAME = "hops.jsonl"
COLUMNS = ("cli_ms", "admit_ms", "tail_ms", "print_ms", "queue_ms", "total_ms")
HEADERS = ("cli", "admit", "tail", "print", "queue", "total")


def default_state_dir():
    configured = os.environ.get("SLACK_CONNECTOR_STATE_DIR")
    if configured:
        return configured
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, "muse", "connectors", "slack")


def default_sessions_dir():
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = os.path.join(xdg, "muse", "sessions")
    return path if os.path.isdir(path) else None


def load_records(path):
    records = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(record, dict) and record.get("event_id"):
                    records.append(record)
    except FileNotFoundError:
        return None
    except OSError as error:
        # FM-28433-1, read side: the same producers that make the writer fail
        # open (a directory in place of the ledger, a permission error) end the
        # report in one line, never a traceback.
        sys.exit(f"hop_report: cannot read {path}: {error}")
    return records


def load_queued(sessions_dir):
    """{printed line: [(queued_at_ms, session id)]} from every session.jsonl below `sessions_dir`."""
    queued = {}
    for path in pathlib.Path(sessions_dir).rglob("session.jsonl"):
        try:
            handle = open(path, "r", encoding="utf-8")
        except OSError:
            continue
        with handle:
            for raw in handle:
                if "inbox_item_queued" not in raw:
                    continue
                try:
                    record = json.loads(raw)
                except ValueError:
                    continue
                if record.get("payload_type") != "runtime.session":
                    continue
                payload = record.get("payload") or {}
                event = payload.get("event") or {}
                if payload.get("kind") != "run" or event.get("kind") != "inbox_item_queued":
                    continue
                body = event.get("body")
                recorded_at = record.get("recorded_at")
                if not isinstance(body, str) or not isinstance(recorded_at, int):
                    continue
                session_id = ((record.get("stream") or {}).get("id")) or path.parent.name
                queued.setdefault(body, []).append((recorded_at // 1000, session_id))
    return queued


def delta(record, later, earlier):
    if record.get(later) is None or record.get(earlier) is None:
        return None
    return int(record[later]) - int(record[earlier])


def message_id(event_id):
    if isinstance(event_id, str) and event_id.startswith("mailbox:"):
        try:
            parts = json.loads(event_id[len("mailbox:"):])
            if isinstance(parts, list) and len(parts) == 2:
                return str(parts[1])
        except ValueError:
            pass
    return event_id


def build_rows(records, queued):
    rows = []
    for record in records:
        row = {
            "event_id": record.get("event_id"),
            "message_id": message_id(record.get("event_id")),
            "conversation": record.get("conversation"),
            "lane": record.get("lane"),
            "from": record.get("from"),
            "role": record.get("role"),
            "pid": record.get("pid"),
            "occurred_at": record.get("occurred_at"),
            "accepted_at_ms": record.get("accepted_at_ms"),
            "printed_at_ms": record.get("printed_at_ms"),
            "queued_at_ms": None,
            "session_id": None,
            "cli_ms": delta(record, "read_at_ms", "accepted_at_ms"),
            "admit_ms": delta(record, "feed_written_at_ms", "read_at_ms"),
            "tail_ms": None,
            "print_ms": None,
            "queue_ms": None,
            "total_ms": None,
        }
        if record.get("role") == "conversation":
            row["tail_ms"] = delta(record, "tail_read_at_ms", "feed_written_at_ms")
            row["print_ms"] = delta(record, "printed_at_ms", "tail_read_at_ms")
        else:
            row["print_ms"] = delta(record, "printed_at_ms", "feed_written_at_ms")
        line = record.get("line")
        printed = record.get("printed_at_ms")
        # The Monitor queues one body per physical stdout line, so a multi-line
        # message joins on its HEADER line — the one carrying `": "` and the
        # `at=<printed_at_ms>` suffix (spec 23499 Clarifications, Session
        # 2026-09-03, #28433).
        key = line.split("\n", 1)[0] if isinstance(line, str) else None
        if key is not None and printed is not None and key in queued:
            later = sorted(entry for entry in queued[key] if entry[0] >= printed) or sorted(queued[key])
            row["queued_at_ms"], row["session_id"] = later[0]
            row["queue_ms"] = row["queued_at_ms"] - printed
        last = row["queued_at_ms"] or printed or record.get("persisted_at_ms") or record.get("feed_written_at_ms")
        if last is not None and record.get("accepted_at_ms") is not None:
            row["total_ms"] = int(last) - int(record["accepted_at_ms"])
        rows.append(row)
    rows.sort(key=lambda row: (row["accepted_at_ms"] or 0, row["printed_at_ms"] or 0, row["role"] or ""))
    return rows


def fmt_ms(value):
    return "-" if value is None else str(value)


def fmt_clock(ms):
    if ms is None:
        return "-"
    try:
        return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    except (OverflowError, OSError, ValueError):
        return str(ms)


def render(rows, state_dir, sessions_dir):
    out = [f"hop report: {os.path.join(state_dir, HOPS_FILE_NAME)}"
           + (f"  sessions: {sessions_dir}" if sessions_dir else "  (no --sessions: queue column empty)")]
    if not rows:
        out.append("no traced messages yet (run the listeners with SLACK_CONNECTOR_TRACE_HOPS=1)")
        return "\n".join(out)
    table = [("accepted (UTC)", "message", "role", *HEADERS)]
    for row in rows:
        who = f"{row['from']} {row['message_id']}"
        role = row["role"] if row["role"] != "conversation" else f"coordinator:{row['conversation']}"
        table.append((fmt_clock(row["accepted_at_ms"]), who, role, *(fmt_ms(row[key]) for key in COLUMNS)))
    for label, pick in (("p50", statistics.median), ("max", max)):
        summary = []
        for key in COLUMNS:
            values = [row[key] for row in rows if row[key] is not None]
            summary.append(fmt_ms(int(pick(values))) if values else "-")
        table.append(("", label, "", *summary))
    widths = [max(len(str(cell)) for cell in column) for column in zip(*table)]
    for index, line in enumerate(table):
        out.append("  ".join(str(cell).ljust(width) for cell, width in zip(line, widths)).rstrip())
        if index == 0:
            out.append("  ".join("-" * width for width in widths))
    out.append("all values in ms; cli = server accept -> CLI line read, admit = read -> feed written, "
               "tail = feed -> coordinator tail read, print = -> Monitor line, queue = -> inbox_item_queued")
    return "\n".join(out)


def positive_int(text):
    """`--last` is a row count: 0 or a negative would slice a plausible but wrong table."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("--last takes a positive row count")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Per-message hop deltas from the slack-connector hop trace (#28433).")
    parser.add_argument("--state-dir", default=None, help="connector state dir (default: env / XDG)")
    parser.add_argument("--sessions", default=None, help="muse sessions dir to join inbox_item_queued from")
    parser.add_argument("--last", type=positive_int, default=None, help="only the newest N rows (N >= 1)")
    parser.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = parser.parse_args(argv)
    if args.sessions is not None and not os.path.isdir(args.sessions):
        # Checked before the ledger is read, so the usage error holds with an
        # empty state dir too (review of #28516).
        parser.error(f"--sessions {args.sessions!r}: not a directory")
    state_dir = args.state_dir or default_state_dir()
    records = load_records(os.path.join(state_dir, HOPS_FILE_NAME))
    if records is None:
        print(f"no {HOPS_FILE_NAME} under {state_dir}: run the listeners with SLACK_CONNECTOR_TRACE_HOPS=1 first",
              file=sys.stderr)
        return 1
    sessions_dir = args.sessions or default_sessions_dir()
    queued = load_queued(sessions_dir) if sessions_dir else {}
    rows = build_rows(records, queued)
    if args.last is not None:
        rows = rows[-args.last:]
    if args.json:
        print(json.dumps(rows, indent=1))
    else:
        print(render(rows, state_dir, sessions_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
