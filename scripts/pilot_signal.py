"""Plan pilot signals without coloring an undecided setup budget.

GQ46 still says setup under 5 minutes. The dummy task still allows 15.
Until those two published numbers are one decision, a setup record stays
UNCOLORED. Support effort is the count of out-of-band prompts. A human
relay count exists only when the caller supplies the events that were seen.
This module does not unlock the product shell.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "ops" / "ai" / "PILOT_METRICS_AND_SIGNAL_SPEC.md"
DUMMY_PATH = ROOT / "ops" / "ai" / "PILOT_DUMMY_TASK.json"


def setup_budget_minutes():
    """Read the two published setup budgets. Do not choose between them."""
    spec = SPEC_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"Setup Time \(T_setup\):.*?Target:\s*<\s*(\d+)\s+minutes",
        spec,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("GQ46 setup target is missing")
    dummy = json.loads(DUMMY_PATH.read_text(encoding="utf-8"))
    dummy_minutes = dummy["pilot_metadata"]["metrics_target"]["setup_time_minutes_max"]
    if type(dummy_minutes) is not int:
        raise ValueError("dummy setup budget must be an int")
    gq46_minutes = int(match.group(1))
    return {
        "gq46_minutes": gq46_minutes,
        "dummy_minutes": dummy_minutes,
        "agree": gq46_minutes == dummy_minutes,
    }


def plan_setup_time(minutes, method, caller_verdict=None):
    """Record raw setup minutes and the method. Refuse a colored verdict."""
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)):
        raise ValueError("setup minutes must be a number")
    if minutes < 0:
        raise ValueError("setup minutes must be >= 0")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("setup method is required")
    if caller_verdict is not None:
        raise ValueError("caller must not color setup time")
    budgets = setup_budget_minutes()
    if budgets["agree"]:
        raise ValueError("setup budgets agree; coloring is still not decided here")
    return {
        "minutes": minutes,
        "method": method.strip(),
        "verdict": "UNCOLORED",
        "budgets": {
            "gq46_minutes": budgets["gq46_minutes"],
            "dummy_minutes": budgets["dummy_minutes"],
        },
        "shell_unlocked": False,
    }


def record_support_effort(out_of_band_prompts):
    """Count out-of-band prompts. Free text is not a support-effort measure."""
    if type(out_of_band_prompts) is not int or out_of_band_prompts < 0:
        raise ValueError("support effort counts out-of-band prompts")
    return {
        "measure": "out_of_band_prompts",
        "count": out_of_band_prompts,
        "meets_zero_target": out_of_band_prompts == 0,
        "shell_unlocked": False,
    }


def delimit_human_relay(events, limit=None):
    """Separate an observed relay count from a numeric limit.

    ``events is None`` means nobody counted. That is not a count of zero.
    A list is a count, including an empty list. ``limit`` is only a budget.
    """
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("human relay limit must be a non-negative int")
    record = {"limit": limit, "shell_unlocked": False}
    if events is None:
        record["status"] = "UNCOUNTED"
        return record
    if isinstance(events, (str, bytes)) or not isinstance(events, (list, tuple)):
        raise ValueError("human relay events must be a list or left uncounted")
    for event in events:
        if not isinstance(event, str) or not event.strip():
            raise ValueError("each human relay event needs a non-empty label")
    record["status"] = "COUNTED"
    record["count"] = len(events)
    if limit is not None:
        record["within_limit"] = record["count"] <= limit
    return record
