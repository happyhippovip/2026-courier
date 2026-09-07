"""Native Antigravity (AGY) Process Runner for Courier System.

Invokes the locally verified Antigravity CLI (/Users/user/.local/bin/agy)
via argument-array subprocess execution with closed stdin, finite timeout,
read-only sandbox restrictions, and strict schema validation.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AGY_CLI_PATH = Path("/Users/user/.local/bin/agy")
DEFAULT_VERIFIED_MODEL = "gemini-3.7-flash-medium"


def is_agy_installed(agy_path: Optional[Path] = None) -> bool:
    """Checks if the native agy binary exists and is executable."""
    bin_path = (agy_path or AGY_CLI_PATH).resolve()
    return bin_path.exists() and os.access(bin_path, os.X_OK)


def get_agy_version(agy_path: Optional[Path] = None) -> str:
    """Returns the installed AGY CLI version string."""
    if not is_agy_installed(agy_path):
        return "NOT_INSTALLED"
    bin_path = (agy_path or AGY_CLI_PATH).resolve()
    try:
        proc = subprocess.run(
            [str(bin_path), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5.0,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def execute_native_agy_prompt(
    prompt: str,
    model: str = DEFAULT_VERIFIED_MODEL,
    timeout_seconds: float = 180.0,
    sandbox: bool = True,
    repo_dir: Optional[Path] = None,
    agy_path: Optional[Path] = None,
    expected_identity: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Executes a single prompt non-interactively via native agy CLI with strict JSON output parsing."""
    bin_path = (agy_path or AGY_CLI_PATH).resolve()
    if not (bin_path.exists() and os.access(bin_path, os.X_OK)):
        return False, {
            "error_type": "EXECUTABLE_NOT_FOUND",
            "error": f"Native AGY executable not found at {bin_path}",
            "verdict": "BLOCKED",
        }

    cmd: List[str] = [
        str(bin_path),
        "-p", prompt,
        "--output-format", "json", "--print-timeout", f"{int(timeout_seconds)}s",
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    if sandbox:
        cmd.append("--sandbox")

    try:
        with open(os.devnull, "r") as devnull:
            proc = subprocess.run(
                cmd,
                stdin=devnull,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(repo_dir) if repo_dir else None,
                timeout=timeout_seconds + 30.0,
            )

        stdout_raw = proc.stdout.strip()
        stderr_raw = proc.stderr.strip()

        # First attempt to parse the outer JSON envelope
        outer_data = None
        try:
            if stdout_raw.strip():
                outer_data = json.loads(stdout_raw)
        except json.JSONDecodeError:
            pass

        auth_keywords = ["oauth", "login required", "authenticate", "re-authenticate", "2fa", "captcha", "account chooser"]

        def _is_auth_error(text: str) -> bool:
            return any(kw in text.lower() for kw in auth_keywords)

        is_auth_gate = False
        
        # 1. Structured check: if AGY explicitly returned an ERROR in JSON
        if outer_data and outer_data.get("status") == "ERROR":
            err_msg = str(outer_data.get("error", ""))
            err_type = str(outer_data.get("error_type", ""))
            if _is_auth_error(err_msg) or _is_auth_error(err_type) or err_type == "AUTHENTICATION_REQUIRED":
                is_auth_gate = True
                
        # 2. Unstructured fallback: if command failed or no valid JSON, scan raw output
        elif proc.returncode != 0 or not outer_data:
            if _is_auth_error(f"{stdout_raw}\n{stderr_raw}"):
                is_auth_gate = True

        if is_auth_gate:
            return False, {
                "error_type": "AUTHENTICATION_REQUIRED",
                "verdict": "HUMAN_GATE",
                "error": "AGY execution requires human authentication/login",
                "returncode": proc.returncode,
            }


        if proc.returncode != 0:
            return False, {
                "error_type": "NONZERO_EXIT",
                "verdict": "FAILED",
                "error": (f"Exit code {proc.returncode}\nSTDOUT:\n{stdout_raw[:2000]}\nSTDERR:\n{stderr_raw[:2000]}"),
                "returncode": proc.returncode,
            }

        if not outer_data:
            return False, {
                "error_type": "INVALID_OUTER_JSON",
                "verdict": "FAILED",
                "error": "Failed to parse AGY JSON output",
                "raw_output_snippet": stdout_raw[:200],
            }

        agy_status = outer_data.get("status")
        if agy_status != "SUCCESS":
            return False, {
                "error_type": "AGY_EXECUTION_FAILED",
                "verdict": "FAILED",
                "error": f"AGY returned non-success status: {agy_status}",
                "outer_data": outer_data,
            }

        response_text = outer_data.get("response", "").strip()

        # Extract inner JSON response from model
        model_payload = None
        parse_err = None
        # 1. Direct parse
        try:
            candidate = json.loads(response_text)
            if isinstance(candidate, dict):
                model_payload = candidate
        except Exception as e:
            parse_err = e

        # 2. Markdown fenced code blocks
        if model_payload is None:
            import re
            blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if blocks:
                valid_candidates = []
                for b in blocks:
                    try:
                        candidate = json.loads(b.strip())
                        if isinstance(candidate, dict):
                            valid_candidates.append(candidate)
                    except:
                        pass
                if len(valid_candidates) > 1:
                    parse_err = ValueError("Multiple valid JSON envelopes found in markdown blocks. Failing closed.")
                elif len(valid_candidates) == 1:
                    model_payload = valid_candidates[0]

        # 3. Outer brace extraction fallback
        if model_payload is None and parse_err is None:
            first_brace = response_text.find("{")
            last_brace = response_text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                try:
                    candidate = json.loads(response_text[first_brace:last_brace + 1].strip())
                    if isinstance(candidate, dict):
                        model_payload = candidate
                except Exception as e:
                    parse_err = e

        if model_payload is None or not isinstance(model_payload, dict):
            with open("scratch/debug_agy_fail.txt", "w") as f:
                f.write(f"STDOUT:\n{stdout_raw}\nSTDERR:\n{stderr_raw}\n")
            return False, {
                "error_type": "INVALID_MODEL_PAYLOAD_JSON",
                "verdict": "FAILED",
                "error": f"Model did not return schema-valid JSON payload: {parse_err}",
                "raw_model_response": response_text[:300],
            }

        # Validate expected identity fields in model_payload
        if expected_identity:
            for k, expected_v in expected_identity.items():
                actual_v = model_payload.get(k)
                if actual_v != expected_v:
                    return False, {
                        "error_type": "IDENTITY_MISMATCH",
                        "verdict": "FAILED",
                        "error": f"Model payload identity mismatch for '{k}': expected '{expected_v}', got '{actual_v}'",
                        "model_payload": model_payload,
                    }

        verdict = model_payload.get("verdict")
        if verdict not in {"PASS", "HUMAN_APPROVAL_REQUIRED", "WORKER_INFORMATION_REQUEST"}:
            return False, {
                "error_type": "INVALID_OR_MISSING_VERDICT",
                "verdict": "FAILED",
                "error": f"Model returned invalid or missing verdict: {verdict}",
                "model_payload": model_payload,
            }

        summary = model_payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            return False, {
                "error_type": "INVALID_OR_MISSING_SUMMARY",
                "verdict": "FAILED",
                "error": "Model payload must include non-empty 'summary' string",
            }

        confirmed_model = outer_data.get("model") or outer_data.get("metadata", {}).get("model") or "UNKNOWN"

        sanitized_evidence = {
            "executable": str(bin_path),
            "requested_model": model,
            "confirmed_model": confirmed_model,
            "model_identity_truthful": "UNKNOWN" if confirmed_model == "UNKNOWN" else (confirmed_model == model),
            "conversation_id": outer_data.get("conversation_id"),
            "duration_seconds": outer_data.get("duration_seconds"),
            "usage": outer_data.get("usage", {}),
            "output_sha256": hashlib.sha256(stdout_raw.encode("utf-8")).hexdigest(),
            "verdict": verdict,
            "summary": summary[:500],
            "correlation_id": model_payload.get("correlation_id"),
            "task_id": model_payload.get("task_id"),
            "task_hash": model_payload.get("task_hash"),
            "target_agent": model_payload.get("target_agent", "GEMINI"),
            "model_payload": model_payload,
        }
        return True, sanitized_evidence

    except subprocess.TimeoutExpired:
        return False, {
            "error_type": "TIMEOUT",
            "verdict": "FAILED",
            "error": f"AGY execution timed out after {timeout_seconds}s",
        }
    except Exception as exc:
        return False, {
            "error_type": "EXECUTION_EXCEPTION",
            "verdict": "FAILED",
            "error": str(exc),
        }
