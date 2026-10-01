#!/usr/bin/env python3
"""Herdr bootstrap for the daemon (ADR 25011 D30; spec 25011 FR-25011-41..46).

Outside a Herdr pane the daemon offers Herdr once per start; the human's yes
is the only trigger; the answer is a per-machine record beside the registry.
`daemon_registry.py start` folds `detect` into its one JSON line (the field
`herdr_offer`); the action verbs are called by the daemon after the human
answered. One JSON line per verb, `outcome` + `next`, never a traceback.

  detect  [--daemon-session-id ID] [--reopen]      the offer read; mints the
                                                    one-time consent token when
                                                    an offer is due
  status                                            read-only: record + detection
  decline --consent-token T --by WORDS              records `no`; runs nothing
  start   --consent-token T --by WORDS [--words W]  the start step: server up if
          [--daemon-session-id ID] [--no-retire]    needed, the daemon relaunched
          [--retire-pid PID] [--timeout-s S]        in a Herdr pane, this process
                                                    retired
  install --consent-token T --by WORDS [...]        the install step: the quoted
          [--install-timeout-s S]                   installer under a bound,
                                                    `herdr --version` verified,
                                                    then the start step

Every action verb spawns nothing without the exact unspent token and a
non-empty `--by` (`consent_missing`, exit 3). Exit codes: 0 ok, 2 usage,
3 refused (consent_missing, already_installed, already_in_herdr), 6 evidence
(failed, install_failed, install_timeout), 7 internal; the offer read itself
never fails a `start` (a broken probe is `no_offer` / `herdr_unreadable`).
"""

import argparse
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

RECORD = "herdr-offer.json"
RECORD_SCHEMA_VERSION = 1  # Constitution V: the sidecar carries its own version; a missing key reads as 1
LANE_NAME = "muse-daemon"
INSTALL_URL_ENV = "MUSE_HERDR_INSTALL_URL"
DEFAULT_INSTALL_URL = "https://herdr.dev/install.sh"
HERDR = ["herdr"]  # the binary, resolved on the one search path; fixtures swap it in via PATH
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_INSTALL_TIMEOUT_S = 300.0
PROBE_TIMEOUT_ENV = "MUSE_DAEMON_HERDR_PROBE_TIMEOUT_S"  # the bound on each read-only probe (FR-25011-41)
DEFAULT_PROBE_TIMEOUT_S = 3.0
LOCAL_BIN = os.path.join(os.path.expanduser("~"), ".local", "bin")  # where the published installer puts herdr
# The daemon's own environment the pane must see, by name (FR-25011-42): the
# gates and knobs (`MUSE_*`), the connector's (`SLACK_*`), the state roots
# (`XDG_*`, `DAEMON_*`) and the tool path; never the terminal context.
PASS_PREFIXES = ("MUSE_", "SLACK_", "XDG_", "DAEMON_")
PASS_NAMES = ("PATH",)
STRIP_PREFIXES = ("HERDR_", "MUSE_LANE_")
STRIP_NAMES = ("TMUX",)
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_EVIDENCE = 6
EXIT_INTERNAL = 7


class Refused(Exception):
    def __init__(self, outcome, message, next_hint, code=EXIT_REFUSED, **extra):
        super().__init__(message)
        self.outcome, self.next_hint, self.code, self.extra = outcome, next_hint, code, extra


class Failed(Refused):
    def __init__(self, outcome, message, next_hint, **extra):
        super().__init__(outcome, message, next_hint, EXIT_EVIDENCE, **extra)


def registry_module():
    """The sibling helper, imported lazily (it imports this module lazily
    too): the state root, the muse binary walk, the clock."""
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    import daemon_registry  # noqa: E402  (sibling script)
    return daemon_registry


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def host_name():
    return socket.gethostname() or "localhost"


def record_path(registry):
    return os.path.join(os.path.dirname(registry) or ".", RECORD)


def read_record(registry):
    """The per-machine record, or an empty one when the file is missing,
    unreadable, or malformed (FM-25011-4: never read as `no`)."""
    try:
        with open(record_path(registry), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {"hosts": {}}
    if not isinstance(data, dict) or not isinstance(data.get("hosts"), dict):
        return {"hosts": {}}
    version = data.get("schema_version", 1)
    if version != RECORD_SCHEMA_VERSION:
        # A newer record is not this helper's to read or rewrite: no offer,
        # never a guessed answer; `status` shows the version it met.
        return {"hosts": {}, "unreadable_version": version}
    data["schema_version"] = RECORD_SCHEMA_VERSION
    return data


def write_record(registry, data):
    path = record_path(registry)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, mode=0o700, exist_ok=True)
    tmp_path = None
    data.pop("unreadable_version", None)
    data["schema_version"] = RECORD_SCHEMA_VERSION
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".herdr-offer-", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except OSError:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def host_entry(data):
    return data["hosts"].setdefault(host_name(), {})


def save_host(registry, data, payload):
    """Persist; a directory that refuses the write loses only persistence and
    says so on the line (FR-25011-45). A record newer than this helper is
    never replaced: no offer, left untouched, named."""
    if "unreadable_version" in data:
        payload["unrecorded"] = (f"{record_path(registry)}: schema_version {data['unreadable_version']} is newer than"
                                 f" {RECORD_SCHEMA_VERSION}; left untouched")
        return
    try:
        write_record(registry, data)
    except OSError as error:
        payload["unrecorded"] = f"{record_path(registry)}: {error}"


def herdr_command():
    return list(HERDR)


def probe_timeout_s():
    try:
        value = float(os.environ.get(PROBE_TIMEOUT_ENV, ""))
    except ValueError:
        return DEFAULT_PROBE_TIMEOUT_S
    return value if value > 0 else DEFAULT_PROBE_TIMEOUT_S


def search_path():
    """"`herdr` on PATH" means the process PATH plus ~/.local/bin, once for
    every reader (FR-25011-41/-43/-45): detection, the start step, and the
    pane all see the same binary."""
    path = os.environ.get("PATH", "")
    parts = [p for p in path.split(os.pathsep) if p]
    if LOCAL_BIN not in parts:
        parts.append(LOCAL_BIN)
    return os.pathsep.join(parts)


def which_herdr(argv):
    return shutil.which(argv[0], path=search_path()) if argv else None


def herdr_call(argv, *args, timeout=None, env=None):
    """One herdr CLI call: (returncode, stdout, stderr); OSError and a hang
    past the bound are answered as a failed call with stderr naming why."""
    timeout = probe_timeout_s() if timeout is None else timeout
    run_env = dict(env if env is not None else os.environ)
    run_env.pop("TMUX", None)
    run_env["PATH"] = search_path()
    try:
        proc = subprocess.run([*argv, *args], capture_output=True, text=True, timeout=timeout, env=run_env, check=False)
    except OSError as error:
        return 127, "", f"herdr could not run: {error}"
    except subprocess.TimeoutExpired:
        return 124, "", f"herdr {' '.join(args[:2])} did not answer within {timeout:g}s"
    return proc.returncode, proc.stdout, proc.stderr


def herdr_json(argv, *args, timeout=None, env=None):
    code, out, err = herdr_call(argv, *args, timeout=timeout, env=env)
    if code != 0:
        raise Failed("failed", f"herdr {' '.join(args[:2])}: exit {code}: {(err or out).strip()[:300]}",
                     "say one line naming this cause; continue in tmux; the token stays valid for a try again")
    try:
        payload = json.loads(out)
    except ValueError as error:
        raise Failed("failed", f"herdr {' '.join(args[:2])} answered non-JSON: {error}",
                     "say one line naming this cause; continue in tmux; the token stays valid for a try again") from error
    result = payload.get("result") if isinstance(payload, dict) else None
    return result if isinstance(result, dict) else (payload if isinstance(payload, dict) else {})


def probe_herdr(argv):
    """`{installed, version, path, server, socket}`; raises Failed
    (`herdr_unreadable`) when an installed herdr cannot be read."""
    path = which_herdr(argv)
    if not path:
        return {"installed": False, "version": None, "path": None, "server": "unknown", "socket": None}
    code, out, err = herdr_call(argv, "--version")
    if code != 0:
        raise Failed("herdr_unreadable", f"herdr --version: exit {code}: {(err or out).strip()[:200]}",
                     "the herdr binary on PATH does not answer; the connect goes ahead without an offer")
    version = out.strip().split()[-1] if out.strip() else None
    server, sock = "unknown", None
    code, out, err = herdr_call(argv, "status", "--json")
    if code == 0:
        try:
            status = json.loads(out)
            running = bool((status.get("server") or {}).get("running"))
            server = "running" if running else "down"
            sock = (status.get("server") or {}).get("socket")
        except (ValueError, AttributeError) as error:
            raise Failed("herdr_unreadable", f"herdr status --json answered non-JSON: {error}",
                         "the herdr binary on PATH does not answer; the connect goes ahead without an offer") from error
    else:
        raise Failed("herdr_unreadable", f"herdr status --json: exit {code}: {(err or out).strip()[:200]}",
                     "the herdr binary on PATH does not answer; the connect goes ahead without an offer")
    return {"installed": True, "version": version, "path": path, "server": server, "socket": sock}


def inside_herdr():
    return os.environ.get("HERDR_ENV") == "1"


def install_url():
    return os.environ.get(INSTALL_URL_ENV) or DEFAULT_INSTALL_URL


def install_command():
    return f"curl -fsSL {install_url()} | sh"


def ask_text(step, herdr):
    if step == "install":
        url = install_url()
        origin = url.split("//", 1)[-1].split("/", 1)[0]
        return (f"Herdr is not installed on this machine. May I install it by running exactly `{install_command()}`?"
                f" It downloads Herdr's installer script from {origin} and runs it with your shell, which places the"
                " `herdr` binary under ~/.local/bin; then this daemon moves into a Herdr pane, where you can watch it"
                " and add more machines. Yes or no — no runs nothing, and I will not ask again on this machine.")
    server = "the Herdr server starts headless and " if herdr.get("server") != "running" else ""
    version = f" ({herdr['version']})" if herdr.get("version") else ""
    return (f"Herdr is installed{version} but this daemon runs outside it. Start Herdr and move the daemon into a"
            f" Herdr pane? Yes: {server}this session relaunches as `muse daemon` in a Herdr tab, open it with `herdr`"
            " and add machines with `herdr machine add <ssh-target>`. No: nothing changes, and I will not ask again"
            " on this machine.")


def script_name():
    return os.path.basename(os.path.realpath(__file__))


def offer_next(step, token, daemon_session_id):
    sid = f" --daemon-session-id {daemon_session_id}" if daemon_session_id else ""
    return (f"put the ask to your human exactly once (say the hand-off line first on a yes; references/herdr-bootstrap.md),"
            f" then wait: yes → python3 scripts/{script_name()} {step} --consent-token {token} --by \"<their words>\"{sid}"
            f" [--words \"<your own connect words>\"] (omit --words for a bare /daemon); no → python3 scripts/{script_name()} decline"
            f" --consent-token {token} --by \"<their words>\"; never proceed on silence, a click, or another participant")


def detect(registry, daemon_session_id=None, reopen=False, mint=True):
    """The offer read (FR-25011-41). `mint=False` is `status`: no token, no
    marker. Returns the payload; writes the marker only on an offer."""
    argv = herdr_command()
    data = read_record(registry)
    entry = dict(host_entry(data))
    record = {k: entry.get(k) for k in ("answer", "at", "by", "daemon_session_id", "handed_off") if k in entry} or None
    payload = {"inside_herdr": inside_herdr(), "host": host_name(), "record": record, "consent_token": None,
               "step": None, "install_command": None}
    if "unreadable_version" in data:
        payload["record_unreadable"] = (f"herdr-offer.json schema_version {data['unreadable_version']} is newer than"
                                        f" {RECORD_SCHEMA_VERSION}; not rewritten, no offer")
    if payload["inside_herdr"]:
        # Inside Herdr nothing is probed and nothing is written (FR-25011-41).
        payload.update(herdr=None, outcome="no_offer", reason="inside_herdr",
                       next="the connect goes ahead; say nothing about Herdr")
        return payload
    def no_offer(reason, next_hint="the connect goes ahead; say nothing about Herdr"):
        payload.update(outcome="no_offer", reason=reason, next=next_hint)
        return payload

    if "unreadable_version" in data:
        # A newer record may hold this machine's `no`: no ask whose yes could
        # not be kept (its token would not persist), never a guessed answer.
        payload["herdr"] = None
        return no_offer("record_unreadable")

    # The record answers first, so a declined or handed-over machine never
    # pays the binary probes on a start (review of #38456).
    handed = entry.get("handed_off") or {}
    if daemon_session_id and handed.get("daemon_session_id") == daemon_session_id:
        payload["herdr"] = None
        offered = entry.get("offered") or {}
        if handed.get("pending"):
            if offered.get("token") and offered.get("daemon_session_id") == daemon_session_id:
                payload["consent_token"] = offered["token"]
                return no_offer("handed_off_this_start",
                                "arm nothing: this daemon's hand-off to Herdr did not finish (the helper stopped after the"
                                f" human's yes); run it once more, exactly: python3 scripts/{script_name()}"
                                f" {offered.get('step') or 'start'} --consent-token {offered['token']} --daemon-session-id"
                                f" {daemon_session_id} --by \"<the same words>\" — it finishes the hand-off (a live"
                                " muse-daemon tab is yours) and ends this session")
            return no_offer("handed_off_this_start",
                            "arm nothing: this daemon's hand-off to Herdr is pending but its token was replaced by another"
                            " daemon's offer on this machine; nothing was handed over — tell your human and wait for their"
                            " word (a decline clears the pending hand-off); do not stop")
        return no_offer("handed_off_this_start",
                        f"arm nothing: this daemon already handed over to Herdr pane {handed.get('lane_ref')};"
                        " tell your human this session is done and stop")
    if entry.get("answer") == "no" and not reopen:
        payload["herdr"] = None
        return no_offer("recorded_no")
    offered = entry.get("offered") or {}
    if (daemon_session_id and offered.get("daemon_session_id") == daemon_session_id
            and offered.get("token") and not reopen):
        step = offered.get("step") or "start"
        payload.update(herdr=None, step=step, outcome="no_offer", reason="offered_this_start",
                       consent_token=offered["token"],
                       next="the ask was already put in this start: wait for the answer; yes → the "
                            f"{step} verb, no → decline, both with --consent-token {offered['token']}")
        return payload
    try:
        herdr = probe_herdr(argv)
    except Failed as error:
        herdr = {"installed": bool(which_herdr(argv)), "version": None, "path": which_herdr(argv), "server": "unknown",
                 "socket": None, "detail": str(error)}
        payload.update(herdr=herdr, outcome="no_offer", reason="herdr_unreadable",
                       next="the connect goes ahead; say nothing about Herdr")
        return payload
    payload["herdr"] = herdr
    step = "start" if herdr["installed"] else "install"
    payload["step"] = step
    if step == "install":
        payload["install_command"] = install_command()
    if not mint:
        return payload  # `status`: the read without a token or marker; `cmd_status` names the outcome
    token = secrets.token_hex(8)
    live = host_entry(data)
    live["offered"] = {"daemon_session_id": daemon_session_id, "at": utc_now(), "token": token, "step": step}
    save_host(registry, data, payload)
    payload.update(outcome="offer", reason=None, consent_token=token, ask=ask_text(step, herdr),
                   next=offer_next(step, token, daemon_session_id))
    return payload


def consent(registry, token, by):
    """The gate (FR-25011-42, INV-25011-1): the exact unspent token and the
    human's words, else nothing runs."""
    if not token or not (by or "").strip():
        raise Refused("consent_missing", "an action needs --consent-token (the token start minted) and --by (the human's own words)",
                      "nothing ran; ask your human, and pass their exact words with the token start printed")
    data = read_record(registry)
    entry = host_entry(data)
    offered = entry.get("offered") or {}
    if not offered.get("token") or offered.get("token") != token:
        raise Refused("consent_missing", "the consent token does not match the offer this machine made (missing, spent, or wrong)",
                      "nothing ran; a new offer needs `detect --reopen` after the human asks for Herdr again")
    return data, entry


def spend(entry, answer, by, daemon_session_id, **more):
    entry.pop("offered", None)
    entry.update(answer=answer, at=utc_now(), by=by, daemon_session_id=daemon_session_id)
    entry.update(more)


def cmd_decline(args):
    data, entry = consent(args.registry, args.consent_token, args.by)
    if (entry.get("handed_off") or {}).get("pending"):
        entry.pop("handed_off", None)  # the human gave up on an unfinished hand-off
    spend(entry, "no", args.by, args.daemon_session_id)
    payload = {"outcome": "declined", "record": {k: entry.get(k) for k in ("answer", "at", "by")}, "host": host_name()}
    save_host(args.registry, data, payload)
    payload["next"] = ("say one short line (nothing changes; you stay in tmux) and continue; never mention Herdr again"
                       " on this machine unless your human asks for it")
    return payload


def pass_env_pairs():
    pairs = {}
    for name, value in os.environ.items():
        if name in STRIP_NAMES or name.startswith(STRIP_PREFIXES):
            continue
        if name in PASS_NAMES or name.startswith(PASS_PREFIXES):
            pairs[name] = value
    pairs["PATH"] = search_path()
    return pairs


def child_env(extra=None):
    env = {name: value for name, value in os.environ.items()
           if name not in STRIP_NAMES and not name.startswith(STRIP_PREFIXES)}
    env["PATH"] = search_path()
    env.update(extra or {})
    return env


def server_up(argv, herdr, registry, timeout_s):
    """A running server, or one started headless and waited for, bounded
    (FR-25011-42, FM-25011-2). Returns the socket path."""
    if herdr.get("server") == "running":
        return herdr.get("socket"), False
    log_path = os.path.join(os.path.dirname(registry) or ".", "herdr-server.log")
    try:
        log = open(log_path, "ab")  # noqa: SIM115 - handed to the detached child
    except OSError:
        log = subprocess.DEVNULL
    try:
        subprocess.Popen([*argv, "server"], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, env=child_env())
    except OSError as error:
        raise Failed("failed", f"herdr server could not start: {error}", "check the herdr binary; continue in tmux")
    finally:
        if log is not subprocess.DEVNULL:
            log.close()
    deadline = time.monotonic() + timeout_s
    while True:
        code, out, _ = herdr_call(argv, "status", "--json", timeout=min(probe_timeout_s(), max(timeout_s, 0.1)))
        if code == 0:
            try:
                status = json.loads(out)
            except ValueError:
                status = {}
            server = status.get("server") or {}
            if server.get("running"):
                return server.get("socket"), True
        if time.monotonic() >= deadline:
            raise Failed("failed", f"the Herdr server did not answer within {timeout_s:g}s of `herdr server` (log: {log_path})",
                         "say one line: Herdr did not start; continue in tmux; the token stays valid for a try again")
        time.sleep(0.2)


def workspace_for(argv, env):
    listing = herdr_json(argv, "workspace", "list", env=env)
    for workspace in listing.get("workspaces") or []:
        if isinstance(workspace, dict) and workspace.get("label") == LANE_NAME and workspace.get("workspace_id"):
            return workspace["workspace_id"], False
    created = herdr_json(argv, "workspace", "create", "--label", LANE_NAME, "--cwd", os.getcwd(), "--no-focus", env=env)
    workspace = created.get("workspace") if isinstance(created.get("workspace"), dict) else {}
    workspace_id = workspace.get("workspace_id") or (created.get("root_pane") or {}).get("workspace_id")
    if not workspace_id:
        raise Failed("failed", "herdr workspace create answered without a workspace id",
                     "inspect Herdr yourself; continue in tmux")
    return workspace_id, True


def launch_daemon_pane(argv, workspace_id, sock, words):
    """The relaunch through the shared lane runtime (D29 item 3), explicit
    `--backend herdr`, with the workspace and socket set for that one call."""
    registry = registry_module()
    runtime = registry.require_lane_runtime()
    muse_bin = registry.daemon_binary_path()
    prompt = "/daemon" + (f" {words.strip()}" if words and words.strip() else "")
    command = [sys.executable or "python3", runtime]
    command += ["open", "--mode", "herdr", "--name", LANE_NAME, "--exact-name", "--label", LANE_NAME,
                # The daemon's tab joins the workspace this bootstrap made (or found) under LANE_NAME: since ADR
                # 38715 Amendment 7 the runtime never places a session by HERDR_WORKSPACE_ID (a bare `open` gets a
                # workspace of its own), so the join is named.
                "--workspace", LANE_NAME,
                "--cwd", os.getcwd(), "--prompt-file", "-", "--engine", muse_bin,
                # The daemon's own pane is unattended by definition: it must
                # never sit on a trust prompt (the runtime's default became
                # the engine's own prompts on 2026-09-19, #38715).
                "--unattended",
                "--engine-arg=--reasoning-effort", "--engine-arg=medium"]
    for name, value in sorted(pass_env_pairs().items()):
        command += ["--env", f"{name}={value}"]
    env = child_env({"HERDR_WORKSPACE_ID": workspace_id, "HERDR_SOCKET_PATH": sock or ""})
    try:
        proc = subprocess.run(command, input=prompt, capture_output=True, text=True, env=env, check=False)
    except OSError as error:
        raise Failed("failed", f"the lane runtime could not run: {error}", "continue in tmux")
    payload = None
    for line in reversed(proc.stdout.splitlines()):
        if line.strip().startswith("{"):
            try:
                payload = json.loads(line)
            except ValueError:
                payload = None
            break
    if not isinstance(payload, dict):
        raise Failed("failed", f"the lane runtime printed no JSON line (exit {proc.returncode}): {proc.stderr.strip()[:300]}",
                     "continue in tmux")
    if payload.get("outcome") == "name_taken":
        return {"taken": True, "lane_ref": payload.get("ref"), "tab_id": payload.get("tab_id"),
                "backend_server": sock, "workspace_id": workspace_id}
    if payload.get("outcome") != "opened":
        raise Failed("failed", f"the lane runtime answered {payload.get('outcome')}: {payload.get('message', '')}"[:400],
                     "say one line naming this cause; continue in tmux; the token stays valid for a try again",
                     runtime=payload)
    return {"lane_ref": payload.get("ref"), "tab_id": payload.get("tab_id"), "backend_server": payload.get("server"),
            "workspace_id": workspace_id, "command": payload.get("command"), "muse_bin": muse_bin, "prompt": prompt}


def daemon_ancestor_pid():
    """The nearest ancestor named in `DAEMON_BINARY_NAMES` (FR-25011-42), one
    `proc_parent` hop at a time; None when there is none. Not
    `daemon_binary_path`'s walk on purpose: that one skips a daemon whose
    binary is gone, while the process to retire is the live one whatever
    its file says."""
    registry = registry_module()
    pid = os.getppid()
    seen = set()
    for _ in range(32):
        if pid <= 1 or pid in seen:
            return None
        seen.add(pid)
        info = registry.proc_parent(pid)
        if info is None:
            return None
        parent, argv0 = info
        if os.path.basename(argv0) in registry.DAEMON_BINARY_NAMES:
            return pid
        if parent is None:
            return None
        pid = parent
    return None


def process_alive(pid):
    """Alive and not a zombie: a process its parent has not reaped yet still
    answers `kill 0`, but it has exited."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            return handle.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def retire(args, payload):
    """SIGTERM to the calling daemon's own muse process, then the bounded
    wait, and only then is the line printed (FR-25011-42): the graceful
    teardown `/quit` shares; nothing is added at exit."""
    if args.no_retire:
        payload["retired"] = False
        payload["retire_reason"] = "--no-retire"
        return None
    registry = registry_module()
    pid = None
    if args.retire_pid is not None:
        # A test seam, like the registry's: honored only under the suite's
        # arming flag (the registry's one predicate), never live — a live
        # daemon retires only its own ancestor, so a mistyped pid cannot end
        # a stranger.
        if not registry.test_seams_enabled():
            payload["retire_pid_ignored"] = f"--retire-pid {args.retire_pid} ({registry.TEST_SEAMS_ENV} not armed); the ancestor walk decides"
        else:
            pid = args.retire_pid
    if pid is not None and (pid <= 1 or pid == os.getpid() or pid == os.getppid()):
        # The seam value only: a pid the walk returns is argv0-vetted, and the
        # daemon IS the helper's direct parent when the tool shell exec'd it.
        payload["retired"] = False
        payload["retire_reason"] = f"pid {pid} is not a daemon to retire (init, this helper, or its shell); nothing signalled"
        return None
    if pid is None:
        pid = daemon_ancestor_pid()
    if not pid:
        payload["retired"] = False
        payload["retire_reason"] = "no daemon ancestor (muse/tbh) above this helper; nothing signalled"
        return None
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as error:
        payload["retired"] = False
        payload["retire_reason"] = f"SIGTERM undeliverable to pid {pid}: {error.strerror}; nothing retired"
        return None
    # The line is printed AFTER the signal, so it is true when read: exited
    # within the bounded wait, or signalled and still winding down.
    deadline = time.monotonic() + max(args.retire_wait_s, 0.0)
    state = "signalled"
    while True:
        if not process_alive(pid):
            state = "exited"
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    payload["retired"] = True
    payload["retire_pid"] = pid
    payload["retire_state"] = state
    return pid


def start_step(args, data, entry, answer):
    argv = herdr_command()
    payload = {"host": host_name()}
    herdr = probe_herdr(argv)
    if not herdr["installed"]:
        raise Failed("failed", "herdr is not on PATH; the start step needs it (the install step comes first)",
                     "run the install verb with the same consent flags")
    # The record first, before anything irreversible (D30 item 4(d)): the
    # answer and a pending hand-off; the token stays valid until completion.
    handed = entry.get("handed_off") or {}
    own_pending = (bool(handed.get("pending")) and args.daemon_session_id is not None
                   and handed.get("daemon_session_id") == args.daemon_session_id)
    before = dict(entry)
    entry.update(answer=answer, at=utc_now(), by=args.by, daemon_session_id=args.daemon_session_id)
    entry["handed_off"] = {"pending": True, "daemon_session_id": args.daemon_session_id, "at": utc_now()}
    save_host(args.registry, data, payload)
    sock, started = server_up(argv, herdr, args.registry, args.timeout_s)
    env = child_env({"HERDR_SOCKET_PATH": sock or ""})
    workspace_id, created = workspace_for(argv, env)
    launched = launch_daemon_pane(argv, workspace_id, sock, args.words)
    if launched.get("taken"):
        if not own_pending:
            # A foreign daemon's tab: this attempt changes nothing on the record.
            entry.clear()
            entry.update(before)
            try:
                write_record(args.registry, data)
            except OSError:
                pass
            raise Refused("already_in_herdr", f"a live Herdr tab labelled {LANE_NAME!r} already runs in workspace"
                          f" {workspace_id} (pane {launched['lane_ref']}); nothing was created",
                          "a daemon is already in Herdr there: say so in one line and stay; do not retry",
                          lane_ref=launched["lane_ref"], workspace_id=workspace_id)
        # K-25011-1: the live tab is this daemon's own unfinished hand-off; finish it.
        payload["completed_pending"] = True
        launched = {"lane_ref": launched["lane_ref"], "tab_id": launched.get("tab_id"),
                    "backend_server": launched["backend_server"], "workspace_id": workspace_id}
    entry.pop("offered", None)
    entry["handed_off"] = {"daemon_session_id": args.daemon_session_id, "lane_ref": launched["lane_ref"],
                           "backend_server": launched.get("backend_server"), "workspace_id": workspace_id, "at": utc_now()}
    payload.update(outcome="handed_off", server_started=started, workspace_created=created, **launched,
                   record={k: entry.get(k) for k in ("answer", "at", "by", "handed_off")})
    save_host(args.registry, data, payload)
    pid = retire(args, payload)
    payload["next"] = ("the Herdr daemon is live; this session " + ("ends now (its own graceful teardown)" if pid else
                       "is done: tell your human to close it") + "; the human opens Herdr with `herdr` (tab muse-daemon)"
                       " and adds machines with `herdr machine add <ssh-target>`")
    return payload


def cmd_start(args):
    data, entry = consent(args.registry, args.consent_token, args.by)
    return start_step(args, data, entry, entry.get("answer") if entry.get("answer") == "installed" else "yes")


def verify_install(argv):
    """`herdr --version` after the installer, through the one search path
    (the process PATH plus ~/.local/bin, the published installer's target)."""
    found = which_herdr(argv)
    if not found:
        return None, "herdr is still not on PATH after the installer"
    code, out, err = herdr_call(argv, "--version")
    if code != 0:
        return None, f"herdr --version: exit {code}: {(err or out).strip()[:200]}"
    return out.strip(), None


def cmd_install(args):
    data, entry = consent(args.registry, args.consent_token, args.by)
    argv = herdr_command()
    if which_herdr(argv):
        raise Refused("already_installed", f"herdr is already on PATH ({which_herdr(argv)}); nothing was downloaded",
                      "run the start verb with the same consent flags")
    log_path = os.path.join(os.path.dirname(args.registry) or ".", "herdr-install.log")
    command = install_command()
    payload = {"host": host_name(), "install_command": command, "log": log_path}
    try:
        log = open(log_path, "ab")  # noqa: SIM115
    except OSError:
        log = subprocess.DEVNULL
    try:
        proc = subprocess.Popen(["sh", "-c", command], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True, env=child_env())
    except OSError as error:
        raise Failed("install_failed", f"the installer could not start: {error}", "say one line; continue in tmux")
    finally:
        if log is not subprocess.DEVNULL:
            log.close()
    try:
        code = proc.wait(timeout=args.install_timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait()
        raise Failed("install_timeout", f"the installer did not finish within {args.install_timeout_s:g}s and was killed (log: {log_path})",
                     "say one line: the Herdr installer timed out; continue in tmux")
    last = ""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().strip().splitlines()
            last = lines[-1] if lines else ""
    except OSError:
        pass
    if code != 0:
        raise Failed("install_failed", f"the installer exited {code} (log: {log_path}): {last[:200]}",
                     "say one line: the Herdr installer failed; continue in tmux")
    version, problem = verify_install(argv)
    if problem:
        raise Failed("install_failed", f"{problem} (log: {log_path})", "say one line: Herdr did not install; continue in tmux")
    entry.update(answer="installed", at=utc_now(), by=args.by, daemon_session_id=args.daemon_session_id,
                 installed={"version": version, "at": utc_now(), "command": command})
    save_host(args.registry, data, payload)  # `installed` is written at verify time and survives a failed start step
    result = start_step(args, data, entry, "installed")
    result.update(installed=version, install_command=command, log=log_path)
    if "unrecorded" in payload:
        result.setdefault("unrecorded", payload["unrecorded"])
    return result


def cmd_status(args):
    payload = detect(args.registry, args.daemon_session_id, mint=False)
    payload["outcome"] = "status"
    payload["next"] = "read-only: the record and the detection; `start` (the registry) makes the offer"
    return payload


def cmd_detect(args):
    return detect(args.registry, args.daemon_session_id, reopen=args.reopen)


def emit(payload, code=EXIT_OK):
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()
    return code


def build_parser():
    parser = argparse.ArgumentParser(prog="herdr_bootstrap.py", description=__doc__.splitlines()[0])
    parser.add_argument("--registry", default=None, help="the registry path (default: the daemon's, MUSE_DAEMON_REGISTRY or XDG)")
    sub = parser.add_subparsers(dest="command")

    def common(p):
        p.add_argument("--daemon-session-id", default=None, help="this daemon's session id (from the session_identity reminder)")

    detect_p = sub.add_parser("detect")
    common(detect_p)
    detect_p.add_argument("--reopen", action="store_true", help="the human asked for Herdr again: ignore a recorded no and this start's marker")
    status_p = sub.add_parser("status")
    common(status_p)

    def action(p):
        common(p)
        p.add_argument("--consent-token", required=True, help="the token start minted with the offer")
        p.add_argument("--by", required=True, help="the human's own words that answered the ask")

    decline_p = sub.add_parser("decline")
    action(decline_p)

    def start_flags(p):
        action(p)
        p.add_argument("--words", default=None, help="the connect words this daemon was started with (the new pane's `/daemon <words>`)")
        p.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S, help="seconds to wait for a started Herdr server (default 20)")
        p.add_argument("--no-retire", action="store_true", help="do not end the calling daemon after the hand-off")
        p.add_argument("--retire-pid", type=int, default=None, help="the daemon process to retire (default: the nearest muse/tbh ancestor)")
        p.add_argument("--retire-wait-s", type=float, default=5.0, help="seconds to wait for the retired process to exit before the line is printed (default 5)")

    start_p = sub.add_parser("start")
    start_flags(start_p)
    install_p = sub.add_parser("install")
    start_flags(install_p)
    install_p.add_argument("--install-timeout-s", type=float, default=DEFAULT_INSTALL_TIMEOUT_S,
                           help="seconds the installer may run before its process group is killed (default 300)")
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        if error.code == 0:
            return 0
        return emit({"outcome": "usage", "error": "usage", "message": "invalid arguments",
                     "next": "verbs: detect, status, decline, start, install; flags in the reference"}, EXIT_USAGE)
    if not args.command:
        return emit({"outcome": "usage", "error": "usage", "message": "missing verb",
                     "next": "verbs: detect, status, decline, start, install"}, EXIT_USAGE)
    if not args.registry:
        args.registry = registry_module().registry_path()
    try:
        if args.command == "detect":
            payload = cmd_detect(args)
        elif args.command == "status":
            payload = cmd_status(args)
        elif args.command == "decline":
            payload = cmd_decline(args)
        elif args.command == "start":
            payload = cmd_start(args)
        else:
            payload = cmd_install(args)
    except Refused as error:
        return emit({"outcome": error.outcome, "error": error.outcome, "message": str(error), "next": error.next_hint,
                     **error.extra}, error.code)
    except Exception as error:  # noqa: BLE001 - never a traceback on the caller's stdout
        return emit({"outcome": "internal", "error": "internal", "message": f"{type(error).__name__}: {error}",
                     "next": "report this line; nothing else changed"}, EXIT_INTERNAL)
    return emit(payload)


if __name__ == "__main__":
    sys.exit(main())
