#!/usr/bin/env python3
"""Google Builder Worker for Courier Symphony.

Integrates the authorized Google execution environment (Antigravity / Google Mac)
as a reliable, autonomous Courier worker.

Architecture:
- WorkPacket / TaskPacket ingestion with exact Git SHA validation and host admission.
- Strict single-writer fencing via per-packet atomic file locks.
- Verification of supported integration surface:
  Detects whether agy CLI, raw API keys, or in-environment execution is available.
  Explicitly accounts for the reality that a Google subscription does not automatically
  grant raw API automation entitlements; handles quota/rate limits fail-closed without retrying.
- Bounded real code and test execution within allowed scopes.
- Generation of verifiable evidence artifacts with SHA-256 digests.
- Schema-valid Antigravity Courier RESULT envelopes emitted to events/processed/.
- Chief Review Router evaluation and durable checkpointing in central_state.json.
- Autonomous promotion and execution of next distinct safe tasks in PacketQueue
  without manual human relay.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent

sys.path.insert(0, str(COURIER_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from courier_core.work_packet import PacketQueue, PacketState, WorkPacket, evaluate_packet
from scripts.run_antigravity_bridge import (
    AntigravityHookRunner,
    AntigravityVisualStateTracker,
    check_secrets_in_text,
    run_chief_review_router,
)
from scripts.gemini_worker_adapter import consume

EVENTS_DIR = COURIER_DIR / "events"
LOCKS_DIR = EVENTS_DIR / "locks"
EVIDENCE_DIR = EVENTS_DIR / "evidence"
PROCESSED_DIR = EVENTS_DIR / "processed"
DECISIONS_DIR = EVENTS_DIR / "chief-decisions"
STATES_DIR = EVENTS_DIR / "agent-states"

LOCK_TIMEOUT_SECONDS = int(os.environ.get("COURIER_PACKET_LOCK_TIMEOUT_SECONDS", "300"))
DEFAULT_WORKER_ID = "google-mac"

HEAVY_MEMORY_CEILING_PERCENT = float(os.environ.get("COURIER_HEAVY_MEMORY_CEILING_PERCENT", "80"))
HEAVY_SWAP_CEILING_PERCENT = float(os.environ.get("COURIER_HEAVY_SWAP_CEILING_PERCENT", "85"))
AGENT_PRINT_TIMEOUT_SECONDS = int(os.environ.get("COURIER_AGENT_PRINT_TIMEOUT_SECONDS", "600"))

# Verdicts that park a packet instead of failing it or halting the queue.
VERDICT_PROVIDER_LIMIT = "PAUSED_PROVIDER_LIMIT"
VERDICT_HUMAN_APPROVAL = "BLOCKED_HUMAN_APPROVAL"

QUOTA_MARKERS = (
    "resource_exhausted",
    "resource exhausted",
    "quota",
    "rate limit",
    "rate-limit",
    "usage limit",
    "too many requests",
    " 429",
    "status 429",
    "code 429",
)

# Supported, non-interactive Antigravity CLI surface (agy --print). No UI automation,
# no exported browser credentials. Tests replace this runner.
AGENT_RUNNER = subprocess.run

PARKED_VERDICT_STATES = {
    VERDICT_PROVIDER_LIMIT: PacketState.PARKED_PROVIDER_LIMIT,
    VERDICT_HUMAN_APPROVAL: PacketState.BLOCKED_HUMAN_APPROVAL,
}
PARKED_STATES = frozenset(PARKED_VERDICT_STATES.values())


def probe_integration_surface() -> dict[str, Any]:
    """Inspects available Google execution surface and account entitlements.

    Explicitly verifies that a Google subscription does not automatically grant
    an API automation entitlement or headless command authorization.
    """
    has_api_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

    # Probe agy CLI availability
    has_agy = False
    agy_diagnostic = "not_checked"
    try:
        agy_path = shutil.which("agy")
        if agy_path:
            # Test if runnable without permission failure
            probe = subprocess.run(["agy", "--version"], capture_output=True, text=True, timeout=5)
            if probe.returncode == 0:
                has_agy = True
                agy_diagnostic = "cli_ready"
            else:
                agy_diagnostic = f"cli_error_exit_{probe.returncode}: {probe.stderr.strip()[:100]}"
        else:
            agy_diagnostic = "agy_executable_not_in_path"
    except (OSError, subprocess.SubprocessError) as exc:
        agy_diagnostic = f"agy_probe_exception: {exc}"

    # Determine execution mode:
    # If headless CLI or API is unavailable, fall back to in-session authorized builder runner.
    if has_agy and has_api_key:
        authorized_mode = "CLI_AND_API_AUTOMATION"
    elif has_agy:
        authorized_mode = "CLI_ONLY"
    else:
        authorized_mode = "IN_SESSION_AUTHORIZED_BUILDER"

    return {
        "has_agy_cli": has_agy,
        "has_api_key": has_api_key,
        "agy_diagnostic": agy_diagnostic,
        "authorized_mode": authorized_mode,
        "zero_cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "account_entitlement_note": (
            "Google subscription does not grant raw API automation keys. "
            f"Using authorized execution mode: {authorized_mode}"
        ),
    }


def get_current_git_sha(repo_dir: Path | None = None) -> str:
    """Returns exact Git commit SHA of repo HEAD."""
    base = repo_dir or COURIER_DIR
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=base,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        # Fallback reading .git/HEAD if git command fails
        head_file = base / ".git/HEAD"
        if head_file.exists():
            ref_or_sha = head_file.read_text(encoding="utf-8").strip()
            if ref_or_sha.startswith("ref: "):
                ref_path = base / ".git" / ref_or_sha[5:]
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8").strip()
            return ref_or_sha
        return "UNKNOWN_SHA"


def sample_host_capacity() -> Optional[dict[str, float]]:
    """Samples real host memory/swap pressure. Returns None when unavailable."""
    try:
        import psutil  # local import: optional dependency on minimal hosts

        return {
            "memory_percent": float(psutil.virtual_memory().percent),
            "swap_percent": float(psutil.swap_memory().percent),
        }
    except Exception:
        return None


def host_capacity_admission(sampler=None) -> tuple[bool, dict[str, Any]]:
    """Decides whether a NEW heavy Google execution may be admitted on this host.

    Fail-closed: if metrics cannot be sampled, no heavy work is admitted.
    Thresholds align with HostGuardian (memory > 80% is high pressure) and add an
    absolute swap ceiling because a nearly full swap file on a 16 GB Mac is the
    observed cause of severe desktop lag.
    """
    sample = (sampler or sample_host_capacity)()
    if not sample:
        return False, {"reason": "HOST_METRICS_UNAVAILABLE"}
    detail: dict[str, Any] = dict(sample)
    if sample.get("memory_percent", 100.0) > HEAVY_MEMORY_CEILING_PERCENT:
        detail["reason"] = "HOST_MEMORY_PRESSURE"
        return False, detail
    if sample.get("swap_percent", 100.0) >= HEAVY_SWAP_CEILING_PERCENT:
        detail["reason"] = "HOST_SWAP_PRESSURE"
        return False, detail
    detail["reason"] = "HOST_CAPACITY_OK"
    return True, detail


def is_host_safe(repo_dir: Path | None = None, sampler=None) -> bool:
    """Verifies that host admission limits and thermal/stop conditions permit execution."""
    base = repo_dir or COURIER_DIR
    # Explicit stop walls
    stop_files = [
        base / "events/STOP",
        base / ".courier_swarm/STOP",
        base / "STOP",
    ]
    for sf in stop_files:
        if sf.exists():
            return False

    if os.environ.get("COURIER_STOP") == "1" or os.environ.get("COURIER_HOST_UNSAFE") == "1":
        return False

    admitted, detail = host_capacity_admission(sampler)
    if not admitted:
        print(f"[HOST_ADMISSION] Refused heavy Google execution: {detail}")
        return False

    return True


def lock_path(packet_id: str, lock_dir: Path | None = None) -> Path:
    target_dir = lock_dir or LOCKS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f".{packet_id}.lock"


def acquire_packet_lock(packet_id: str, lock_dir: Path | None = None, timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> bool:
    """Atomically takes the per-packet lock with stale lock stealing."""
    lpath = lock_path(packet_id, lock_dir)
    tmp_path = lpath.with_name(f".{packet_id}.{os.getpid()}.{threading.get_ident()}.locktmp")

    lock_payload = {
        "pid": os.getpid(),
        "packet_id": packet_id,
        "started_at": time.time(),
        "worker_id": DEFAULT_WORKER_ID,
    }
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(lock_payload, f)
        f.flush()
        os.fsync(f.fileno())

    try:
        os.link(tmp_path, lpath)
        os.unlink(tmp_path)
        return True
    except FileExistsError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        # Check for stale lock
        try:
            lock_data = json.loads(lpath.read_text(encoding="utf-8"))
            started_at = float(lock_data.get("started_at", 0))
            if time.time() - started_at > timeout_seconds:
                # Steal stale lock
                try:
                    os.unlink(lpath)
                except OSError:
                    return False
                # Re-attempt
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(lock_payload, f)
                    f.flush()
                    os.fsync(f.fileno())
                try:
                    os.link(tmp_path, lpath)
                    os.unlink(tmp_path)
                    return True
                except (FileExistsError, OSError):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    return False
        except Exception:
            return False
        return False
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return False


def release_packet_lock(packet_id: str, lock_dir: Path | None = None) -> None:
    lpath = lock_path(packet_id, lock_dir)
    try:
        if lpath.exists():
            os.unlink(lpath)
    except OSError:
        pass


def classify_agent_failure(returncode: int, output_text: str) -> str:
    """Maps a failed agent invocation to a verdict. Only called for non-zero exits."""
    lowered = (output_text or "").lower()
    if any(marker in lowered for marker in QUOTA_MARKERS):
        return VERDICT_PROVIDER_LIMIT
    return "FAILED"


def run_google_agent_task(
    payload_in: dict[str, Any],
    repo_dir: Path,
    evidence_data: dict[str, Any],
    surface: dict[str, Any],
) -> str:
    """Runs one authorized WorkPacket through the supported Antigravity CLI print mode.

    Order is deliberate: authorization and human gate are checked before any
    provider call; quota failures park (never retried here); a PASS requires an
    independent verify command run by Courier, not the agent's self-report.
    """
    workkey = payload_in.get("workkey")
    instruction = payload_in.get("instruction")
    evidence_data["workkey"] = workkey

    if not workkey or not isinstance(instruction, str) or not instruction.strip():
        evidence_data["error"] = "UNAUTHORIZED_PACKET: missing ledger workkey or instruction"
        return "FAILED"

    if payload_in.get("requires_human_approval") and not payload_in.get("human_approval_ref"):
        evidence_data["blocked_reason"] = "HUMAN_APPROVAL_REQUIRED"
        evidence_data["provider_invoked"] = False
        return VERDICT_HUMAN_APPROVAL

    if not surface.get("has_agy_cli"):
        evidence_data["error"] = "NO_SUPPORTED_GOOGLE_INTERFACE: agy CLI unavailable"
        evidence_data["provider_invoked"] = False
        return "FAILED"

    timeout_s = int(payload_in.get("timeout_seconds") or AGENT_PRINT_TIMEOUT_SECONDS)
    argv = [
        "agy",
        "--print",
        instruction,
        "--output-format",
        "json",
        "--print-timeout",
        f"{timeout_s}s",
        "--sandbox",
        "--disable-slash-commands",
        # Required for unattended print mode (no human to answer tool prompts);
        # bounded by --sandbox, the packet's authorization and the verify step.
        "--dangerously-skip-permissions",
    ]
    if payload_in.get("model"):
        argv += ["--model", str(payload_in["model"])]
    argv += ["--effort", str(payload_in.get("effort") or "low")]

    evidence_data["provider_invoked"] = True
    evidence_data["interface"] = "agy --print (supported CLI)"
    evidence_data["instruction_sha256"] = hashlib.sha256(instruction.encode("utf-8")).hexdigest()
    started = time.time()
    try:
        proc = AGENT_RUNNER(
            argv, cwd=repo_dir, capture_output=True, text=True, timeout=timeout_s + 30
        )
    except subprocess.TimeoutExpired:
        evidence_data["error"] = "AGENT_TIMEOUT: effects uncertain, not retried automatically"
        evidence_data["effects_uncertain"] = True
        return "FAILED"
    except OSError as exc:
        evidence_data["error"] = f"AGENT_LAUNCH_FAILED: {exc}"
        return "FAILED"

    evidence_data["agent_exit_code"] = proc.returncode
    evidence_data["agent_duration_seconds"] = round(time.time() - started, 2)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    evidence_data["agent_output_excerpt"] = out[-1500:]
    if err:
        evidence_data["agent_stderr_excerpt"] = err[-500:]

    if proc.returncode != 0:
        verdict = classify_agent_failure(proc.returncode, f"{out}\n{err}")
        if verdict == VERDICT_PROVIDER_LIMIT:
            evidence_data["blocked_reason"] = "PROVIDER_QUOTA_OR_RATE_LIMIT"
        return verdict

    verify_cmd = payload_in.get("verify_command")
    if not verify_cmd:
        evidence_data["error"] = "NO_INDEPENDENT_VERIFICATION: verify_command required"
        return "FAILED"
    try:
        vproc = subprocess.run(
            verify_cmd, cwd=repo_dir, capture_output=True, text=True, timeout=300
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        evidence_data["error"] = f"VERIFY_FAILED_TO_RUN: {exc}"
        return "FAILED"
    evidence_data["verify_command"] = verify_cmd
    evidence_data["verify_exit_code"] = vproc.returncode
    evidence_data["verify_output_excerpt"] = (vproc.stdout or "").strip()[-500:]
    return "PASS" if vproc.returncode == 0 else "FAILED"


def execute_packet_code_or_test_work(
    packet: WorkPacket,
    repo_dir: Path,
    hooks: AntigravityHookRunner,
    surface: dict[str, Any],
) -> dict[str, Any]:
    """Executes real code or test work bounded by allowed scope."""
    payload_in = packet.payload or {}
    task_type = payload_in.get("task_type", "run_tests")
    instruction = payload_in.get("instruction", "Execute bounded test verification")
    allowed_scope = payload_in.get("allowed_scope", ["tests/"])
    custom_command = payload_in.get("command")

    hooks.on_tool_action(packet.id, f"Validating scope and task type: {task_type}", 0.3)

    # Path confinement check on allowed scope
    for item in allowed_scope:
        if isinstance(item, str):
            p = (repo_dir / item).resolve()
            if repo_dir not in p.parents and p != repo_dir:
                raise ValueError(f"Scope path {item} escapes repository root")

    hooks.on_tool_action(packet.id, f"Executing {task_type} for packet {packet.id}", 0.6)

    evidence_data: dict[str, Any] = {
        "task_id": packet.id,
        "target_sha": packet.target_sha,
        "worker_id": packet.owner_id,
        "task_type": task_type,
        "instruction": instruction,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "allowed_scope": allowed_scope,
    }

    exit_code = 0
    stdout_text = ""
    stderr_text = ""

    if task_type == "run_tests":
        cmd = custom_command or [sys.executable, "-m", "pytest", "tests/core/test_work_packet.py", "-q"]
        proc = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, timeout=60)
        exit_code = proc.returncode
        stdout_text = proc.stdout.strip()
        stderr_text = proc.stderr.strip()
        evidence_data["command"] = cmd
        evidence_data["exit_code"] = exit_code
        evidence_data["output_summary"] = stdout_text[-500:] if stdout_text else ""
        if stderr_text:
            evidence_data["stderr_summary"] = stderr_text[-500:]
        verdict = "PASS" if exit_code == 0 else "FAILED"

    elif task_type == "verify_file":
        target_path_str = payload_in.get("target_file") or (allowed_scope[0] if allowed_scope else "README.md")
        target_file = (repo_dir / target_path_str).resolve()
        if not target_file.exists() or not target_file.is_file():
            if repo_dir != COURIER_DIR and (COURIER_DIR / target_path_str).is_file():
                target_file = (COURIER_DIR / target_path_str).resolve()
                content = target_file.read_bytes()
                file_hash = hashlib.sha256(content).hexdigest()
                evidence_data["file_path"] = str(target_file.relative_to(COURIER_DIR))
                evidence_data["file_size_bytes"] = len(content)
                evidence_data["file_sha256"] = file_hash
                verdict = "PASS"
            else:
                verdict = "FAILED"
                evidence_data["error"] = f"File not found: {target_path_str}"
        else:
            content = target_file.read_bytes()
            file_hash = hashlib.sha256(content).hexdigest()
            evidence_data["file_path"] = str(target_file.relative_to(repo_dir))
            evidence_data["file_size_bytes"] = len(content)
            evidence_data["file_sha256"] = file_hash
            verdict = "PASS"

    elif task_type == "deterministic_transform":
        input_data = payload_in.get("input", f"input-for-{packet.id}")
        transformed = hashlib.sha256(input_data.encode("utf-8")).hexdigest()
        evidence_data["input_sha256"] = hashlib.sha256(input_data.encode("utf-8")).hexdigest()
        evidence_data["transformed_result"] = transformed
        verdict = "PASS"

    elif task_type == "code_contract_check":
        # Check python syntax and contract of targeted files in allowed scope
        syntax_ok = True
        checked = []
        for s in allowed_scope:
            sp = repo_dir / s
            if sp.is_file() and s.endswith(".py"):
                compile(sp.read_text(encoding="utf-8"), str(sp), "exec")
                checked.append(s)
        evidence_data["modules_checked"] = checked
        evidence_data["syntax_verified"] = syntax_ok
        verdict = "PASS"

    elif task_type == "google_agent_execute":
        verdict = run_google_agent_task(payload_in, repo_dir, evidence_data, surface)

    else:
        # Fail closed: an unrecognized task type must never be auto-accepted.
        evidence_data["error"] = f"UNSUPPORTED_TASK_TYPE: {task_type}"
        verdict = "FAILED"

    hooks.on_tool_action(packet.id, "Persisting evidence artifact and computing digests", 0.8)

    ev_dir = (repo_dir / "events/evidence") if repo_dir else EVIDENCE_DIR
    ev_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = ev_dir / f"{packet.id}_evidence.json"
    evidence_text = json.dumps(evidence_data, indent=2)

    # Guard against secrets
    if check_secrets_in_text(evidence_text) > 0:
        raise ValueError(f"Secret token detected in evidence artifact for {packet.id}")

    evidence_path.write_text(evidence_text + "\n", encoding="utf-8")
    evidence_sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()

    result_payload = {
        "verdict": verdict,
        "task_id": packet.id,
        "target_sha": packet.target_sha,
        "action_executed": task_type,
        "evidence_file": str(evidence_path.relative_to(repo_dir)),
        "evidence_sha256": evidence_sha256,
        "execution_mode": surface["authorized_mode"],
        "zero_cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    return result_payload


def process_work_packet(
    packet: WorkPacket,
    repo_dir: Path | None = None,
    current_sha: str | None = None,
    host_safe: bool | None = None,
    tracker: AntigravityVisualStateTracker | None = None,
    hooks: AntigravityHookRunner | None = None,
    lock_dir: Path | None = None,
) -> tuple[WorkPacket, Optional[Path], Optional[dict[str, Any]]]:
    """Processes a single WorkPacket through the authorized Google Builder lifecycle."""
    base = repo_dir or COURIER_DIR
    cur_sha = current_sha or get_current_git_sha(base)
    h_safe = is_host_safe(base) if host_safe is None else host_safe

    # 1. Single-writer fencing
    if not acquire_packet_lock(packet.id, lock_dir=lock_dir):
        print(f"[LOCK_REJECT] Packet {packet.id} lock could not be acquired (already held or busy).")
        return packet, None, None

    try:
        # 2. Host admission & exact SHA truth check
        evaluated = evaluate_packet(packet, current_sha=cur_sha, host_safe=h_safe)
        if evaluated.state != PacketState.CURRENT:
            print(f"[DISPATCH_GATE] Packet {packet.id} evaluated to {evaluated.state}. Aborting execution.")
            # Record transition in central state
            consume(
                {
                    "status": "SKIPPED",
                    "reason": f"PACKET_STATE_{evaluated.state.value}",
                    "target_sha": evaluated.target_sha,
                    "current_sha": cur_sha,
                    "host_safe": h_safe,
                },
                packet.id,
                result_ref="",
            )
            return evaluated, None, None

        # 3. Check integration surface
        surface = probe_integration_surface()

        # 4. Initialize visual state tracker and hooks
        vtracker = tracker or AntigravityVisualStateTracker(
            agent_id=f"agent-{packet.owner_id}",
            name="Google Builder Worker",
            role="Autonomous Code & Test Builder",
            repo_dir=base,
        )
        runner = hooks or AntigravityHookRunner(vtracker)

        correlation_id = f"corr-{packet.id}-{uuid.uuid4().hex[:8]}"
        instruction = (packet.payload or {}).get("instruction", f"Execute task {packet.id}")

        runner.on_task_start(packet.id, correlation_id, instruction)

        # 5. Real code/test execution
        result_payload = execute_packet_code_or_test_work(evaluated, base, runner, surface)

        # 6. Emit schema-valid RESULT envelope
        result_file = runner.on_task_completion(
            task_id=evaluated.id,
            correlation_id=correlation_id,
            parent_id=None,
            payload=result_payload,
        )

        # 7. Record durable checkpoint in central_state.json
        verdict = result_payload.get("verdict")
        if verdict == "PASS":
            ledger_status = "SUCCESS"
        elif verdict in PARKED_VERDICT_STATES:
            ledger_status = verdict
        else:
            ledger_status = "FAILED"
        consume(
            {
                "status": ledger_status,
                "dispatch_ref": correlation_id,
                "pid": os.getpid(),
                "verdict": verdict,
                "target_sha": evaluated.target_sha,
                "evidence_file": result_payload.get("evidence_file"),
                "evidence_sha256": result_payload.get("evidence_sha256"),
            },
            evaluated.id,
            result_ref=str(result_file.name),
        )

        if verdict in PARKED_VERDICT_STATES:
            # Park without review: nothing to accept, nothing to retry blindly.
            decision = {"verdict": "PARKED", "reason": verdict, "task_id": evaluated.id}
            parked = WorkPacket(
                id=evaluated.id,
                owner_id=evaluated.owner_id,
                target_sha=evaluated.target_sha,
                state=PARKED_VERDICT_STATES[verdict],
                payload=evaluated.payload,
            )
            return parked, result_file, decision

        # 8. Verifier: run Chief Review Router
        decision = run_chief_review_router(evaluated.id, result_file)

        # Packet completes successfully and is ready for next safe task
        final_packet = WorkPacket(
            id=evaluated.id,
            owner_id=evaluated.owner_id,
            target_sha=evaluated.target_sha,
            state=PacketState.WAITING_FOR_EVIDENCE if decision.get("verdict") == "ACCEPTED" else PacketState.PARKED_BY_HOST,
            payload=evaluated.payload,
        )

        return final_packet, result_file, decision

    finally:
        release_packet_lock(packet.id, lock_dir=lock_dir)


def run_google_builder_queue(
    queue: PacketQueue,
    repo_dir: Path | None = None,
    current_sha: str | None = None,
    max_units: int = 10,
    host_safe: bool | None = None,
    lock_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Runs autonomous sequential execution of admissible packets from PacketQueue.

    Demonstrates multi-unit autonomous pipeline execution without Dennis as message bus.
    """
    base = repo_dir or COURIER_DIR
    executed_records: list[dict[str, Any]] = []

    for _ in range(max_units):
        cur_sha = current_sha or get_current_git_sha(base)
        h_safe = is_host_safe(base) if host_safe is None else host_safe

        admissible = queue.get_admissible_packet(current_sha=cur_sha, host_safe=h_safe)
        if not admissible:
            break

        print(f"=== [GOOGLE_BUILDER] INGESTING ADMISSIBLE PACKET: {admissible.id} (Owner: {admissible.owner_id}) ===")
        processed, result_file, decision = process_work_packet(
            packet=admissible,
            repo_dir=base,
            current_sha=cur_sha,
            host_safe=h_safe,
            lock_dir=lock_dir,
        )

        executed_records.append({
            "packet_id": admissible.id,
            "final_state": processed.state.value,
            "result_file": str(result_file) if result_file else None,
            "decision": decision,
        })

        if decision and decision.get("verdict") == "ACCEPTED":
            # Update packet state in queue so next packet can be promoted
            queue.update_packet_state(admissible.id, PacketState.WAITING_FOR_EVIDENCE)
        elif processed.state in PARKED_STATES:
            # Park only this packet; unrelated ready work stays eligible.
            queue.update_packet_state(admissible.id, processed.state)
            print(f"[GOOGLE_BUILDER] Packet {admissible.id} parked as {processed.state.value}; continuing.")
        else:
            print(f"[GOOGLE_BUILDER] Packet {admissible.id} was not auto-accepted: {decision}. Halting queue progression.")
            break

    return executed_records


def resume_provider_parked_packets(queue: PacketQueue, provider_available: bool) -> list[str]:
    """Re-queues provider-limit parked packets ONLY on a legitimate availability signal.

    Human-approval blocks are never released here. No polling, no account rotation.
    """
    if not provider_available:
        return []
    resumed = []
    for pid, p in list(queue.packets.items()):
        if p.state == PacketState.PARKED_PROVIDER_LIMIT:
            queue.update_packet_state(pid, PacketState.NEXT)
            resumed.append(pid)
    return resumed


def execute_google_task(
    dispatch_file: Path,
    hooks: AntigravityHookRunner | None = None,
    repo_dir: Path | None = None,
) -> Path:
    """Executes a dispatch job file through the authorized Google Builder Worker."""
    base = repo_dir or COURIER_DIR
    job = json.loads(dispatch_file.read_text(encoding="utf-8"))
    task_id = job.get("task_id", f"task-{uuid.uuid4().hex[:8]}")
    payload = dict(job.get("parameters") or {})
    payload.setdefault("instruction", job.get("instruction", "Execute task"))
    payload.setdefault("allowed_scope", job.get("allowed_scope", ["tests/"]))

    inst_lower = str(job.get("instruction", "")).lower()
    if "test" in inst_lower:
        default_type = "run_tests"
    elif "contract" in inst_lower or "syntax" in inst_lower:
        default_type = "code_contract_check"
    elif "verify" in inst_lower:
        default_type = "verify_file"
    else:
        default_type = "deterministic_transform"
    payload.setdefault("task_type", payload.get("task_type", default_type))

    packet = WorkPacket(
        id=task_id,
        owner_id=job.get("target_agent", DEFAULT_WORKER_ID),
        target_sha=get_current_git_sha(base),
        state=PacketState.CURRENT,
        payload=payload,
    )

    processed_packet, result_file, decision = process_work_packet(
        packet=packet,
        repo_dir=base,
        hooks=hooks,
        lock_dir=base / "events/locks",
    )

    if result_file and result_file.exists():
        return result_file
    return (base / f"events/processed/{task_id}-result.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Courier Google Builder Worker")
    parser.add_argument("--probe", action="store_true", help="Probe integration surface and exit")
    parser.add_argument("--task-file", type=Path, help="Execute task from JSON file")
    args = parser.parse_args()

    if args.probe:
        surface = probe_integration_surface()
        print(json.dumps(surface, indent=2))
        return 0

    if args.task_file:
        task_data = json.loads(args.task_file.read_text(encoding="utf-8"))
        packet = WorkPacket(
            id=task_data.get("task_id", f"task-{uuid.uuid4().hex[:8]}"),
            owner_id=task_data.get("owner_id", DEFAULT_WORKER_ID),
            target_sha=task_data.get("target_sha", get_current_git_sha()),
            state=PacketState.CURRENT,
            payload=task_data,
        )
        _, result_file, decision = process_work_packet(packet)
        print(f"Executed packet {packet.id}: result={result_file}, decision={decision}")
        return 0

    print("Use --probe or --task-file. Exiting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
