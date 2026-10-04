"""Workspace-bound Muse exec/resume/message boundary; no guessed session references."""
import json
import os
from pathlib import Path
from runtime_state import atomic_json, read_object

IDENTITY_FIELDS = ("goal_id", "task_id", "attempt_id", "dispatch_id")
CHECKPOINT_FIELDS = ("status", "branch", "last_commit", "next_task")
TEMPLATE = Path(__file__).with_name("muse_prompt.md")


class MuseCapabilityUnknown(ValueError):
    pass


class MuseBindingError(ValueError):
    pass


def cli_capabilities(config):
    raw = os.environ.get("COURIER_MUSE_CLI")
    caps = json.loads(raw) if raw else config.get("MUSE_CLI")
    return caps if isinstance(caps, dict) else {}


def task_binding(task, slot_id, workspace):
    if not slot_id or not workspace or not Path(workspace).is_absolute():
        raise MuseBindingError("Explicit slot and absolute workspace required")
    identity = {key: task.get(key) for key in IDENTITY_FIELDS}
    if any(not isinstance(value, str) or not value for value in identity.values()):
        raise MuseBindingError("Incomplete canonical task identity")
    return dict(identity, slot_id=str(slot_id), workspace=os.path.normpath(workspace))


def build_prompt(task, checkpoint, masterprompt=""):
    parts = [masterprompt.strip() or TEMPLATE.read_text(encoding="utf-8").strip()]
    parts.append("Courier task identity (do not change): " + json.dumps(
        {key: task.get(key) for key in IDENTITY_FIELDS}, sort_keys=True))
    parts.append("Instruction:\n" + str(task.get("instruction", task.get("description", ""))))
    if checkpoint:
        parts.append("Bound checkpoint: " + json.dumps(checkpoint, sort_keys=True))
    return "\n\n".join(parts)


def build_muse_command(task, checkpoint, capabilities, *, slot_id=None,
                       workspace=None, action="exec", prompt=None):
    if capabilities.get("protocol") != "headless-v1":
        raise MuseCapabilityUnknown("Confirm MUSE_CLI.protocol=headless-v1 before launch")
    binding = task_binding(task, slot_id, workspace)
    if action not in ("exec", "resume", "session-message"):
        raise MuseCapabilityUnknown("Unsupported Muse operation")
    if checkpoint and checkpoint.get("binding") != binding:
        raise MuseBindingError("Checkpoint slot/task/attempt/dispatch/workspace mismatch")
    cmd = [str(capabilities.get("binary") or "muse"), action, "--workspace", binding["workspace"]]
    if action == "exec":
        if capabilities.get("reasoning_effort"):
            cmd.extend(["--reasoning-effort", str(capabilities["reasoning_effort"])])
        if capabilities.get("yolo") is True:
            cmd.append("--yolo")
        cmd.append(prompt if prompt is not None else build_prompt(task, checkpoint))
    else:
        if (capabilities.get("session_ref_format") != "json-envelope-v1"
                or checkpoint.get("session_ref_verified") is not True
                or not isinstance(checkpoint.get("session_ref"), str)
                or not checkpoint["session_ref"].strip()):
            raise MuseBindingError("No verified session/output contract; reconcile before resume")
        cmd.append(checkpoint["session_ref"])
        if action == "session-message":
            cmd.append(prompt if prompt is not None else build_prompt(task, checkpoint))
        elif capabilities.get("yolo") is True:
            cmd.append("--yolo")
    return cmd, None


def parse_result(stdout, returncode, capabilities=None):
    result = {"execution_mode": "MUSE", "exit_code": returncode}
    # This envelope is opt-in, NOT a claim about an unobserved physical CLI format.
    # Model-written fenced JSON is never accepted as session provenance.
    if (capabilities or {}).get("session_ref_format") == "json-envelope-v1":
        try:
            envelope = json.loads(stdout)
            ref = envelope["session_ref"]
            if not isinstance(ref, str) or not ref.strip() or not isinstance(envelope["result"], dict):
                raise ValueError("Invalid session envelope")
            result.update({k: envelope["result"][k] for k in CHECKPOINT_FIELDS if k in envelope["result"]})
            result.update(session_ref=ref, session_ref_verified=True)
        except (ValueError, KeyError, TypeError):
            raise MuseBindingError("Invalid physical session output; no resume reference saved")
    elif "```json" in stdout:
        try:
            parsed = json.loads(stdout.split("```json")[-1].split("```")[0].strip())
            if isinstance(parsed, dict):
                result.update({k: parsed[k] for k in CHECKPOINT_FIELDS if k in parsed})
        except ValueError:
            pass
    if returncode != 0 or result.get("status") not in ("SUCCESS", "FAILED"):
        result["status"] = "FAILED"
        result["raw_diagnostic"] = stdout[-4000:]
    return result


def load_checkpoint(state_dir):
    return read_object(Path(state_dir) / "checkpoint.json")


def save_checkpoint(state_dir, task, result, *, slot_id, workspace):
    data = {k: result[k] for k in CHECKPOINT_FIELDS if isinstance(result.get(k), str)}
    data.update(task_id=task["task_id"], binding=task_binding(task, slot_id, workspace))
    if result.get("session_ref_verified") is True and result.get("session_ref"):
        data.update(session_ref=result["session_ref"], session_ref_verified=True)
    atomic_json(Path(state_dir) / "checkpoint.json", data)


def prepare_prompt(state_dir, task, binding, checkpoint, capabilities):
    """Persist the exact template-expanded prompt before a process sees it."""
    path = Path(state_dir) / "prompt.json"
    existing = read_object(path)
    if existing.get("binding") == binding:
        return existing["prompt"]
    template_path = capabilities.get("masterprompt_path")
    template = Path(template_path).expanduser().read_text() if template_path else ""
    prompt = build_prompt(task, checkpoint, template)
    atomic_json(path, {"binding": binding, "prompt": prompt})
    return prompt
