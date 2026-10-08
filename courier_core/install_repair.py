"""Restore a damaged install without deleting user data.

The install journal and status words come from courier_core.install_state.
This module copies missing runtime and launcher files back from a package
directory, asks the caller to register and start when those are absent, and
reports HEALTHY only when derive_state says so. A second call on a healthy
install does not rewrite the journal.

Scheduler registration and process start are caller hooks. This module does
not talk to Windows, launchd, or the controller.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from courier_core.install_state import (
    FAILED,
    HEALTHY,
    NOT_INSTALLED,
    REPAIR_REQUIRED,
    Evidence,
    InstallJournal,
    JournalUnreadable,
    derive_state,
    status_from_dir,
)

ROUTE = ("PREFLIGHT", "INSTALL", "CONFIGURE", "CONNECT", "VERIFY", "START")


def repair(
    state_dir,
    now: datetime,
    *,
    package_dir,
    observe: Callable[[], Evidence],
    register: Callable[[], bool] | None = None,
    start: Callable[[], dict | None] | None = None,
    launcher_path: str | None = None,
) -> dict[str, Any]:
    """Repair one install directory. ``reported`` is HEALTHY only after a fresh derivation."""
    journal = InstallJournal(state_dir)
    try:
        document = journal.load()
    except JournalUnreadable:
        return _outcome(False, REPAIR_REQUIRED, "JOURNAL_UNREADABLE", noop=True)

    evidence = observe()
    status = derive_state(document, evidence, now) if document is not None else None
    if document is None or status is None or status["state"] == NOT_INSTALLED:
        return _outcome(False, NOT_INSTALLED, None, noop=True)
    if status["state"] == HEALTHY:
        return _outcome(True, HEALTHY, None, noop=True)
    if status["state"] not in (REPAIR_REQUIRED, FAILED):
        return _outcome(False, status["state"], status["reason_code"], noop=True)
    if status["reason_code"] in ("SCHEDULER_PRIVILEGED_PRINCIPAL", "PROCESS_IDENTITY_MISMATCH"):
        return _outcome(False, status["state"], status["reason_code"], noop=True)

    version = document.get("version") or "0"
    repair_version = version if document.get("phase") == "installing" else f"{version}+repair"
    begun = journal.begin(
        repair_version,
        now,
        config_path=document.get("config_path"),
        runtime_path=document.get("runtime_path"),
    )
    if not begun.ok or begun.journal is None:
        current = status_from_dir(state_dir, observe(), now)
        return _outcome(False, current["state"], begun.reason or current["reason_code"], noop=True)

    for name in ROUTE:
        stepped = journal.phase(name, now)
        if not stepped.ok:
            return _fail(journal, state_dir, observe, now, stepped.reason or "REPAIR_UNVERIFIED")

    if not _restore_missing(state_dir, begun.journal, package_dir, launcher_path):
        return _fail(journal, state_dir, observe, now, "RESTORE_FAILED")

    evidence = observe()
    if not evidence.scheduler_registered:
        if register is None or register() is not True:
            return _fail(journal, state_dir, observe, now, "SCHEDULER_UNREGISTERED")
        evidence = observe()
    if not evidence.process_alive:
        identity = start() if start is not None else None
        if not identity:
            return _fail(journal, state_dir, observe, now, "PROCESS_NOT_ALIVE")
        evidence = observe()
    else:
        identity = evidence.process_identity

    finish_at = _finish_at(now, evidence)
    preview_doc = dict(journal.load() or begun.journal)
    preview_doc["phase"] = "complete"
    preview_doc["finished_at"] = _iso(finish_at)
    preview_doc["failure_reason"] = None
    if identity is not None:
        preview_doc["process_identity"] = dict(identity)
    verdict = derive_state(preview_doc, evidence, now)
    if verdict["state"] != HEALTHY:
        return _fail(journal, state_dir, observe, now, verdict["reason_code"] or "REPAIR_UNVERIFIED")

    done = journal.complete(finish_at, process_identity=identity)
    if not done.ok:
        return _fail(journal, state_dir, observe, now, done.reason or "REPAIR_UNVERIFIED")
    final = status_from_dir(state_dir, observe(), now)
    if final["state"] != HEALTHY:
        journal.rollback(now)
        final = status_from_dir(state_dir, observe(), now)
        return _outcome(False, final["state"], final["reason_code"], noop=False)
    return _outcome(True, HEALTHY, None, noop=False)


def _fail(journal: InstallJournal, state_dir, observe, now: datetime, reason: str) -> dict[str, Any]:
    failed = journal.fail(reason, now)
    if not failed.ok:
        current = status_from_dir(state_dir, observe(), now)
        return _outcome(False, current["state"], reason, noop=False)
    final = status_from_dir(state_dir, observe(), now)
    if final["state"] == HEALTHY:
        final = {"state": FAILED, "reason_code": reason}
    return _outcome(False, final["state"], final.get("reason_code") or reason, noop=False)


def _restore_missing(state_dir, document: dict, package_dir, launcher_path: str | None) -> bool:
    """Copy missing components from the package. Existing files and protected dirs stay."""
    protected = set(document.get("protected_dirs") or ("projects", "data"))
    targets = []
    for raw in (document.get("runtime_path"), document.get("config_path"), launcher_path):
        if isinstance(raw, str) and raw and raw not in targets:
            targets.append(raw)
    package = Path(package_dir)
    root = Path(state_dir)
    for raw in targets:
        dest = _destination(root, raw)
        if _hits_protected(root, dest, protected):
            return False
        if dest.exists():
            continue
        source = package / Path(raw).name
        if not source.is_file():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    return True


def _destination(root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return root / path


def _hits_protected(root: Path, dest: Path, protected: set[str]) -> bool:
    try:
        relative = dest.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    return any(part in protected for part in relative.parts[:-1])


def _finish_at(now: datetime, evidence: Evidence) -> datetime:
    """A completion stamp strictly before a confirmation that is already in hand."""
    confirmed = evidence.controller_confirmed_at
    if isinstance(confirmed, datetime) and confirmed.tzinfo is not None and confirmed <= now:
        return confirmed - timedelta(seconds=1)
    return now - timedelta(seconds=1)


def _iso(moment: datetime) -> str:
    from datetime import timezone
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _outcome(ok: bool, state: str, reason: str | None, *, noop: bool) -> dict[str, Any]:
    return {
        "ok": ok,
        "state": state,
        "reason_code": reason,
        "noop": noop,
        "reported": HEALTHY if state == HEALTHY else None,
    }
