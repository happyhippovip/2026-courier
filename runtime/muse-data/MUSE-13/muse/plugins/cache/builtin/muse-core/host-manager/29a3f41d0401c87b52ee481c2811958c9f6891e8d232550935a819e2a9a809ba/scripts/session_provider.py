"""One session interface, three modes (ADR 41038 D1, D2, D3, D5; #41038).

The `agents` skill — and any other caller of host-manager — speaks exactly
six actions to a thread's session, whatever runs it:

    open · send · read · pending · close · attach_line

Each MODE is one implementation of those six, a `SessionProvider`:

    herdr  (A) a TUI in a Herdr tab on this machine          — lane_runtime.py
    tmux   (B) a TUI in a tmux pane on this machine          — lane_runtime.py
    msp    (C) a session on an MSP host, no TUI; transport   — msp_provider.py
               today: the mailbox CLI (`muse hosts|start|send|steer|
               pending|approval decide|watch|tail`)

`lane_runtime.py` registers `herdr` and `tmux` by wrapping today's window
code (tab creation, names, workspace close, the attach command are not
edited: ADR 41038 D5); the msp provider registers itself under `msp` through
`register()` when its module is present. Nothing here starts a process.

The contract, action by action (every receipt is host-manager's one JSON
shape — `outcome`, `provider`, `ref`, `capabilities`, `progress`, `next`,
plus `receipt` on a write — and the exit table below; ADR 38715 D4):

  open(request)        -> {outcome: "opened", identity: {provider, server,
                           ref, cwd, engine}, mode, mode_why,
                           mode_line: "mode=<x> (<why>)", attach: <line>,
                           receipt}
                           request: {name, cwd, engine, engine_args, brief
                           (path or None), unattended, env: [K=V…], label,
                           workspace_label, host (mode C: the MSP host id)}
  send(session, body, typed=False, automated=False)
                       -> {outcome: "sent", delivery: "message"|"typed",
                           session_receipt (the session's own receipt:
                           locally the `muse session-message send --json`
                           line, remotely the transport's command id and
                           receipt), receipt}
                           | {outcome: "held"} the session holds the message
                           for its own admission (a human in it allows it)
                           | a stop: `next` names today's typed form; the
                           helper never retries a message as keystrokes
  read(session, lines=200, tail=False)
                       -> {outcome: "read", lines: […], group:
                           working|idle|waiting-on-you|unknown}
  pending(session, decide=None)
                       -> {outcome: "pending", items: [{id, kind, text,
                           decide: "available"|"not_available"}], attach}
                           decide=(id, "allow"|"deny") -> outcome
                           "decided" | "already_resolved" | "not_available"
                           (modes A and B until #40184: the item names the
                           pane and the attach line; exit 4)
  close(session, confirm=None)
                       -> {outcome: "closed", closed: <what ended>}
                           | {outcome: "not_found"} on a repeat
  attach_line(session) -> one string: the command or click that puts a
                           human in front of the session (mode C: the tail)

Exit codes (the same table as lane_runtime.py; a test pins them equal):
  0 ok · 2 usage · 3 refused by a guard · 4 unsupported by this mode
  (`mode_unavailable`, `unsupported_by_provider`) · 5 a human step ·
  6 evidence unavailable / a pinned local mode installed but silent
  (`provider_unreachable`), the msp pin's host or transport unreachable
  (`mode_unreachable`, `transport_unreachable`) · 7 internal

The selection ladder (ADR 41038 D3), top-down, first rule wins — `infer_mode`
below is that ladder as a pure function; `lane_runtime.py` feeds it what its
provider detection found:

  1. a pin — `--mode herdr|tmux|msp` on the verb, or the project setting
     (`agents set mode <x>`) — is used, or the verb stops: `mode_unavailable`
     (exit 4) when the mode is not on this host (`fallback` names the
     ladder's own choice, omitted when that choice is the pinned mode
     itself), `provider_unreachable` (exit 6) when it is here but does not
     answer (`mode_unreachable` is the msp pin's word for a host it cannot
     reach); never a silent substitute;
  2. `--host <machine>`: `msp` when that machine advertises MSP (`muse hosts`
     lists it as authorized and MSP-ready); otherwise the remote ssh + tmux
     path is fleet-manager's (ADR 38715 D6), so host-manager stops and names
     it (`mode_unavailable`, exit 4) — it never emulates a remote session.
     With the protocol flag on (Amendment 3), this machine is one of those
     hosts: a bare `open` (no pin, no `--host`) is `msp` when the provider
     is ready and `muse hosts` lists this machine (`local_host`), with the
     why `this machine advertises MSP`; not listed, not ready, or flag off,
     the arm is not taken and rule 3 answers with today's words;
  3. otherwise today's rule: Herdr when its server runs (a down server is
     started), else tmux.

Every `open` receipt carries `mode=<x> (<why>)`.

The protocol path (ADR 41038 D5) ships behind `TBH_AGENTS_SESSION_PROTOCOL`:
off (unset) is today's behaviour byte for byte (the ladder included: a golden
table in the provider suite pins it); on, `send` without `--type` is the
session message, `pending` lists what the session waits on, and the ladder
reads the local-MSP arm of rule 2.
"""

import os

MODES = ("herdr", "tmux", "msp")
ACTIONS = ("open", "send", "read", "pending", "close", "attach_line")

PROTOCOL_ENV = "TBH_AGENTS_SESSION_PROTOCOL"
PROTOCOL_ON = ("1", "on", "true", "yes")

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_UNSUPPORTED = 4
EXIT_NEEDS_USER_ACTION = 5
EXIT_EVIDENCE = 6
EXIT_INTERNAL = 7

# The `why` words an open receipt's `mode=<x> (<why>)` line carries, one per
# ladder arm; a caller keys on the mode, a human reads the why.
WHY_PINNED = "pinned by --mode"
WHY_HOST_MSP = "host {host} advertises MSP"
WHY_LOCAL_MSP = "this machine advertises MSP"
WHY_HERDR_RUNNING = "Herdr server running"
WHY_HERDR_STARTED = "Herdr server started"
WHY_HERDR_IN_PANE = "inside a Herdr pane"
WHY_TMUX_FALLBACK = "tmux; no Herdr server"


def protocol_enabled(env=None):
    """Whether the protocol path is on: `TBH_AGENTS_SESSION_PROTOCOL` is one
    of 1/on/true/yes (case-insensitive). Unset or anything else is off."""
    value = (env if env is not None else os.environ).get(PROTOCOL_ENV, "")
    return value.strip().lower() in PROTOCOL_ON


def mode_line(mode, why):
    """The one line every `open` receipt carries: `mode=<x> (<why>)`."""
    return f"mode={mode} ({why})"


class ProviderStop(Exception):
    """A provider's refusal or unavailability, as the verb's one line:
    `outcome`, the message, the `next` step, the exit code, extra fields."""

    def __init__(self, outcome, message, next_hint, exit_code, **extra):
        super().__init__(message)
        self.outcome = outcome
        self.next = next_hint
        self.exit_code = exit_code
        self.extra = extra


class Unsupported(ProviderStop):
    """An action this mode has no way to do (`unsupported_by_provider`, exit
    4); `next` names the alternative."""

    def __init__(self, mode, action, next_hint, **extra):
        super().__init__("unsupported_by_provider", f"mode {mode} cannot {action}; host-manager never emulates it",
                         next_hint, EXIT_UNSUPPORTED, error=action, **extra)


class SessionProvider:
    """The six actions. A mode overrides what it can do; what it leaves to
    this base answers `unsupported_by_provider` naming the action."""

    mode = None
    capabilities = ()

    def open(self, request):
        raise Unsupported(self.mode, "open", "open the session with another --mode")

    def send(self, session, body, typed=False, automated=False):
        raise Unsupported(self.mode, "send", "attach and type it yourself: run the session's attach line")

    def read(self, session, lines=200, tail=False):
        raise Unsupported(self.mode, "read", "attach and look: run the session's attach line")

    def pending(self, session, decide=None):
        raise Unsupported(self.mode, "pending", "attach and answer it yourself: run the session's attach line")

    def close(self, session, confirm=None):
        raise Unsupported(self.mode, "close", "end the session from its own window")

    def attach_line(self, session):
        raise Unsupported(self.mode, "attach_line", "the session has no attach line in this mode")

    def discover(self):
        """`(ready, hosts, why)`: whether this mode can open anything here and
        which machine ids it reaches — the ladder's rule 2 input. Local modes
        have no hosts; the msp provider answers from `muse hosts`."""
        return False, (), f"mode {self.mode} has no host discovery"


_REGISTRY = {}


def register(name, provider):
    """Add one mode. `provider` is a `SessionProvider` subclass or instance;
    the msp module calls this for `msp`, lane_runtime.py for `herdr` and
    `tmux`. A second registration of the same name replaces the first (a test
    swaps a fake in); an unknown mode name is a programming error."""
    if name not in MODES:
        raise ValueError(f"unknown mode {name!r}: modes are {', '.join(MODES)}")
    missing = [action for action in ACTIONS if not callable(getattr(provider, action, None))]
    if missing:
        raise ValueError(f"provider for {name!r} lacks {', '.join(missing)}")
    _REGISTRY[name] = provider
    return provider


def registered():
    """The modes that have a provider here, in ladder order."""
    return tuple(mode for mode in MODES if mode in _REGISTRY)


def provider(name):
    """The provider for a mode, or a `mode_unavailable` stop (exit 4); mode
    C behind the flag (ADR 41038 D5, D6 ②) names the flag when it is off."""
    found = _REGISTRY.get(name)
    if found is None:
        behind_flag = name == "msp" and not protocol_enabled()
        raise ProviderStop("mode_unavailable",
                           f"mode msp is behind {PROTOCOL_ENV} (off in this shell); no msp provider is registered" if behind_flag
                           else f"no {name} provider is registered in this host-manager",
                           (f"set {PROTOCOL_ENV}=1, or " if behind_flag else "") + f"use one of: {', '.join(registered()) or 'none'}",
                           EXIT_UNSUPPORTED, error=name, modes=list(registered()))
    return found


def infer_mode(pin=None, host=None, *, msp_hosts=(), herdr_reachable=False, herdr_installed=False,
               herdr_started=False, tmux_installed=True, in_pane=False, msp_ready=False, protocol=False, local_host=None,
               msp_why=None):
    """ADR 41038 D3 as one pure function: `(mode, why)` or a `ProviderStop`.

    `pin` is `--mode` (None or "auto" = no pin); `host` is `--host`;
    `msp_hosts` the machine ids `muse hosts` lists as authorized and
    MSP-ready; `msp_ready` whether the msp provider can be used here at all
    (registered and its CLI present); the Herdr/tmux facts come from
    lane_runtime's provider detection. A local pin that is not installed is
    rule 1's `mode_unavailable` with `fallback`; one installed but silent
    keeps today's `provider_unreachable`; the msp pin and the host rule are
    the new arms. `protocol` is the
    `TBH_AGENTS_SESSION_PROTOCOL` flag and `local_host` this machine's id as
    `muse hosts` would list it (D3 Amendment 3): with the flag on, an
    unpinned open with no `host` is `msp` when `local_host` is in
    `msp_hosts` and the provider is ready; with the flag off mode C is not
    available at all — an msp pin or a named host stops naming the flag
    (`mode_unavailable`, exit 4) and the rest of the table is the old path.
    `msp_why` is discovery's own reason when the provider is not ready (a
    CLI missing from PATH and one without the `muse` verbs are told apart).
    """
    if pin in ("auto", ""):
        pin = None
    if pin is not None and pin not in MODES:
        raise ProviderStop("usage", f"--mode takes {'|'.join(MODES)}, got {pin!r}",
                           "repeat the verb with one of those modes", EXIT_USAGE, error="--mode")
    fallback = ("herdr", WHY_HERDR_RUNNING) if herdr_reachable else ("tmux", WHY_TMUX_FALLBACK)
    # 0. mode C is behind the flag (ADR 41038 D5; D3 Amendment 3): off, an msp pin or a named host refuses naming it
    if not protocol and (pin == "msp" or (host and pin is None)):
        raise ProviderStop("mode_unavailable",
                           (f"--mode msp was pinned but mode msp is behind {PROTOCOL_ENV} (off in this shell)" if pin == "msp" else
                            f"host {host!r} needs mode msp, which is behind {PROTOCOL_ENV} (off in this shell); host-manager opens "
                            "sessions on this machine only, and the remote ssh + tmux path is fleet-manager's") + "; nothing was started",
                           f"set {PROTOCOL_ENV}=1, or " + (f"drop the pin: the ladder's fallback here is {fallback[0]} ({fallback[1]})" if pin == "msp"
                                                          else f"`fleet-manager open {host}` (the remote ssh + tmux path)"),
                           EXIT_UNSUPPORTED, error="msp" if pin == "msp" else "host", fallback=fallback[0], flag=PROTOCOL_ENV,
                           **({"host": host} if host else {}))
    # 1. a pin
    if pin == "msp":
        if "msp" not in registered() or not msp_ready:
            raise ProviderStop("mode_unavailable", "--mode msp was pinned but no MSP provider can run here ("
                               + ("the msp provider is not registered" if "msp" not in registered() else
                                  msp_why or "the mailbox CLI on this host cannot answer `muse hosts`") + ")",
                               f"drop the pin: the ladder's fallback here is {fallback[0]} ({fallback[1]})",
                               EXIT_UNSUPPORTED, error="msp", fallback=fallback[0])
        if host and host not in msp_hosts:
            raise ProviderStop("mode_unreachable", f"--mode msp was pinned but host {host!r} is not an authorized, "
                               "MSP-ready host in `muse hosts`; nothing was started",
                               f"authorize it (`muse hosts` must list it), or open it through fleet-manager: `fleet-manager open {host}`",
                               EXIT_EVIDENCE, error="msp", host=host)
        return "msp", WHY_PINNED
    if pin in ("herdr", "tmux"):
        if host:
            raise ProviderStop("mode_unavailable", f"--mode {pin} is a mode of this machine; it cannot open a session on {host!r}",
                               f"`fleet-manager open {host} --mode {pin}` (the remote ssh + tmux path), or drop --host", EXIT_UNSUPPORTED,
                               error="host", host=host)
        if pin == "herdr" and not herdr_reachable and not herdr_installed:
            # Rule 1: not on this host is `mode_unavailable` with the ladder's
            # own choice as `fallback`; the detection word stays in `error`
            # (QA r22 N-1 / N-HM1).
            raise ProviderStop("mode_unavailable", "--mode herdr was pinned but Herdr is not installed",
                               "install Herdr yourself (host-manager never installs it), or run the same verb with"
                               f" --mode tmux (the ladder's fallback here is {fallback[0]})",
                               EXIT_UNSUPPORTED, error="herdr_not_installed", fallback=fallback[0])
        if pin == "herdr" and not herdr_reachable:
            raise ProviderStop("provider_unreachable", "--mode herdr was pinned but its server does not answer",
                               "start the herdr server (`herdr server`), or run the same verb with --mode tmux",
                               EXIT_EVIDENCE, error="herdr_unreachable")
        if pin == "tmux" and not tmux_installed:
            # Rule 1 as for the herdr pin; the ladder's own choice is named only when it is not tmux itself
            raise ProviderStop("mode_unavailable", "--mode tmux was pinned but tmux is not installed",
                               "install tmux, or run the same verb with --mode herdr", EXIT_UNSUPPORTED, error="tmux_not_installed",
                               **({"fallback": "herdr"} if herdr_reachable else {}))
        return pin, WHY_PINNED
    # 2. another machine
    if host:
        if host in msp_hosts and "msp" in registered() and msp_ready:
            return "msp", WHY_HOST_MSP.format(host=host)
        raise ProviderStop("mode_unavailable", f"host {host!r} advertises no MSP (not in `muse hosts`); host-manager opens "
                           "sessions on this machine only, and the remote ssh + tmux path is fleet-manager's",
                           f"`fleet-manager open {host}` (the remote ssh + tmux path), or authorize the host for MSP", EXIT_UNSUPPORTED,
                           error="host", host=host, fallback="tmux")
    # 2, Amendment 3 (flag on only): this machine is one of the named hosts
    if protocol and local_host and local_host in msp_hosts and "msp" in registered() and msp_ready:
        return "msp", WHY_LOCAL_MSP
    # 3. today's rule
    if in_pane:
        return "herdr", WHY_HERDR_IN_PANE
    if herdr_reachable:
        return "herdr", WHY_HERDR_STARTED if herdr_started else WHY_HERDR_RUNNING
    return "tmux", WHY_TMUX_FALLBACK
