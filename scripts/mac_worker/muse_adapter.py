"""Boundary between a Courier task and the Muse CLI.

How Muse receives its prompt is not assumed. The operator declares the CLI's
confirmed method in the worker config (or COURIER_MUSE_CLI as JSON):

    "MUSE_CLI": {"binary": "muse", "prompt_via": "arg", "prompt_flag": "-p",
                 "extra_args": [], "masterprompt_path": "/path/masterprompt.md"}

prompt_via is "arg" (prompt_flag + prompt as one argument) or "stdin". Until a
method is declared, build_muse_command raises MuseCapabilityUnknown and the
task fails closed as MUSE_PROMPT_METHOD_UNCONFIRMED: nothing is typed into a
terminal or GUI.
"""
import json
import os
from pathlib import Path

PROMPT_METHODS = ("arg", "stdin")
CHECKPOINT_FIELDS = ("task_id", "status", "branch", "last_commit", "next_task")


class MuseCapabilityUnknown(Exception):
    pass


def cli_capabilities(config):
    raw = os.environ.get("COURIER_MUSE_CLI")
    caps = json.loads(raw) if raw else config.get("MUSE_CLI")
    return caps if isinstance(caps, dict) else {}


def build_prompt(task, checkpoint, masterprompt=""):
    identity = {k: task.get(k) for k in ("goal_id", "task_id", "attempt_id", "dispatch_id")}
    parts = [masterprompt.strip()] if masterprompt.strip() else []
    parts.append("Courier task identity (do not change): " + json.dumps(identity, sort_keys=True))
    parts.append("Instruction:\n" + str(task.get("instruction", task.get("description", ""))))
    if checkpoint:
        parts.append("Previous slot checkpoint: " + json.dumps(checkpoint, sort_keys=True))
    parts.append("When finished, print one ```json block with \"status\" (SUCCESS or FAILED) and, "
                 "if you committed, \"branch\", \"last_commit\" and \"next_task\".")
    return "\n\n".join(parts)


def build_muse_command(task, checkpoint, cli_capabilities):
    """Return (argv, stdin_text) for one Muse run of this task."""
    method = cli_capabilities.get("prompt_via")
    if method not in PROMPT_METHODS:
        raise MuseCapabilityUnknown(
            f"Muse prompt delivery is not confirmed (prompt_via={method!r}); declare MUSE_CLI.prompt_via as one of {PROMPT_METHODS}")
    binary = cli_capabilities.get("binary") or "muse"
    extra = [str(a) for a in cli_capabilities.get("extra_args", [])]
    masterprompt = ""
    path = cli_capabilities.get("masterprompt_path")
    if path:
        masterprompt = Path(path).expanduser().read_text(encoding="utf-8")
    prompt = build_prompt(task, checkpoint, masterprompt)
    if method == "arg":
        flag = cli_capabilities.get("prompt_flag")
        if not flag:
            raise MuseCapabilityUnknown("prompt_via=arg needs the confirmed prompt_flag")
        return [binary, *extra, flag, prompt], None
    return [binary, *extra], prompt


def parse_result(stdout, returncode):
    result = {"execution_mode": "MUSE", "exit_code": returncode}
    if "```json" in stdout:
        try:
            parsed = json.loads(stdout.split("```json")[-1].split("```")[0].strip())
            if isinstance(parsed, dict):
                result.update(parsed)
        except ValueError:
            pass
    if returncode != 0 or result.get("status") not in ("SUCCESS", "FAILED"):
        result["status"] = "FAILED"
        result["raw_diagnostic"] = stdout[-4000:]
    return result


def load_checkpoint(state_dir):
    try:
        data = json.loads((Path(state_dir) / "checkpoint.json").read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_checkpoint(state_dir, task, result):
    data = load_checkpoint(state_dir)
    data.update({k: result[k] for k in CHECKPOINT_FIELDS if isinstance(result.get(k), str)})
    data["task_id"] = task["task_id"]
    tmp = Path(state_dir) / "checkpoint.json.tmp"
    tmp.write_text(json.dumps(data, sort_keys=True))
    tmp.replace(Path(state_dir) / "checkpoint.json")
