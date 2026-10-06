"""Controller-facing service layer (lane L3).

Wiring only: it speaks the documented controller API
(``tests/golden/README.md``: ``/v1/health``, ``/v1/claim``, ``/v1/start``,
``/v1/heartbeat``, ``/v1/result``, ``/v1/events`` SSE) with the standard
library, maps claims to :class:`ExecutionSpec`, and delivers results with a
durable outbox. Every HTTP call is a single attempt with an explicit
timeout; there is no retry loop. An unreachable controller means the result
stays in the outbox, not a storm.

Claim ``spec`` mapping (L2 contract, fail-closed): ``spec`` is declarative,
``{adapter, params, effect_class, timeout_s, effect_key}``. The adapter must
be allowlisted and its params must validate (:mod:`courier_worker.adapter_bridge`);
the host then runs Courier's own adapter runner. A spec that carries ``argv``
is refused: the worker never executes a command supplied by a claim.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import signal
import socket
import sys
import threading
import time
import urllib.parse
from typing import Callable, Optional

from courier_worker import adapter_bridge
from courier_worker.host import (
    DEFAULT_TIMEOUT_S,
    MAX_TIMEOUT_S,
    ExecutionResult,
    ExecutionSpec,
    HostBusy,
    Outcome,
    ResourcePaused,
    SpecError,
    WorkerHost,
    acquire_home_lock,
    outbox_read_all,
    outbox_remove,
    outbox_write,
    release_home_lock,
    run_orphan_gate,
)

REQUEST_TIMEOUT_S = 10.0
STARTUP_HEALTH_ATTEMPTS = 5
STARTUP_HEALTH_SLEEP_S = 1.0
FLUSH_TIMEOUT_S = 3.0
SSE_RECONNECTS = 3
SSE_POLL_S = 0.25  # bounds how long stop() waits for the watcher thread

CANCEL_TYPES = frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})


class ControllerError(RuntimeError):
    """The controller call failed (unreachable, timeout, or 5xx)."""


class ControllerUnreachable(ControllerError):
    """No usable controller at startup; the host exits instead of spinning."""


class StaleDispatch(ControllerError):
    """The controller no longer owns this dispatch (404/409); drop it."""


class ControllerClient:
    """One attempt per call, explicit timeouts, token header always."""

    def __init__(self, base_url: str, token: str, timeout_s: float = REQUEST_TIMEOUT_S):
        parts = urllib.parse.urlparse(base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ControllerError(f"bad controller url: {base_url!r}")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_s = timeout_s

    def _conn(self) -> http.client.HTTPConnection:
        parts = urllib.parse.urlparse(self.base_url)
        cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        return cls(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
                   timeout=self.timeout_s)

    def _call(self, method: str, path: str, body: Optional[dict] = None):
        data = None
        headers = {"X-Courier-Token": self.token, "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body)
            headers["Content-Type"] = "application/json"
        conn = self._conn()
        try:
            conn.request(method, "/v1" + path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
        except (OSError, socket.timeout, http.client.HTTPException) as exc:
            raise ControllerError(f"{method} {path}: {exc}") from exc
        finally:
            conn.close()
        if 500 <= resp.status:
            raise ControllerError(f"{method} {path}: status {resp.status}")
        payload = None
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except ValueError:
                payload = None
        return resp.status, payload

    def health(self) -> bool:
        try:
            status, _ = self._call("GET", "/health")
        except ControllerError:
            return False
        return status == 200

    def claim(self, worker_id: str) -> Optional[dict]:
        try:
            status, payload = self._call("POST", "/claim", {"worker_id": worker_id})
        except ControllerError:
            return None
        if status == 204:
            return None
        if status == 200 and isinstance(payload, dict):
            return payload
        return None

    def start(self, dispatch_id: str) -> None:
        try:
            status, _ = self._call("POST", "/start", {"dispatch_id": dispatch_id})
        except ControllerError as exc:
            raise StaleDispatch(f"start for {dispatch_id} failed: {exc}") from exc
        if status in (404, 409):
            raise StaleDispatch(f"controller rejects dispatch {dispatch_id}: {status}")
        if status != 200:
            raise StaleDispatch(f"start for {dispatch_id}: status {status}")

    def heartbeat(self, worker_id: str, dispatch_ids: list) -> dict:
        status, payload = self._call("POST", "/heartbeat",
                               {"worker_id": worker_id, "dispatch_ids": dispatch_ids})
        if status != 200:
            raise ControllerError(f"heartbeat: status {status}")
        return payload or {}

    def deliver(self, payload: dict) -> str:
        """Send one result. Returns 'accepted', 'stale', or raises."""
        try:
            status, body = self._call("POST", "/result", payload)
        except ControllerError:
            raise
        if status in (404, 409):
            return "stale"
        if status == 200 and isinstance(body, dict) \
                and body.get("status") in ("ACCEPTED_FOR_VERIFY", "ACK_DUPLICATE"):
            return "accepted"
        if status == 200:
            return "accepted"
        raise ControllerError(f"result: status {status}")


def resolve_spec(claim: dict, worker_id: str, artifacts_root: str, heartbeat_s: float,
                 home: Optional[str] = None) -> ExecutionSpec:
    """Map one ``POST /claim`` answer to an executable spec, fail-closed."""
    if not isinstance(claim, dict):
        raise SpecError("claim is not an object")
    task_id = claim.get("task_id")
    dispatch_id = claim.get("dispatch_id")
    attempt = claim.get("attempt")
    ttl_s = claim.get("ttl_s")
    spec = claim.get("spec")
    if not isinstance(task_id, str) or not task_id:
        raise SpecError("claim carries no task_id")
    if not isinstance(dispatch_id, str) or not dispatch_id:
        raise SpecError("claim carries no dispatch_id")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise SpecError("claim carries no valid attempt")
    if not isinstance(ttl_s, (int, float)) or ttl_s < 1:
        raise SpecError("claim carries no valid ttl_s")
    adapter, params, effect_key = adapter_bridge.validate_request(spec)
    home = home or os.path.dirname(os.path.abspath(artifacts_root))
    timeout_s = spec.get("timeout_s") or DEFAULT_TIMEOUT_S
    if not isinstance(timeout_s, (int, float)) or not 0 < timeout_s <= MAX_TIMEOUT_S:
        raise SpecError("claim spec timeout_s is out of bounds")
    claim_heartbeat = claim.get("heartbeat_s")
    if isinstance(claim_heartbeat, (int, float)) and claim_heartbeat > 0:
        heartbeat_s = min(heartbeat_s, float(claim_heartbeat))
    result_id = "r-" + dispatch_id
    if len(result_id) > 200:
        raise SpecError("dispatch_id leaves no room for a result_id within 200 chars")
    return ExecutionSpec(
        task_id=task_id, attempt=attempt, dispatch_id=dispatch_id, worker_id=worker_id,
        result_id=result_id, argv=adapter_bridge.runner_argv(home, dispatch_id),
        timeout_s=float(timeout_s), lease_ttl_s=float(ttl_s),
        artifact_dir=os.path.join(artifacts_root, dispatch_id), heartbeat_s=heartbeat_s,
        adapter=adapter, params=params, effect_key=effect_key)


def _artifact_prefix(artifact_dir: str, home: Optional[str]) -> str:
    """``artifacts/<dispatch>/`` when the artifact dir lies inside home, else ''."""
    if not home:
        return ""
    rel = os.path.relpath(os.path.abspath(artifact_dir), os.path.abspath(home))
    if rel == os.curdir or rel.startswith(os.pardir) or os.path.isabs(rel):
        return ""
    return rel.replace(os.sep, "/") + "/"


def build_result_payload(result: ExecutionResult, report: Optional[dict] = None,
                         home: Optional[str] = None) -> dict:
    """The result the controller verifies; never claims more than the run proved.

    A bridged run (``result.spec.adapter`` set) that exited 0 is only a
    success if the runner wrote a report saying so; a missing report is a
    non-retryable failure. Artifact paths are relative to ``home`` when given,
    which is the scope the controller's verifier reads from.
    """
    prefix = _artifact_prefix(result.spec.artifact_dir, home)
    outcome, retryable, reason = result.l2_outcome, result.retryable, None
    if outcome != "success":
        reason = f"worker outcome: {result.outcome}"
    elif result.spec.adapter is not None:
        if report is None:
            outcome, retryable, reason = "failure", False, "adapter runner produced no structured result"
        elif report["outcome"] != "success":
            outcome, retryable = "failure", bool(report.get("retryable", False))
            reason = str(report.get("reason") or "adapter reported failure")[:500]
    payload = {
        "dispatch_id": result.spec.dispatch_id,
        "result_id": result.spec.result_id,
        "artifacts": [{"path": prefix + a.path.replace(os.sep, "/"), "sha256": a.sha256}
                      for a in result.artifacts],
        "outcome": outcome,
    }
    if outcome != "success":
        # Only failures carry retryability; a success is exactly the golden
        # wire shape, so an identical re-send is acknowledged as a duplicate.
        payload["retryable"] = retryable
        if reason:
            payload["reason"] = reason
    return payload


def build_spec_failure_payload(dispatch_id: str, result_id: str, reason: str) -> dict:
    return {"dispatch_id": dispatch_id, "result_id": result_id,
            "artifacts": [], "outcome": "failure", "retryable": False, "reason": reason}


class CancelWatcher:
    """Follow ``GET /v1/events`` (SSE) for cancellations of our task.

    Best-effort by design: after SSE_RECONNECTS failed attempts the watcher
    gives up and the run stays bounded by lease and timeout instead. The
    controller remains the authority; this only shortens cancel latency.
    """

    def __init__(self, base_url: str, token: str, task_id: str, timeout_s: float = REQUEST_TIMEOUT_S):
        self.base_url = base_url
        self.token = token
        self.task_id = task_id
        self.timeout_s = timeout_s
        self._cancelled = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.degraded = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._follow, name="courier-cancel-watch",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def _follow(self) -> None:
        attempts = 0
        while not self._stop.is_set() and attempts <= SSE_RECONNECTS:
            try:
                self._subscribe()
                return  # clean EOF while stopping
            except Exception:
                attempts += 1
                if attempts > SSE_RECONNECTS:
                    self.degraded = True
                    return
                self._stop.wait(1.0)

    def _subscribe(self) -> None:
        # Raw socket with a short poll instead of a blocking http.client read:
        # a blocked read held the socket and this thread for timeout_s after
        # the run ended (Windows golden handle leak), and neither shutdown()
        # nor a timed-out SocketIO can end it portably. The controller streams
        # with Connection: close and no chunking (courier_core/serve.py).
        parts = urllib.parse.urlparse(self.base_url)
        host = parts.hostname or "127.0.0.1"
        port = parts.port or (443 if parts.scheme == "https" else 80)
        sock = socket.create_connection((host, port), timeout=self.timeout_s)
        try:
            if parts.scheme == "https":
                import ssl
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            sock.sendall((f"GET /v1/events HTTP/1.1\r\nHost: {host}:{port}\r\n"
                          f"X-Courier-Token: {self.token}\r\nAccept: text/event-stream\r\n"
                          "Connection: close\r\n\r\n").encode())
            sock.settimeout(SSE_POLL_S)
            header_deadline = time.monotonic() + self.timeout_s
            buf = b""
            in_body = False
            data_lines: list = []
            while not self._stop.is_set() and not self._cancelled.is_set():
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    if not in_body and time.monotonic() > header_deadline:
                        raise ControllerError("sse: no response headers")
                    continue  # quiet stream; re-check stop/cancel
                if not chunk:
                    return
                buf += chunk
                if not in_body:
                    if b"\r\n\r\n" not in buf:
                        if len(buf) > 65536:
                            raise ControllerError("sse: oversized headers")
                        continue
                    head, buf = buf.split(b"\r\n\r\n", 1)
                    status = head.split(b"\r\n", 1)[0].split()
                    code = status[1].decode("ascii", "replace") if len(status) > 1 else "?"
                    if code != "200":
                        raise ControllerError(f"sse: status {code}")
                    if b"transfer-encoding: chunked" in head.lower():
                        raise ControllerError("sse: chunked stream not supported")
                    in_body = True
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").strip()
                    if text == "":
                        self._dispatch_event(data_lines)
                        data_lines = []
                    elif text.startswith("data:"):
                        data_lines.append(text[5:].strip())
                    # ":" comments (keep-alive), "id:" and "event:" need no action
        finally:
            sock.close()

    def _dispatch_event(self, data_lines: list) -> None:
        if not data_lines:
            return
        try:
            data = json.loads("\n".join(data_lines))
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        inner = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        event_type = data.get("type") or data.get("event_type") or inner.get("type")
        task_id = data.get("task_id") or inner.get("task_id")
        if event_type in CANCEL_TYPES and task_id == self.task_id:
            self._cancelled.set()


class WorkerLoop:
    """Claim, run, deliver, repeat until the stop event is set."""

    def __init__(self, home: str, base_url: str, worker_id: str, heartbeat_s: float,
                 engine: Optional[WorkerHost] = None,
                 client_factory: Optional[Callable[[], ControllerClient]] = None):
        self.home = home
        self.base_url = base_url
        self.worker_id = worker_id
        self.heartbeat_s = heartbeat_s
        self.engine = engine or WorkerHost(home)
        self._client_factory = client_factory or self._default_client
        self._client: Optional[ControllerClient] = None
        self._watchers: dict = {}

    def _default_client(self) -> ControllerClient:
        token_path = os.path.join(self.home, "run", "controller.token")
        try:
            with open(token_path, encoding="utf-8") as fh:
                token = fh.read().strip()
        except OSError as exc:
            raise ControllerUnreachable(f"no controller token at {token_path}: {exc}") from exc
        if not token:
            raise ControllerUnreachable("controller token file is empty")
        return ControllerClient(self.base_url, token)

    def artifacts_root(self) -> str:
        return os.path.join(self.home, "artifacts")

    # -- one bounded step ------------------------------------------------------
    def flush_outbox(self, timeout_s: float = FLUSH_TIMEOUT_S) -> int:
        """Deliver every pending result once. Returns the remaining count."""
        client = self._client or self._client_factory()
        self._client = client
        remaining = 0
        for _path, payload in outbox_read_all(self.home):
            try:
                client.deliver(payload)
            except ControllerError:
                remaining += 1
                continue
            outbox_remove(self.home, payload["dispatch_id"])  # accepted AND stale
        return remaining

    def iterate(self, stop: threading.Event) -> str:
        """Run one claim-execute-deliver cycle. Never loops by itself."""
        try:
            self.flush_outbox()
        except ControllerError:
            return "idle"
        client = self._client or self._client_factory()
        self._client = client
        claim = client.claim(self.worker_id)
        if claim is None:
            return "idle"
        try:
            spec = resolve_spec(claim, self.worker_id, self.artifacts_root(), self.heartbeat_s,
                                home=self.home)
        except SpecError as exc:
            payload = build_spec_failure_payload(
                str(claim.get("dispatch_id", "")), "r-" + str(claim.get("dispatch_id", "")),
                f"spec-invalid: {exc}")
            self._deliver_payload(payload)
            return "spec-rejected"
        adapter_bridge.write_request(self.home, spec)
        try:
            client.start(spec.dispatch_id)
        except StaleDispatch:
            adapter_bridge.cleanup(self.home, spec.dispatch_id)
            return "stale"
        watcher = CancelWatcher(self.base_url, client.token, spec.task_id,
                                timeout_s=max(self.heartbeat_s, 1.0))
        self._watchers[spec.dispatch_id] = watcher
        watcher.start()
        try:
            result = self.engine.run_once(
                spec,
                on_heartbeat=lambda _elapsed: self._send_heartbeat(client, spec),
                is_cancelled=lambda: watcher.cancelled() or stop.is_set())
        finally:
            watcher.stop()
            self._watchers.pop(spec.dispatch_id, None)
        if result.outcome == Outcome.CANCELLED and not watcher.cancelled():
            # Host shutdown, not a task cancel: the attempt's effect is unknown, so
            # report nothing and let the lease expire. The controller then retries
            # an idempotent task and BLOCKs anything else; a fabricated failure
            # here would wrongly FAIL the task.
            adapter_bridge.cleanup(self.home, spec.dispatch_id)
            return "abandoned"
        report = adapter_bridge.read_report(self.home, spec.dispatch_id)
        self._deliver_payload(build_result_payload(result, report, home=self.home))
        adapter_bridge.cleanup(self.home, spec.dispatch_id)
        if result.outcome == Outcome.CANCELLED:
            # The tree is reaped: a heartbeat without this dispatch is the stop
            # confirmation the controller needs to journal TASK_CANCELLED.
            try:
                client.heartbeat(self.worker_id, [])
            except ControllerError:
                pass
        return "delivered"

    def _send_heartbeat(self, client: ControllerClient, spec: ExecutionSpec) -> bool:
        payload = client.heartbeat(self.worker_id, [spec.dispatch_id])
        if spec.dispatch_id in payload.get("cancel", []) or spec.dispatch_id in payload.get("stop", []):
            watcher = self._watchers.get(spec.dispatch_id)
            if watcher:
                watcher._cancelled.set()
        return True

    def _deliver_payload(self, payload: dict) -> None:
        outbox_write(self.home, payload)
        try:
            self._client.deliver(payload)
        except ControllerError:
            return  # stays in the outbox for the next flush; no retry here
        outbox_remove(self.home, payload["dispatch_id"])  # accepted AND stale

    # -- owned run ---------------------------------------------------------------
    def run(self, stop: Optional[threading.Event] = None) -> int:
        stop = stop or threading.Event()
        lock_fd = acquire_home_lock(self.home)
        try:
            run_orphan_gate(self.home)
            client = self._default_client()
            self._client = client
            for _ in range(STARTUP_HEALTH_ATTEMPTS):
                if client.health():
                    break
                if stop.is_set():
                    return 0
                stop.wait(STARTUP_HEALTH_SLEEP_S)
            else:
                if not client.health():
                    raise ControllerUnreachable(
                        f"controller at {self.base_url} unhealthy after "
                        f"{STARTUP_HEALTH_ATTEMPTS} attempts")
            while not stop.is_set():
                try:
                    action = self.iterate(stop)
                except ControllerError:
                    action = "idle"
                except HostBusy:
                    return 0
                except ResourcePaused as exc:
                    print(f"courier_worker.service: paused due to resource pressure: {exc}", file=sys.stderr)
                    action = "idle"
                if action == "idle":
                    stop.wait(self.heartbeat_s)
            try:
                remaining = self.flush_outbox()
            except ControllerError:
                remaining = len(outbox_read_all(self.home))
            return 0 if remaining == 0 else 1
        finally:
            release_home_lock(lock_fd)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="courier_worker.host",
                                     description="Bounded Courier v1 worker host (single-flight).")
    parser.add_argument("--home", default=os.environ.get("COURIER_HOME", os.getcwd()))
    parser.add_argument("--controller", required=True)
    parser.add_argument("--max-tasks", type=int, default=1)
    parser.add_argument("--heartbeat", type=float, default=2.0)
    parser.add_argument("--worker-id", default=f"worker-{os.getpid()}")
    args = parser.parse_args(argv)
    if args.max_tasks != 1:
        parser.error("--max-tasks supports exactly 1 (single-flight ownership)")
        return 2
    if not 0.2 <= args.heartbeat <= 30.0:
        parser.error("--heartbeat must be within [0.2, 30.0]")
        return 2
    stop = threading.Event()

    def _handle_signum(_signum, _frame):
        stop.set()

    for signame in ("SIGTERM", "SIGINT", "SIGBREAK"):
        signum = getattr(signal, signame, None)
        if signum is not None:
            try:
                signal.signal(signum, _handle_signum)
            except (OSError, ValueError):
                pass
    loop = WorkerLoop(args.home, args.controller, args.worker_id, args.heartbeat)
    try:
        return loop.run(stop)
    except HostBusy as exc:
        print(f"courier_worker.host: {exc}", file=sys.stderr)
        return 3
    except ControllerUnreachable as exc:
        print(f"courier_worker.host: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
