#!/usr/bin/env python3
"""
Operating Ledger — thread-safe cost and revenue tracking for the Courier system.
Uses atomic writes (tmp + os.replace) and a threading.Lock for concurrency safety.

Trust properties:
- ATTESTER: every revenue entry carries verifier_id (who attested the completion).
- PROVENANCE: every entry carries the runtime git SHA captured at import time.
- MONOTONICITY: a per-file sequence counter prevents timestamp replay.
- IDEMPOTENCY: record_revenue and add_goal are no-ops for duplicate goal_id.
"""
import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

# Durable path for the operating ledger
LEDGER_PATH = Path(__file__).parent.parent / "operating_ledger.json"

# Module-level lock protects concurrent in-process writes
_LOCK = threading.Lock()

# Runtime SHA captured once at import — provides evidence provenance per process
def _capture_sha() -> str:
    try:
        root = Path(__file__).parent.parent
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode().strip()
    except Exception:
        return "unknown"

_RUNTIME_SHA: str = _capture_sha()


def _capture_runtime_identity() -> str:
    """Bind entries to the tracked source tree loaded by this process.

    HEAD alone cannot distinguish an uncommitted runtime from its base commit.
    Capture the binary worktree diff at import and bind it to that HEAD without
    changing any historical ledger record.
    """
    try:
        root = Path(__file__).parent.parent
        diff = subprocess.check_output(
            ["git", "diff", "--binary", "HEAD", "--"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        material = _RUNTIME_SHA.encode("utf-8") + b"\0" + diff
        return "runtime-sha256:" + hashlib.sha256(material).hexdigest()
    except Exception:
        return "unknown"


_RUNTIME_IDENTITY: str = _capture_runtime_identity()

# Cost table (USD per 1k tokens) — updated 2026-09 to include current models
COST_TABLE = {
    # Gemini 1.5 family
    "gemini-1.5-pro":        {"input": 0.00125,   "output": 0.00500},
    "gemini-1.5-flash":      {"input": 0.000075,  "output": 0.00030},
    "gemini-1.5-flash-8b":   {"input": 0.0000375, "output": 0.00015},
    # Gemini 2.0 family
    "gemini-2.0-flash":      {"input": 0.000100,  "output": 0.00040},
    "gemini-2.0-flash-lite": {"input": 0.000075,  "output": 0.00030},
    "gemini-2.0-pro-exp":    {"input": 0.00125,   "output": 0.00500},
    # Gemini 2.5 family
    "gemini-2.5-flash":      {"input": 0.000150,  "output": 0.00060},
    "gemini-2.5-pro":        {"input": 0.001250,  "output": 0.01000},
    # Claude (Anthropic)
    "claude-3-5-sonnet":     {"input": 0.003000,  "output": 0.01500},
    "claude-3-5-haiku":      {"input": 0.000800,  "output": 0.00400},
    "claude-3-opus":         {"input": 0.015000,  "output": 0.07500},
    # OpenAI
    "gpt-4o":                {"input": 0.002500,  "output": 0.01000},
    "gpt-4o-mini":           {"input": 0.000150,  "output": 0.00060},
    "o3-mini":               {"input": 0.001100,  "output": 0.00440},
    # Fallback
    "default":               {"input": 0.001000,  "output": 0.00200},
}

# ─── Internal helpers ─────────────────────────────────────────────────────────

def _empty_ledger():
    return {
        "goals": [],
        "tasks": [],
        "costs": {"compute": 0.0},
        "revenue": {"gross": 0.0, "margin": 0.0, "entries": []},
        "_seq": 0,
    }


def _read_raw():
    """Read ledger from disk (no lock — caller must hold _LOCK)."""
    if not LEDGER_PATH.exists():
        return _empty_ledger()
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all top-level keys exist (forward-compat)
        data.setdefault("goals", [])
        data.setdefault("tasks", [])
        data.setdefault("costs", {"compute": 0.0})
        data.setdefault("revenue", {"gross": 0.0, "margin": 0.0, "entries": []})
        data["revenue"].setdefault("entries", [])
        data.setdefault("_seq", 0)
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_ledger()


def _write_atomic(data):
    """Atomic write via tmp file + os.replace (no lock — caller must hold _LOCK)."""
    tmp_path = LEDGER_PATH.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, LEDGER_PATH)


def _next_seq(ledger) -> int:
    """Increment and return the monotonic sequence counter (caller holds _LOCK)."""
    ledger["_seq"] = ledger.get("_seq", 0) + 1
    return ledger["_seq"]

# ─── Public API ───────────────────────────────────────────────────────────────

def read_ledger():
    """Return a snapshot of the current ledger (safe to call any time)."""
    with _LOCK:
        return _read_raw()


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the USD cost for a given model + token counts."""
    rates = COST_TABLE.get(model, COST_TABLE["default"])
    return (input_tokens / 1000.0) * rates["input"] + (output_tokens / 1000.0) * rates["output"]


def record_compute(goal_id, task_id, worker_id, model, input_tokens, output_tokens):
    """
    Records compute usage per task.
    Thread-safe. Allows the Courier supervisor (and Codex) to analyse costs
    and optimise model routing over time.
    Returns the recorded entry dict.
    """
    cost = calculate_cost(model, input_tokens, output_tokens)
    with _LOCK:
        ledger = _read_raw()
        seq = _next_seq(ledger)
        entry = {
            "seq": seq,
            "timestamp": time.time(),
            "sha": _RUNTIME_SHA,
            "runtime_identity": _RUNTIME_IDENTITY,
            "goal_id": goal_id,
            "task_id": task_id,
            "worker_id": worker_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 8),
        }
        ledger["tasks"].append(entry)
        ledger["costs"]["compute"] = round(
            ledger["costs"].get("compute", 0.0) + cost, 8
        )
        ledger["revenue"]["margin"] = round(
            ledger["revenue"].get("gross", 0.0) - ledger["costs"]["compute"], 8
        )
        _write_atomic(ledger)
    return entry


def record_revenue(goal_id: str, amount_usd: float, note: str = "",
                   verifier_id: str = "") -> bool:
    """
    Records revenue received for a completed goal.
    Updates gross and recalculates margin.

    IDEMPOTENT: if a revenue entry for goal_id already exists, returns False
    without writing. This prevents double-counting from retried verify calls.

    ATTESTER: verifier_id captures who independently attested the completion.
    PROVENANCE: sha captures the runtime commit this process is running.
    MONOTONICITY: seq counter ensures strict append ordering.

    Returns True on new entry, False on duplicate.
    """
    with _LOCK:
        ledger = _read_raw()
        existing_goal_ids = {e["goal_id"] for e in ledger["revenue"].get("entries", [])}
        if goal_id in existing_goal_ids:
            return False  # idempotent — already recorded
        seq = _next_seq(ledger)
        ledger["revenue"]["gross"] = round(
            ledger["revenue"].get("gross", 0.0) + amount_usd, 8
        )
        ledger["revenue"]["entries"].append({
            "seq": seq,
            "timestamp": time.time(),
            "sha": _RUNTIME_SHA,
            "runtime_identity": _RUNTIME_IDENTITY,
            "goal_id": goal_id,
            "amount_usd": round(amount_usd, 8),
            "note": note,
            "verifier_id": verifier_id,
        })
        ledger["revenue"]["margin"] = round(
            ledger["revenue"]["gross"] - ledger["costs"].get("compute", 0.0), 8
        )
        _write_atomic(ledger)
    return True


def add_goal(goal_id: str, status: str = "STARTED") -> bool:
    """
    Append a goal entry in the ledger.
    IDEMPOTENT: if goal_id already exists, returns False without writing.
    Returns True on new entry, False on duplicate.
    """
    with _LOCK:
        ledger = _read_raw()
        existing = {g["goal_id"] for g in ledger["goals"]}
        if goal_id in existing:
            return False  # idempotent
        seq = _next_seq(ledger)
        ledger["goals"].append({
            "seq": seq,
            "goal_id": goal_id,
            "status": status,
            "timestamp": time.time(),
            "sha": _RUNTIME_SHA,
            "runtime_identity": _RUNTIME_IDENTITY,
        })
        _write_atomic(ledger)
    return True


def print_operator_report():
    ledger = read_ledger()
    compute  = ledger["costs"].get("compute", 0.0)
    gross    = ledger["revenue"].get("gross", 0.0)
    margin   = ledger["revenue"].get("margin", 0.0)
    print("--- OPERATOR REPORT ---")
    print(f"Goals Tracked : {len(ledger.get('goals', []))}")
    print(f"Tasks Logged  : {len(ledger.get('tasks', []))}")
    print(f"Compute Cost  : ${compute:.6f}")
    print(f"Gross Revenue : ${gross:.6f}")
    print(f"Margin        : ${margin:.6f}")
    print(f"Runtime SHA   : {_RUNTIME_SHA}")


if __name__ == "__main__":
    print_operator_report()
