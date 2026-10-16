"""Smallest executable "Courier's own computer" loop.

INTENT -> WORKKEY -> HOST SELECTION -> WORK LEASE -> GRANT -> OWNED EXECUTION
-> HEARTBEAT -> EVIDENCE -> ACCEPTED STATE -> CHECKPOINT -> DONE, and after a
device loss: RECOVERY RECEIPT -> NEW ELIGIBLE HOST -> AUTHORITY REVALIDATION
-> CONTINUE FROM THE LAST ACCEPTED STEP.

Each step is a command run as a process Courier owns; a step is accepted
only when its process exits 0 and its declared output exists, and the
accepted fact cites that evidence. Hosts here are local device identities;
the same loop runs unchanged when a host is a real remote machine.
"""
import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass

from courier_runtime.continuation import AcceptedFact, AcceptedLog, Checkpoint, decide
from courier_runtime.grants import GRANTED
from courier_runtime.hosts import Evidence, select
from courier_runtime.lease import StaleLease
from courier_runtime.ownership import OwnedProcess


from pathlib import Path


def is_verbatim_path(p: str | os.PathLike) -> bool:
    """Check whether a path uses Windows verbatim namespace syntax."""
    s = str(p).strip()
    return (
        s.startswith("\\\\?\\")
        or s.startswith("//?/")
        or s.startswith("\\??\\")
        or s.startswith("/??/")
    )


def strip_verbatim(s: str) -> str:
    """Strip Windows verbatim namespace prefix (\\\\?\\, \\\\?\\UNC\\, \\??\\, etc.)."""
    s_clean = str(s).strip()
    prefix = s_clean[:8].replace("/", "\\")
    if prefix.upper().startswith("\\\\?\\UNC\\") or prefix.upper().startswith("\\??\\UNC\\"):
        return "\\\\" + s_clean[8:]
    if s_clean.startswith("\\\\?\\") or s_clean.startswith("//?/") or s_clean.startswith("\\??\\") or s_clean.startswith("/??/"):
        return s_clean[4:]
    return s_clean


def to_verbatim_path(p: str | os.PathLike) -> str:
    """Convert an absolute Windows path to its canonical verbatim (\\\\?\\) format."""
    resolved = normalize_path(p)
    s = str(resolved)
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s.lstrip("\\")
    return "\\\\?\\" + s


class VerbatimPathError(RuntimeError):
    """Raised when verbatim path validation fails closed."""
    pass


def verify_verbatim_path(
    p: str | os.PathLike,
    must_exist: bool = False,
    inside_workdir: str | os.PathLike | None = None,
) -> tuple[bool, str]:
    """Verbindliche Verifikation eines Windows-Verbatim-Pfads.
    
    Prüft:
    1. Pfad ist nicht None, nicht leer/Whitespace, und frei von Null-Bytes.
    2. Startet mit einem anerkannten Windows-Verbatim-Präfix (\\\\?\\, \\\\?\\UNC\\, \\??\\).
    3. Payload nach dem Präfix ist absolut (Laufwerksbuchstabe X:\\ oder UNC \\\\server\\share).
       Relative Pfade unter Verbatim-Präfixen werden abgelehnt.
    4. Falls inside_workdir angegeben: Pfad muss strikt innerhalb des Workspaces liegen.
    5. Falls must_exist=True: Pfad muss im Dateisystem existieren.
    
    Gibt (True, canonical_verbatim_str) zurück bei Erfolg,
    sonst (False, reason).
    """
    if p is None:
        return False, "VERBATIM_PATH_NULL"
    s = str(p).strip()
    if not s:
        return False, "VERBATIM_PATH_EMPTY"
    if "\0" in s:
        return False, "VERBATIM_PATH_NULL_BYTE"

    if not is_verbatim_path(s):
        return False, f"NOT_VERBATIM: path '{s}' does not start with a recognized verbatim prefix"

    stripped = strip_verbatim(s)
    if not (len(stripped) >= 2 and stripped[1] == ":" or stripped.startswith("\\\\")):
        return False, f"VERBATIM_MALFORMED: payload after prefix is not absolute: '{stripped}'"

    if len(stripped) >= 2 and stripped[1] == ":":
        drive = stripped[0]
        if not drive.isalpha():
            return False, f"VERBATIM_INVALID_DRIVE: '{drive}' is not an alphabetic drive letter"

    try:
        norm = normalize_path(s)
    except Exception as e:
        return False, f"VERBATIM_CANONICALIZATION_FAILED: {e}"

    if inside_workdir is not None:
        contained = resolve_workspace_child(inside_workdir, s)
        if contained is None:
            return False, f"VERBATIM_ESCAPES_WORKSPACE: '{s}' escapes workdir '{inside_workdir}'"

    if must_exist:
        if not norm.exists():
            return False, f"VERBATIM_TARGET_NOT_FOUND: '{norm}' does not exist on disk"

    canonical = to_verbatim_path(norm)
    return True, canonical



def extract_windows_drive(p: str | os.PathLike) -> str | None:
    """Extract Windows drive letter (e.g. 'C:') or UNC host prefix from a path."""
    if p is None:
        return None
    s = strip_verbatim(str(p).strip())
    if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
        return s[:2].upper()
    if s.startswith("\\\\"):
        parts = s.lstrip("\\").split("\\")
        if parts and parts[0]:
            return "\\\\" + parts[0].upper()
    return None


def is_drive_scope_breach(workdir: str | os.PathLike, target: str | os.PathLike) -> bool:
    """Check whether target references a different Windows drive or UNC share than workdir."""
    workdir_drive = extract_windows_drive(workdir)
    target_drive = extract_windows_drive(target)
    if workdir_drive and target_drive:
        return workdir_drive.upper() != target_drive.upper()
    if target_drive and not workdir_drive:
        return True
    return False


class DriveScopeBreachError(RuntimeError):
    """Raised when an operation attempts a cross-drive scope breach."""
    pass


def check_drive_scope(workdir: str | os.PathLike, target: str | os.PathLike) -> tuple[bool, str]:
    """Verbindliche Prüfung gegen unautorisierten Laufwerkswechsel (Scopebruch).
    
    Gibt (True, "VALID_DRIVE_SCOPE") zurück bei gleicher Laufwerksbindung,
    sonst (False, reason).
    """
    if is_drive_scope_breach(workdir, target):
        w_drive = extract_windows_drive(workdir) or "LOCAL"
        t_drive = extract_windows_drive(target) or "FOREIGN"
        return False, f"DRIVE_SCOPE_BREACH: target drive '{t_drive}' differs from authorized workspace drive '{w_drive}'"
    return True, "VALID_DRIVE_SCOPE"


def normalize_path(p: str | os.PathLike) -> Path:
    """Normalize and resolve a path, safely handling Windows verbatim prefixes."""
    s = strip_verbatim(str(p).strip())
    return Path(s).resolve()


def is_reparse_point(p: str | os.PathLike) -> bool:
    """Detect Windows NTFS reparse points (junctions, symlinks, appexec links) safely."""
    if p is None:
        return False
    try:
        s = strip_verbatim(str(p).strip())
        if not s:
            return False
        st = os.lstat(s)
        attrs = getattr(st, "st_file_attributes", 0)
        if attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
            return True
        if os.path.islink(s):
            return True
    except (OSError, ValueError):
        pass
    return False


def is_path_confined(target: str | os.PathLike, root: str | os.PathLike) -> bool:
    """Check whether target is strictly contained within root."""
    try:
        t = normalize_path(target)
        r = normalize_path(root)
        if os.name == "nt":
            t_s = str(t).lower().rstrip("\\")
            r_s = str(r).lower().rstrip("\\")
            return t_s == r_s or t_s.startswith(r_s + "\\")
        else:
            return t == r or r in t.parents
    except Exception:
        return False


def find_reparse_points_in_path(
    p: str | os.PathLike,
    stop_at: str | os.PathLike | None = None,
) -> list[Path]:
    """Find all path components from p upwards (stopping at stop_at) that are reparse points."""
    reparse_points: list[Path] = []
    if p is None:
        return reparse_points
    try:
        curr = Path(strip_verbatim(str(p).strip()))
        stop_path = Path(strip_verbatim(str(stop_at).strip())).resolve() if stop_at else None

        while True:
            if is_reparse_point(curr):
                reparse_points.append(curr)
            if stop_path is not None:
                try:
                    curr_res = curr.resolve()
                    if os.name == "nt":
                        if str(curr_res).lower().rstrip("\\") == str(stop_path).lower().rstrip("\\"):
                            break
                    else:
                        if curr_res == stop_path:
                            break
                except Exception:
                    pass
            parent = curr.parent
            if parent == curr:
                break
            curr = parent
    except Exception:
        pass
    return reparse_points


class ReparsePointSecurityError(RuntimeError):
    """Raised when a reparse point violates confinement or security policy."""
    pass


def check_reparse_point_safety(
    p: str | os.PathLike,
    workdir: str | os.PathLike | None = None,
    allow_confined: bool = True,
) -> tuple[bool, str]:
    """Verbindliche Absicherung und Prüfung von Windows-Reparse-Points (Junctions, Symlinks).
    
    Gibt (True, reason) bei sicherem/konformem Pfad, sonst (False, failure_reason).
    """
    if p is None:
        return False, "REPARSE_POINT_ERROR: path is None"

    found = find_reparse_points_in_path(p, stop_at=workdir)
    if not found:
        return True, "NO_REPARSE_POINT"

    for rp in found:
        if not allow_confined:
            return False, f"REPARSE_POINT_DISALLOWED: reparse points forbidden by policy at '{rp}'"

        if workdir is not None:
            try:
                target = rp.resolve()
            except Exception as e:
                return False, f"REPARSE_POINT_CANONICALIZATION_FAILED: cannot resolve '{rp}': {e}"

            if is_drive_scope_breach(workdir, target):
                return False, f"REPARSE_POINT_DRIVE_BREACH: reparse point '{rp}' targets '{target}' across drives"

            if not is_path_confined(target, workdir):
                return False, f"REPARSE_POINT_ESCAPE: reparse point '{rp}' targets '{target}' outside authorized workdir '{workdir}'"

    if workdir is not None:
        try:
            norm_p = normalize_path(p)
            if is_drive_scope_breach(workdir, norm_p):
                return False, f"REPARSE_POINT_DRIVE_BREACH: path '{p}' resolves across drives to '{norm_p}'"
            if not is_path_confined(norm_p, workdir):
                return False, f"REPARSE_POINT_ESCAPE: path '{p}' resolves outside authorized workdir '{workdir}'"
        except Exception as e:
            return False, f"REPARSE_POINT_RESOLUTION_FAILED: {e}"

    return True, f"CONFINED_REPARSE_POINT: '{found[0]}' safely contained within '{workdir}'"


def resolve_workspace_child(workdir: str | os.PathLike, child: str | os.PathLike) -> Path | None:
    """Resolve child relative to workdir; returns None if child escapes workdir.

    Handles absolute paths, relative paths, spaces, Unicode, Windows verbatim prefixes,
    drive changes / scope breaches, and unconfined reparse points (junctions/symlinks).
    """
    try:
        # Strict fail-closed drive scope breach check
        if is_drive_scope_breach(workdir, child):
            return None

        root = normalize_path(workdir)
        s_child = strip_verbatim(str(child).strip())
        p_child = Path(s_child)
        full_child = p_child if p_child.is_absolute() else (root / p_child)

        # Reparse point security check
        safe, _ = check_reparse_point_safety(full_child, workdir=root)
        if not safe:
            return None

        candidate = full_child.resolve()

        if os.name == "nt":
            root_s = str(root).lower().rstrip("\\")
            cand_s = str(candidate).lower()
            if cand_s == root_s or cand_s.startswith(root_s + "\\"):
                return candidate
            return None
        else:
            if candidate == root or root in candidate.parents:
                return candidate
            return None
    except Exception:
        return None


class AuthenticWorkspaceRootError(RuntimeError):
    """Raised when authentic workspace root cannot be determined or verified."""
    pass


DEFAULT_WORKSPACE_MARKERS = (".git", "pyproject.toml", "courier_runtime")


def is_forbidden_system_root(p: Path) -> bool:
    """Detect unconfined filesystem roots or Windows system directories."""
    resolved = p.resolve()
    if resolved.parent == resolved:
        return True
    if os.name == "nt":
        s = str(resolved).lower().rstrip("\\")
        if len(s) <= 2 and s.endswith(":"):
            return True
        system_roots = [
            os.environ.get("SystemRoot", r"C:\Windows").lower().rstrip("\\"),
            os.environ.get("ProgramFiles", r"C:\Program Files").lower().rstrip("\\"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)").lower().rstrip("\\"),
        ]
        for sys_root in system_roots:
            if s == sys_root or s.startswith(sys_root + "\\"):
                return True
    else:
        s = str(resolved)
        if s in ("/", "/bin", "/sbin", "/etc", "/usr", "/System", "/Library"):
            return True
    return False


def find_authentic_workspace_root(
    start_path: str | os.PathLike | None = None,
    required_markers: tuple[str, ...] | list[str] | set[str] | None = None,
    allow_fallback: bool = False,
) -> Path | None:
    """Authentisch und fail-closed den Workspace-Root ermitteln.
    
    Beginnt bei `start_path` (oder CWD) und wandert die Hierarchie nach oben,
    bis ein Verzeichnis gefunden wird, das mindestens einen der kanonischen
    Workspace-Marker (default: .git, pyproject.toml, courier_runtime) enthält.
    
    Verhindert Ausbruch in verbotene System-Roots (C:\\, Windows, System-Pfade).
    Behandelt Windows-Verbatim-Pfade (\\\\?\\), relative Pfade, Symlinks und Spaces.
    
    Wirft `AuthenticWorkspaceRootError`, wenn kein valider Workspace gefunden wird
    (bzw. gibt None zurück falls allow_fallback=True).
    """
    if start_path is None:
        start_path = os.getcwd()

    start = normalize_path(start_path)
    if start.is_file():
        start = start.parent

    markers = tuple(required_markers) if required_markers is not None else DEFAULT_WORKSPACE_MARKERS

    curr = start
    while True:
        if is_forbidden_system_root(curr):
            break

        for m in markers:
            marker_path = curr / m
            if marker_path.exists():
                return curr.resolve()

        parent = curr.parent
        if parent == curr:
            break
        curr = parent

    if allow_fallback:
        return None
    raise AuthenticWorkspaceRootError(
        f"No authentic workspace root found starting from '{start_path}' (markers={markers})"
    )


def verify_workspace_root(
    path: str | os.PathLike | None = None,
    expected_name: str | None = None,
) -> tuple[bool, str]:
    """Prüft verbindlich, ob ein Pfad oder CWD ein authentischer Workspace-Root ist.
    
    Gibt (True, str(root)) zurück bei Erfolg, sonst (False, error_reason).
    """
    try:
        root = find_authentic_workspace_root(path, allow_fallback=False)
        if root is None:
            return False, "WORKSPACE_ROOT_NOT_FOUND"
        if expected_name is not None:
            if root.name.lower() != expected_name.lower():
                return False, f"WORKSPACE_NAME_MISMATCH: expected '{expected_name}', got '{root.name}'"
        return True, str(root)
    except Exception as e:
        return False, str(e)



@dataclass(frozen=True)
class Step:
    name: str
    argv: list
    output: str                    # file the step must produce
    effect_class: str = "idempotent"


class Workspace:
    def __init__(self, *, hosts, lease_store, broker, accepted_log, registry, workdir, clock, lease_ttl_s=30):
        self.hosts, self.leases, self.broker = hosts, lease_store, broker
        self.log, self.registry = accepted_log, registry
        self.workdir = str(normalize_path(workdir))
        self.clock = clock
        self.ttl = lease_ttl_s
        self.evidence = []

    def run(self, workkey, requirement, scope, request, steps, host=None, stop_after=None):
        """Run steps from the last accepted one. Returns the decision dict of the final state.

        stop_after: simulate a device loss after starting that step (process left running).
        """
        host = host or select(requirement, self.hosts)
        checkpoint = Checkpoint.from_log(workkey, [s.name for s in steps], self.log, lease_scope=scope)
        grant, state, reason = self.broker.authorize(request)
        if state != GRANTED:
            return {"state": "NEEDS_USER", "reasons": [f"authority required: {reason}"], "host": host.device_id}
        checkpoint.grant_ids = [grant.grant_id]
        owned_alive = [r.pid for r in self.registry.owned(workkey) if _alive(r)]
        lease_free = self.leases.current(scope) is None or self.leases.current(scope).holder == host.device_id
        decision = decide(checkpoint, grants_valid={grant.grant_id: True}, owned_alive=owned_alive,
                          lease_available=lease_free)
        if not decision["safe"]:
            return {**decision, "host": host.device_id}
        lease = self.leases.acquire(scope, host.device_id, workkey, ttl_s=self.ttl)
        for index in range(decision["resume_step"] or 0, len(steps)):
            step = steps[index]
            resolved_out = resolve_workspace_child(self.workdir, step.output)
            if resolved_out is None:
                self.leases.release(lease)
                return {"state": "FAILED", "host": host.device_id, "step": index,
                        "reasons": [f"output path escapes workdir: {step.output}"]}
            out = str(resolved_out)
            proc = subprocess.Popen(step.argv, cwd=self.workdir, stdin=subprocess.DEVNULL)
            self.registry.add(OwnedProcess.capture(proc.pid, workkey, host.device_id))
            if stop_after == index:
                return {"state": "DEVICE_LOST", "host": host.device_id, "step": index, "pid": proc.pid}
            code = proc.wait(timeout=60)
            lease = self.leases.renew(lease, ttl_s=self.ttl)          # heartbeat after progress
            self.registry.stop(workkey)                                  # nothing of ours left behind

            if os.path.exists(out):
                safe, reason = check_reparse_point_safety(out, workdir=self.workdir)
                if not safe:
                    self.leases.release(lease)
                    return {"state": "FAILED", "host": host.device_id, "step": index,
                            "reasons": [f"output violates reparse point security: {reason}"]}

            passed = code == 0 and os.path.exists(out)
            ev = Evidence(workkey, "python", host.device_id, _sha256(out) if passed else "", passed)
            self.evidence.append(ev)
            if not passed:
                return {"state": "FAILED", "host": host.device_id, "step": index, "reasons": [f"exit {code}"]}
            self.leases.check_write(scope, lease.token)                 # fenced: only the lease holder accepts
            self.log.append(AcceptedFact(workkey, index, f"{step.name} produced {step.output}",
                                         (f"evidence:{ev.artifact_sha256}",), "controller", self.clock()))
        self.leases.release(lease)
        return {"state": "DONE", "host": host.device_id, "steps": len(steps)}


def _alive(record):
    from courier_runtime.ownership import is_same_process
    return is_same_process(record)


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()
