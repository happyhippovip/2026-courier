#!/usr/bin/env python3
"""Connector conformance (ADR 37480 D1): a courtesy check for connector
authors, never a daemon gate.

    connector_conformance.py <connector script> --listen <listen args...> --reply-to <alias> [--text T]

Exercises the three mechanical rules against ANY connector script:

1. single-listener refusal — a second `listen` with the same arguments, while
   the first is live, exits non-zero with a one-line diagnostic;
2. reply idempotency — two `reply --to <alias> --text T --key <k>` calls
   post once: the second exits 0 and its receipt says `"idempotent": true`
   (or repeats the first receipt byte for byte);
3. feed grammar — every non-empty stdout line the live listener printed
   parses as `c<n> <sender>: <text>` (`c` + digits, a sender without `:`).

"Live" is the listener's first stderr or stdout line (a connector announces
itself before it streams; this is the causal wait, no sleeping). Run it with
the connector's own fake backend on PATH. Exit 0 when all three pass.
"""

import argparse
import json
import re
import subprocess
import sys
import threading

FEED_RE = re.compile(r"^c[0-9]+ [^:]+: .*$")
import os

# Bound on a child told to stop, and on the second `listen` that must refuse:
# a connector that lost rule 3 keeps that second listener alive, which is a
# FAIL, never a hang. Tests may shorten it (CONNECTOR_CONFORMANCE_WAIT_S).
STOP_WAIT_S = float(os.environ.get("CONNECTOR_CONFORMANCE_WAIT_S", "30"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("script")
    parser.add_argument("--listen", nargs=argparse.REMAINDER, default=[], help="listen args (after `listen`)")
    parser.add_argument("--reply-to", default=None, metavar="ALIAS")
    parser.add_argument("--text", default="conformance check")
    parser.add_argument("--key", default="conformance-key")
    args, rest = parser.parse_known_args(argv)
    listen_args = list(args.listen)
    reply_to = args.reply_to
    # `--listen` swallows the remainder; pull `--reply-to <alias>` back out of it.
    if "--reply-to" in listen_args:
        idx = listen_args.index("--reply-to")
        reply_to = listen_args[idx + 1]
        del listen_args[idx:idx + 2]
    base = [sys.executable, "-B", args.script]
    results = {}

    live = subprocess.Popen(base + ["listen"] + listen_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout_lines = []
    ready = threading.Event()

    def pump(stream, sink):
        for line in stream:
            sink.append(line.rstrip("\n"))
            ready.set()

    stderr_lines = []
    threads = [threading.Thread(target=pump, args=(live.stdout, stdout_lines), daemon=True),
               threading.Thread(target=pump, args=(live.stderr, stderr_lines), daemon=True)]
    for thread in threads:
        thread.start()
    ready.wait(STOP_WAIT_S)
    try:
        second = subprocess.Popen(base + ["listen"] + listen_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            second_out, second_err = second.communicate(timeout=STOP_WAIT_S)
        except subprocess.TimeoutExpired:
            # Rule 3 lost: the second listener is live beside the first.
            second.kill()
            second.communicate()
            results["single-listener refusal"] = (False, "second listen still running after %gs (not refused)" % STOP_WAIT_S)
        else:
            refused = second.returncode != 0 and bool((second_out + second_err).strip())
            results["single-listener refusal"] = (refused, "exit %d: %s" % (
                second.returncode, (second_out + second_err).strip().splitlines()[:1]))

        if reply_to:
            first = subprocess.run(base + ["reply", "--to", reply_to, "--text", args.text, "--key", args.key],
                                   capture_output=True, text=True, timeout=STOP_WAIT_S)
            again = subprocess.run(base + ["reply", "--to", reply_to, "--text", args.text, "--key", args.key],
                                   capture_output=True, text=True, timeout=STOP_WAIT_S)
            ok = first.returncode == 0 and again.returncode == 0
            if ok:
                try:
                    receipt = json.loads(again.stdout.strip().splitlines()[-1])
                    ok = bool(receipt.get("idempotent")) or again.stdout == first.stdout
                except (ValueError, IndexError):
                    ok = again.stdout == first.stdout
            results["reply idempotency"] = (ok, "first exit %d, retry exit %d" % (first.returncode, again.returncode))
    finally:
        live.terminate()
        try:
            live.wait(timeout=STOP_WAIT_S)
        except subprocess.TimeoutExpired:
            live.kill()
        for thread in threads:
            thread.join(STOP_WAIT_S)

    feed = [line for line in stdout_lines if line.strip()]
    bad = [line for line in feed if not FEED_RE.match(line) and not line.startswith("refused:")]
    results["feed grammar"] = (not bad, "%d line(s) checked%s" % (len(feed), ("; bad: %r" % bad[:3]) if bad else ""))

    failed = False
    for name, (ok, detail) in results.items():
        print("%s: %s (%s)" % (name, "ok" if ok else "FAIL", detail))
        failed = failed or not ok
    if rest:
        print("ignored args: %r" % rest)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
