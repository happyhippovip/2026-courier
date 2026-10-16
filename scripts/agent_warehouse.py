from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

@dataclass
class AgentCatalogEntry:
    id: str
    display_name: str
    agent_class: str
    status: str
    owner_files: List[str]
    capabilities: List[str]
    write_authority: bool
    read_only_default: bool
    supported_hosts: List[str]
    provider_binding: Optional[str]
    cost_class: str
    heavy_job_class: Optional[str]
    evidence_sources: List[str] = field(default_factory=list)

@dataclass
class AgentCatalog:
    schema_version: str
    authority: str
    related_issues: List[int]
    agents: List[AgentCatalogEntry]

    @classmethod
    def load(cls, path: Path) -> 'AgentCatalog':
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        agents = []
        for a_data in data.get("agents", []):
            agents.append(AgentCatalogEntry(
                id=a_data["id"],
                display_name=a_data["display_name"],
                agent_class=a_data["class"],
                status=a_data["status"],
                owner_files=a_data.get("owner_files", []),
                capabilities=a_data.get("capabilities", []),
                write_authority=a_data.get("write_authority", False),
                read_only_default=a_data.get("read_only_default", True),
                supported_hosts=a_data.get("supported_hosts", []),
                provider_binding=a_data.get("provider_binding"),
                cost_class=a_data.get("cost_class", "unknown"),
                heavy_job_class=a_data.get("heavy_job_class"),
                evidence_sources=a_data.get("evidence_sources", [])
            ))
            
        return cls(
            schema_version=data.get("schema_version", ""),
            authority=data.get("authority", ""),
            related_issues=data.get("related_issues", []),
            agents=agents
        )

@dataclass
class RoutingExplanation:
    selected_agent_id: str
    capable_reason: str
    non_duplicate_reason: str
    cost_reason: str
    fallback_agent_id: Optional[str]

class CapabilitySelector:
    def __init__(self, catalog: AgentCatalog):
        self.catalog = catalog
        
    def select_agent_for_task(self, required_capability: str, required_host: Optional[str] = None, current_owners: List[str] = None, require_implemented: bool = True) -> RoutingExplanation:
        if current_owners is None:
            current_owners = []
            
        candidates = []
        for agent in self.catalog.agents:
            if require_implemented and agent.status != "implemented":
                continue
            if required_capability in agent.capabilities:
                if required_host is None or not agent.supported_hosts or required_host in agent.supported_hosts:
                    # Exclude active owners to prevent duplicate writers
                    if agent.id in current_owners:
                        continue
                    
                    # Also exclude if any of its owner_files are claimed by current_owners
                    active_owner_files = set()
                    for owner_id in current_owners:
                        for a in self.catalog.agents:
                            if a.id == owner_id:
                                active_owner_files.update(a.owner_files)
                    
                    if set(agent.owner_files).intersection(active_owner_files):
                        continue
                        
                    candidates.append(agent)
                    
        if not candidates:
            raise ValueError(f"No agent found for capability {required_capability} (or all capable agents are blocked by duplicate writer constraints)")
            
        # Sort by cost (local > free > low > medium > high > routed)
        # Sort by class (core > specialist > provider > reserve)
        cost_ranks = {"local_first": 0, "free": 1, "low": 2, "medium": 3, "high": 4, "local_or_routed": 5}
        class_ranks = {"core": 0, "specialist": 1, "provider": 2, "reserve": 3}
        
        candidates.sort(key=lambda a: (
            class_ranks.get(a.agent_class, 99),
            cost_ranks.get(a.cost_class, 99)
        ))
        
        selected = candidates[0]
        fallback = candidates[1].id if len(candidates) > 1 else None
        
        return RoutingExplanation(
            selected_agent_id=selected.id,
            capable_reason=f"Agent declares capability '{required_capability}' in catalog",
            non_duplicate_reason=f"Respects one-writer constraint; active owners: {current_owners}",
            cost_reason=f"Selected cheapest available option (cost class: {selected.cost_class})",
            fallback_agent_id=fallback
        )


MAX_SUBPROCESS_OUTPUT_BYTES = 64 * 1024  # 64 KB per stream default limit

SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9_\-\.+=/]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd|auth)\b(\s*[:=]\s*['\"]?)[A-Za-z0-9_\-\.+=/]+(['\"]?)"), r"\1\2[REDACTED]\3"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{16,})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(ghp_[A-Za-z0-9]{20,})\b"), "[REDACTED_GITHUB_TOKEN]"),
]


def redact_sensitive_output(text: str) -> str:
    """Filter API keys, bearer tokens, and credentials from stdout/stderr."""
    if not text:
        return text
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


@dataclass
class SubprocessResultReceipt:
    execution_id: str
    task_id: str
    dispatch_id: str
    worker_id: str
    command: List[str]
    exit_code: int
    outcome: str               # "success" or "failure"
    status: str                # "ACCEPTED_FOR_VERIFY", "NONZERO_EXIT", "TIMEOUT", "EMPTY_OUTPUT", "LAUNCH_ERROR"
    stdout: str
    stderr: str
    stdout_bytes: int
    stderr_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    duration_s: float
    agent_id: Optional[str] = None
    error_reason: Optional[str] = None
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence_sha256: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.agent_id:
            self.agent_id = self.worker_id

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_dir(self, directory: Path | str) -> Path:
        """Durable atomic write of the result receipt."""
        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / f"rcpt-{self.dispatch_id}.json"
        
        # Atomic replace via temp file in the same directory
        fd, tmp_path_str = tempfile.mkstemp(dir=target_dir, prefix=".tmp-rcpt-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path_str, final_path)
        except BaseException:
            try:
                os.unlink(tmp_path_str)
            except OSError:
                pass
            raise
            
        return final_path


def execute_warehouse_subprocess(
    cmd: Sequence[str],
    *,
    task_id: str,
    dispatch_id: str,
    worker_id: str,
    agent_id: Optional[str] = None,
    timeout_s: float = 60.0,
    max_output_bytes: int = MAX_SUBPROCESS_OUTPUT_BYTES,
    cwd: Optional[Path | str] = None,
    env: Optional[Dict[str, str]] = None,
    require_output: bool = False,
    redact_secrets: bool = True,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    evidence_sha256: Optional[str] = None,
) -> SubprocessResultReceipt:
    """Executes a child subprocess, captures bounded stdout/stderr streams,
    redacts secrets, and classifies the exit status into a durable receipt.
    
    Guarantees:
    - stdout and stderr captured and distinguished as separate streams.
    - Nonzero exit codes NEVER classified as success/ACCEPTED_FOR_VERIFY.
    - Timeout produces structured failure result.
    - Output limits enforced: streams exceeding max_output_bytes are safely truncated.
    - Empty output passes when require_output=False, fails when require_output=True.
    - Sensitive credentials and keys redacted from stored outputs.
    """
    if not cmd or not isinstance(cmd, (list, tuple)):
        raise ValueError("cmd must be a non-empty sequence of arguments")

    t0 = time.monotonic()
    execution_id = f"exec-{dispatch_id}-{int(time.time() * 1000) % 1000000:06d}"
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    raw_stdout = b""
    raw_stderr = b""
    is_timeout = False

    try:
        proc = subprocess.Popen(
            list(cmd),
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        try:
            raw_stdout, raw_stderr = proc.communicate(timeout=timeout_s)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            is_timeout = True
            proc.kill()
            try:
                raw_stdout, raw_stderr = proc.communicate(timeout=5.0)
            except subprocess.TimeoutExpired:
                pass
            exit_code = -1
    except OSError as exc:
        duration_s = time.monotonic() - t0
        err_msg = str(exc)
        return SubprocessResultReceipt(
            execution_id=execution_id,
            task_id=task_id,
            dispatch_id=dispatch_id,
            worker_id=worker_id,
            agent_id=agent_id or worker_id,
            command=list(cmd),
            exit_code=-127,
            outcome="failure",
            status="LAUNCH_ERROR",
            stdout="",
            stderr=err_msg,
            stdout_bytes=0,
            stderr_bytes=len(err_msg.encode("utf-8")),
            stdout_truncated=False,
            stderr_truncated=False,
            duration_s=duration_s,
            error_reason=f"Subprocess launch failed: {exc}",
            artifacts=artifacts or [],
            evidence_sha256=evidence_sha256,
        )

    duration_s = time.monotonic() - t0
    stdout_bytes = len(raw_stdout or b"")
    stderr_bytes = len(raw_stderr or b"")
    stdout_truncated = False
    stderr_truncated = False

    if stdout_bytes > max_output_bytes:
        raw_stdout = (raw_stdout or b"")[:max_output_bytes]
        stdout_truncated = True

    if stderr_bytes > max_output_bytes:
        raw_stderr = (raw_stderr or b"")[:max_output_bytes]
        stderr_truncated = True

    stdout_text = raw_stdout.decode("utf-8", errors="replace") if raw_stdout else ""
    stderr_text = raw_stderr.decode("utf-8", errors="replace") if raw_stderr else ""

    if stdout_truncated:
        stdout_text += "\n[TRUNCATED: max_output_bytes exceeded]"
    if stderr_truncated:
        stderr_text += "\n[TRUNCATED: max_output_bytes exceeded]"

    if redact_secrets:
        stdout_text = redact_sensitive_output(stdout_text)
        stderr_text = redact_sensitive_output(stderr_text)

    # Classification logic: Fail closed on non-zero exit or timeout
    if is_timeout:
        outcome = "failure"
        status = "TIMEOUT"
        error_reason = f"Subprocess timed out after {timeout_s}s"
    elif exit_code != 0:
        outcome = "failure"
        status = "NONZERO_EXIT"
        error_reason = f"Process exited with non-zero exit code {exit_code}"
    elif require_output and not stdout_text.strip():
        outcome = "failure"
        status = "EMPTY_OUTPUT"
        error_reason = "Subprocess produced empty output when output was required by task contract"
    else:
        outcome = "success"
        status = "ACCEPTED_FOR_VERIFY"
        error_reason = None

    return SubprocessResultReceipt(
        execution_id=execution_id,
        task_id=task_id,
        dispatch_id=dispatch_id,
        worker_id=worker_id,
        agent_id=agent_id or worker_id,
        command=list(cmd),
        exit_code=exit_code,
        outcome=outcome,
        status=status,
        stdout=stdout_text,
        stderr=stderr_text,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        duration_s=duration_s,
        error_reason=error_reason,
        artifacts=artifacts or [],
        evidence_sha256=evidence_sha256,
    )
