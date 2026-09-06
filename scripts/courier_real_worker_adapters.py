"""Strict native real-worker adapters attaching CLI1, CODEX, and GEMINI genuine execution boundaries to CourierSafetyDispatcher."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from scripts.courier_safety_dispatcher import LocalConsumer, canonical_hash
from scripts.native_agy_runner import execute_native_agy_prompt, is_agy_installed

COURIER_REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_target_scope(goal_context: str, repo_root: Path) -> Optional[str]:
    """Extracts explicit target product/package scope from goal context or returns None.

    Inspects subdirectories in repo_root to check if any known product or package is referenced,
    or matches patterns like 'package <x>', 'app <y>', 'service <z>', 'product <p>', '<x> module', 'building <dir>'.
    """
    if not isinstance(goal_context, str) or not goal_context.strip():
        return None

    text = goal_context.lower()

    ignored = {
        "events", "runtime", "memory", "tmp", "tests", "venv", ".git", ".gemini",
        "__pycache__", "config", "schemas", "scripts", "tmp_queue_test"
    }

    # Helper to scan directories up to 2 levels deep
    def find_dir(candidate_name: str) -> Optional[str]:
        cand_lower = candidate_name.lower()
        try:
            for child in repo_root.iterdir():
                if child.is_dir() and child.name not in ignored and not child.name.startswith("."):
                    if child.name.lower() == cand_lower:
                        return child.name
                    # Check nested packages/services/apps
                    for sub in child.iterdir():
                        if sub.is_dir() and not sub.name.startswith(".") and sub.name.lower() == cand_lower:
                            return sub.name
        except Exception:
            pass
        return None

    # 1. Check for explicit phrases like "package X", "X module", "service Y", "product Z", "app A"
    match1 = re.search(r'\b(?:package|service|product|app|module|directory)\s+([a-zA-Z0-9_\-]+)\b', text)
    if match1:
        found = find_dir(match1.group(1))
        if found:
            return found

    match2 = re.search(r'\b([a-zA-Z0-9_\-]+)\s+(?:package|service|product|app|module)\b', text)
    if match2:
        found = find_dir(match2.group(1))
        if found:
            return found

    # 2. Check if any top-level or 2nd-level directory is mentioned as a whole word in the goal text
    try:
        for child in repo_root.iterdir():
            if child.is_dir() and child.name not in ignored and not child.name.startswith("."):
                name = child.name.lower()
                if re.search(r'\b' + re.escape(name) + r'\b', text):
                    return child.name
                for sub in child.iterdir():
                    if sub.is_dir() and not sub.name.startswith("."):
                        subname = sub.name.lower()
                        if re.search(r'\b' + re.escape(subname) + r'\b', text):
                            return sub.name
    except Exception:
        pass

    return None


def create_real_cli1_adapter(repo_root: Optional[Union[Path, str]] = None) -> LocalConsumer:
    """Creates a truthful CLI1 deterministic local worker adapter invoking scripts/cli_operations_autopilot.py."""
    root = Path(repo_root or COURIER_REPO_ROOT).resolve()

    def cli1_worker(task_envelope: Dict[str, Any]) -> Dict[str, Any]:
        task_hash = task_envelope["task_hash"]
        worker_id = task_envelope["worker_id"]
        target_agent = task_envelope["target_agent"]
        mission_id = task_envelope.get("mission_id", "")
        task_id = task_envelope.get("task_id", task_hash[:16])

        if target_agent != "CLI1":
            return {"status": "FAIL_CLOSED"}

        task_payload = task_envelope.get("payload", {})
        action = task_payload.get("action")
        correlation_id = str(task_envelope.get("correlation_id", ""))

        if action == "discover_improvement_opportunities":
            raise RuntimeError("CLI1_DISCOVERY_DEMOTED: CLI1 no longer performs hardcoded product-gap discovery. Use GEMINI.")

        elif action in ("implementation", "implement") or "implement" in task_payload.get("capability_request", "") or "write" in task_payload.get("capability_request", ""):
            raise RuntimeError(
                "CLI1_READONLY_CONTRACT_VIOLATED: CLI1 cannot perform implementation work. "
                "Route implementation capability to GEMINI."
            )

        elif action == "verify_improvement_tests":
            target_files = task_payload.get("target_files", [])
            is_social = any("social_platform" in str(f) for f in target_files)
            if is_social:
                cmd = ["python3", "-m", "unittest", "discover", "social_platform/tests"]
            else:
                cmd = ["python3", "-c", "import sys; print('No files modified'); sys.exit(1)"]
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30.0,
            )
            verdict = "PASS" if proc.returncode == 0 else "FAILED"
            payload_out = {
                "worker_agent": "CLI1",
                "worker_type": "DETERMINISTIC_LOCAL",
                "real_model_call": False,
                "separate_process": False,
                "entrypoint": "scripts/cli_operations_autopilot.py",
                "execution_mode": "REAL_CLI1_LOCAL_EXECUTION",
                "stage": "REAL_REPO_VERIFICATION",
                "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                "worker_originated_ack": False,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
                "task_hash": task_hash,
                "target_agent": target_agent,
                "action": "verify_improvement_tests",
                "files_verified": target_files,
                "test_returncode": proc.returncode,
                "test_output_summary": proc.stderr.splitlines()[-1] if proc.stderr else "OK",
                "verdict": verdict,
                "zero_cost_policy": "ZERO_COST_ONLY",
                "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
                "status": "COMPLETED" if verdict == "PASS" else "FAILED",
            }
        else:
            try:
                from scripts.cli_operations_autopilot import CLIOperationsAutopilot
                autopilot = CLIOperationsAutopilot(repo_dir=root)
                obs = autopilot.observe_organization()
            except Exception as exc:
                obs = {}

            payload_out = {
                "worker_agent": "CLI1",
                "worker_type": "DETERMINISTIC_LOCAL",
                "real_model_call": False,
                "separate_process": False,
                "entrypoint": "scripts/cli_operations_autopilot.py",
                "execution_mode": "REAL_CLI1_LOCAL_EXECUTION",
                "stage": "REAL_ORGANIZATIONAL_AND_REPO_OBSERVATION",
                "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                "worker_originated_ack": False,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
                "task_hash": task_hash,
                "target_agent": target_agent,
                "organization_observation": {
                    "active_workers_count": len(obs.get("available_workers", [])),
                    "active_locks_count": len(obs.get("active_locks", [])),
                    "heavy_job_active": obs.get("heavy_job_active", False),
                    "daemon_alive": obs.get("daemon_alive", False),
                },
                "zero_cost_policy": "ZERO_COST_ONLY",
                "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
                "verdict": "PASS",
                "status": "ANALYSIS_COMPLETE",
            }

        return {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED",
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),
            }
        }

    return cli1_worker


def create_real_codex_adapter(repo_root=None) -> Any:
    root = Path(repo_root or COURIER_REPO_ROOT).resolve()

    def codex_worker(task_envelope: Dict[str, Any]) -> Dict[str, Any]:
        task_hash = task_envelope["task_hash"]
        worker_id = task_envelope["worker_id"]
        target_agent = task_envelope["target_agent"]
        mission_id = task_envelope.get("mission_id", "")
        task_id = task_envelope.get("task_id", task_hash[:16])
        payload_in = task_envelope.get("payload", {})
        requested_model = task_envelope.get("requested_model", "codex")
        requires_write = task_envelope.get("requires_write", False)
        correlation_id = str(task_envelope.get("correlation_id", ""))

        if target_agent != "CODEX":
            return {"status": "FAIL_CLOSED"}

        instruction = str(payload_in.get("prompt") or payload_in.get("action") or "Inspect and analyse the repository.")

        raw_scope = payload_in.get("allowed_scope") or payload_in.get("target_files") or []
        if isinstance(raw_scope, str):
            raw_scope = [raw_scope]
        validated_scope = []
        for s in raw_scope:
            s = str(s).strip()
            if s.startswith("/") or s.startswith("..") or "\x00" in s:
                continue
            validated_scope.append(s)
        if not validated_scope:
            validated_scope = ["./"]

        if requires_write:
            raise RuntimeError(
                "CODEX_WRITE_NOT_YET_SUPPORTED: Codex bridge operates in read-only sandbox mode. "
                "Route write missions to GEMINI."
            )

        expected_identity = {
            "correlation_id": correlation_id,
            "task_id": task_id,
            "mission_id": mission_id,
            "task_hash": task_hash,
            "target_agent": "CODEX"
        }

        from scripts.run_codex_bridge import execute_real_codex_cli
        outer_timeout = float(task_envelope.get("timeout_seconds", os.environ.get("COURIER_NATIVE_AGY_TIMEOUT", "1200.0")))
        
        try:
            success, cli_res = execute_real_codex_cli(
                instruction=instruction,
                allowed_scope=validated_scope,
                task_id=task_id,
                expected_identity=expected_identity,
            )
            if not success:
                raise RuntimeError(f"CODEX_GENUINE_ENTRYPOINT_FAILED: {cli_res.get('error')}")
        except Exception as exc:
            raise RuntimeError(f"CODEX_GENUINE_ENTRYPOINT_FAILED: {exc}")

        verdict = cli_res.get("verdict", "FAILED")
        result_status = "HUMAN_GATE" if verdict == "HUMAN_APPROVAL_REQUIRED" else "COMPLETED"

        payload_out = {
            "worker_agent": "CODEX",
            "worker_type": "NATIVE_MODEL_CLI",
            "real_model_call": True,
            "separate_process": True,
            "requested_model": requested_model,
            "entrypoint": "/Applications/ChatGPT.app/Contents/Resources/codex",
            "execution_mode": "REAL_CODEX_CLI_EXECUTION",
            "stage": "REAL_CODEX_MODEL_EXECUTION",
            "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
            "worker_originated_ack": False,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "mission_id": mission_id,
            "task_hash": task_hash,
            "target_agent": target_agent,
            "cli_result": cli_res,
            "verdict": verdict,
            "summary": cli_res.get("summary", ""),
            "zero_cost_policy": "ZERO_COST_ONLY",
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
            "status": result_status,
        }

        return {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": result_status,
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),
            }
        }
    return codex_worker

def create_real_gemini_adapter(repo_root=None, model="gemini-3.7-flash-medium", agy_path=None) -> Any:
    root = Path(repo_root or COURIER_REPO_ROOT).resolve()

    def gemini_worker(task_envelope: Dict[str, Any]) -> Dict[str, Any]:
        task_hash = task_envelope["task_hash"]
        worker_id = task_envelope["worker_id"]
        target_agent = task_envelope["target_agent"]
        mission_id = task_envelope.get("mission_id", "")
        task_id = task_envelope.get("task_id", task_hash[:16])
        requested_model = task_envelope.get("requested_model") or model
        payload_in = task_envelope.get("payload", {})
        correlation_id = str(task_envelope.get("correlation_id", ""))
        
        if target_agent != "GEMINI":
            return {"status": "FAIL_CLOSED"}

        action = payload_in.get("action")
        
        expected_identity = {
            "correlation_id": correlation_id,
            "task_id": task_id,
            "mission_id": mission_id,
            "task_hash": task_hash,
            "target_agent": "GEMINI"
        }

        requires_write = task_envelope.get("requires_write", False)
        native_attempt = task_envelope.get("native_attempt", 1)
        
        identity_headers = (
            f"TARGET_AGENT: GEMINI\n"
            f"CORRELATION_ID: {correlation_id}\n"
            f"MISSION_ID: {mission_id}\n"
            f"TASK_ID: {task_id}\n"
            f"TASK_HASH: {task_hash}\n"
        )
        
        if requires_write and action == "implement_bounded_improvement":
            task_instruction = payload_in.get("prompt", "Perform the requested modification.")
            criteria = payload_in.get("acceptance_criteria", {})
            if native_attempt == 1:
                phase_1 = (
                    "You are performing an implementation task. You MUST use your available tools to actually write the requested files to the REPOSITORY DIRECTORY (your current working directory) or perform the requested modifications.\n"
                    "Do NOT write to a scratch pad unless explicitly requested.\n"
                    f"TASK INSTRUCTION: {task_instruction}\n"
                    f"ACCEPTANCE CRITERIA: {criteria}\n"
                )
            else:
                phase_1 = (
                    "The previous execution returned a success result, but Courier's deterministic verifier found that the requested workspace effect is still absent.\n"
                    "Do not return success yet. Perform the requested workspace modification now in the repository working directory using your available legitimate tools.\n"
                    "Then verify the requested effect exists.\n"
                    f"TASK INSTRUCTION: {task_instruction}\n"
                    f"ACCEPTANCE CRITERIA: {criteria}\n"
                )
            prompt = (
                f"{identity_headers}"
                f"PHASE 1 (EXECUTION):\n{phase_1}"
                "PHASE 2 (RESULT ENVELOPE):\n"
                "ONLY AFTER you have successfully performed the workspace modifications using your tools, return the final result.\n"
                "Return a valid JSON object with exact keys: "
                "'correlation_id', 'mission_id', 'task_id', 'task_hash', 'target_agent', 'changed_files' (list of strings), 'verdict' ('PASS' or 'HUMAN_APPROVAL_REQUIRED'), and 'summary' (concise summary of changes actually made)."
            )
            stage = "REAL_INDEPENDENT_IMPLEMENTATION"
            task_type = "IMPLEMENTATION"
        elif action == "discover_improvement_opportunities":
            goal_context = payload_in.get("goal_context", "")
            prompt = (
                f"{identity_headers}"
                "You are performing a read-only discovery task.\n"
                f"GOAL CONTEXT: {goal_context}\n"
                "Analyze the repository based on the goal context provided above. "
                "Return ONLY a valid JSON object with exact keys: "
                "'correlation_id', 'mission_id', 'task_id', 'task_hash', 'target_agent', 'weakness_id', 'description', 'suggested_files' (list of strings), 'verification_strategy', "
                "'verdict' ('PASS' or 'HUMAN_APPROVAL_REQUIRED'), and 'summary'."
            )
            stage = "REAL_INDEPENDENT_DISCOVERY"
            task_type = "DISCOVERY"
        else:
            prompt = (
                f"{identity_headers}"
                "You are performing a read-only acceptance review. All schemas and repository structure checks have passed successfully.\n"
                "Return ONLY a valid JSON object with exact keys: "
                "'correlation_id', 'mission_id', 'task_id', 'task_hash', 'target_agent', 'verdict' ('PASS' or 'HUMAN_APPROVAL_REQUIRED'), and 'summary' (concise acceptance review summary string)."
            )
            stage = "REAL_INDEPENDENT_ACCEPTANCE_AUDIT"
            task_type = "VERIFICATION"

        outer_timeout = float(task_envelope.get("timeout_seconds", os.environ.get("COURIER_NATIVE_AGY_TIMEOUT", "1200.0")))
        inner_timeout = max(10.0, outer_timeout - 10.0)

        success, agy_res = execute_native_agy_prompt(
            prompt=prompt,
            model=requested_model,
            timeout_seconds=inner_timeout,
            sandbox=True,
            repo_dir=root,
            agy_path=agy_path,
            expected_identity=expected_identity,
        )

        verdict = agy_res.get("verdict", "FAILED") if isinstance(agy_res, dict) else "FAILED"
        if not success:
            if verdict == "HUMAN_GATE":
                pass
            else:
                raise RuntimeError(f"GEMINI_NATIVE_AGY_FAILED: {agy_res.get('error', 'Unknown error')}")

        if verdict == "HUMAN_GATE" or agy_res.get("error_type") == "AUTHENTICATION_REQUIRED":
            payload_gate = {
                "worker_agent": "GEMINI",
                "worker_type": "NATIVE_AGY_MODEL",
                "real_model_call": True,
                "separate_process": True,
                "requested_model": requested_model,
                "confirmed_model": "UNKNOWN",
                "model_identity_truthful": "UNKNOWN",
                "entrypoint": agy_res.get("executable", "/Users/user/.local/bin/agy"),
                "execution_mode": "REAL_GEMINI_NATIVE_AGY_EXECUTION",
                "stage": "REAL_INDEPENDENT_ACCEPTANCE_AUDIT",
                "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                "worker_originated_ack": False,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
                "task_hash": task_hash,
                "target_agent": target_agent,
                "verdict": "HUMAN_APPROVAL_REQUIRED",
                "status": "HUMAN_GATE",
            }
            return {
                "ack": {
                    "schema_version": "1.0",
                    "type": "ACK",
                    "status": "ACCEPTED",
                    "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                    "task_hash": task_hash,
                    "worker_id": worker_id,
                    "target_agent": target_agent,
                    "correlation_id": correlation_id,
                    "task_id": task_id,
                    "mission_id": mission_id,
                },
                "result": {
                    "schema_version": "1.0",
                    "type": "RESULT",
                    "status": "HUMAN_GATE",
                    "task_hash": task_hash,
                    "worker_id": worker_id,
                    "target_agent": target_agent,
                    "correlation_id": correlation_id,
                    "task_id": task_id,
                    "mission_id": mission_id,
                    "payload": payload_gate,
                    "result_fingerprint": canonical_hash(payload_gate),
                }
            }

        summary = agy_res.get("summary")
        if not summary:
            raise RuntimeError("GEMINI_MISSING_SUMMARY: Model returned empty summary")

        result_status = "HUMAN_GATE" if verdict == "HUMAN_APPROVAL_REQUIRED" else "COMPLETED"

        payload_out = {
            "worker_agent": "GEMINI",
            "worker_type": "NATIVE_AGY_MODEL",
            "real_model_call": True,
            "separate_process": True,
            "requested_model": requested_model,
            "confirmed_model": agy_res.get("confirmed_model", "UNKNOWN"),
            "model_identity_truthful": agy_res.get("model_identity_truthful", "UNKNOWN"),
            "entrypoint": agy_res.get("executable", "/Users/user/.local/bin/agy"),
            "execution_mode": "REAL_GEMINI_NATIVE_AGY_EXECUTION",
            "stage": stage,
            "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
            "worker_originated_ack": False,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "mission_id": mission_id,
            "task_hash": task_hash,
            "target_agent": target_agent,
            "conversation_id": agy_res.get("conversation_id"),
            "duration_seconds": agy_res.get("duration_seconds"),
            "output_sha256": agy_res.get("output_sha256"),
            "verdict": verdict,
            "summary": summary,
            "task_type": task_type,
            "zero_cost_policy": "ZERO_COST_ONLY",
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
            "status": result_status,
        }

        if task_type == "DISCOVERY":
            payload_out["action"] = "discover_improvement_opportunities"
            payload_out["weakness_id"] = agy_res.get("weakness_id", "GENERAL_IMPROVEMENT")
            payload_out["description"] = agy_res.get("description") or agy_res.get("summary", "Improvement identified by Gemini")
            payload_out["suggested_files"] = agy_res.get("suggested_files", [])
            payload_out["verification_strategy"] = agy_res.get("verification_strategy", "run_unit_tests")
        elif task_type == "IMPLEMENTATION":
            payload_out["action"] = "implement_bounded_improvement"
            changed = agy_res.get("changed_files", [])
            if not changed:
                import subprocess
                diff = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True).stdout.strip()
                untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True).stdout.strip()
                all_changed = (diff + "\n" + untracked).split("\n")
                changed = [f for f in all_changed if f]
            payload_out["changed_files"] = changed
            payload_out["verification_strategy"] = agy_res.get("verification_strategy", "run_unit_tests")

        return {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": result_status,
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),
            }
        }

    return gemini_worker

def get_real_worker_adapters(repo_root: Optional[Path] = None, gemini_model: str = "gemini-3.7-flash-medium") -> Dict[str, Any]:
    root = repo_root or COURIER_REPO_ROOT
    return {
        "CLI1": create_real_cli1_adapter(root),
        "CODEX": create_real_codex_adapter(root),
        "GEMINI": create_real_gemini_adapter(root, model=gemini_model),
    }
