"""Deterministic project readiness, derived only from acceptance/registry.yaml.

Law: progress is the share of acceptance checks proven at their required evidence level on
the current version. Everything else is shown as working, blocked or unknown, and the number
goes down when the proof goes away.

This module is the only producer of readiness percentages. Nothing here stores or accepts a
hand-typed percentage. A criterion declared VERIFIED is still not credited when its evidence
is missing, below the required level, invalidated, blocked, stale, proven on a version whose
relevant files changed, or proven against an older acceptance definition.
"""
import argparse
import datetime
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

STATES = ("VERIFIED", "IN_PROGRESS", "BLOCKED", "NOT_STARTED", "UNKNOWN")
STATE_ALIASES = {"IN_FLIGHT": "IN_PROGRESS"}
DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "acceptance" / "registry.yaml"
MARKS = {"VERIFIED": "✓", "IN_PROGRESS": "•", "BLOCKED": "!", "NOT_STARTED": "?", "UNKNOWN": "?"}
CUSTOMER_STATUS = {"VERIFIED": "verified", "IN_PROGRESS": "working", "BLOCKED": "blocked",
                   "NOT_STARTED": "unknown", "UNKNOWN": "unknown"}
HUMAN_OWNERS = {"you", "human", "founder", "customer"}
V1_SCOPES = ("V1",)
FIRST_REAL_USE_SCOPES = ("V1", "FIRST_REAL_USE")
# When several rules fire, the result is the most serious one.
REGRESSION_PRIORITY = ("BLOCKED", "UNKNOWN", "IN_PROGRESS")


def load_registry(path=DEFAULT_REGISTRY):
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml  # only needed when the registry is not written in JSON syntax

        return yaml.safe_load(text)


def level_ids(registry):
    return [level["id"] if isinstance(level, dict) else level for level in registry["evidence_levels"]]


def normalize_state(state):
    return STATE_ALIASES.get(state, state)


def _forbid_typed_numbers(where, mapping):
    for key in mapping:
        lowered = str(key).lower()
        if "percent" in lowered or lowered in ("progress", "readiness", "score"):
            raise ValueError(f"{where}: hand-typed '{key}' is not allowed; numbers are derived")


def validate(registry):
    levels = level_ids(registry)
    _forbid_typed_numbers("registry", registry)
    stage_ids = []
    for stage in registry["stages"]:
        _forbid_typed_numbers(f"stage {stage.get('id')}", stage)
        if stage["id"] in stage_ids:
            raise ValueError(f"duplicate stage id: {stage['id']}")
        stage_ids.append(stage["id"])
    gate = registry.get("next_gate")
    if gate is not None and gate not in stage_ids:
        raise ValueError(f"next_gate names an unknown stage: {gate}")
    seen = set()
    for item in registry["criteria"]:
        _forbid_typed_numbers(f"criterion {item.get('id')}", item)
        if item["id"] in seen:
            raise ValueError(f"duplicate criterion id: {item['id']}")
        seen.add(item["id"])
        if item["stage"] not in stage_ids:
            raise ValueError(f"{item['id']}: unknown stage {item['stage']}")
        state = normalize_state(item["state"])
        if state not in STATES:
            raise ValueError(f"{item['id']}: unknown state {item['state']}")
        for key in ("required_evidence_level", "evidence_level"):
            if item.get(key, levels[0]) not in levels:
                raise ValueError(f"{item['id']}: unknown evidence level {item.get(key)}")
        if state == "BLOCKED" and not item.get("blocker"):
            raise ValueError(f"{item['id']}: BLOCKED needs a named blocker")
        if not item.get("customer_label"):
            raise ValueError(f"{item['id']}: customer_label is required")


def _matches(path, patterns):
    path = path.replace("\\", "/")
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def effective_state(item, registry, today, current_version, changed_paths=None):
    """Return (state, reasons). Only a declared VERIFIED can be regressed here."""
    declared = normalize_state(item["state"])
    if declared != "VERIFIED":
        return declared, []
    levels = level_ids(registry)
    fresh = item.get("freshness") or {}
    found = []  # (state, one-line reason)

    if item.get("blocker"):
        found.append(("BLOCKED", f"blocker found: {item['blocker']}"))
    if not item.get("evidence_ref") or not item.get("evidence_sha"):
        found.append(("UNKNOWN", "no evidence attached"))
    have, need = item.get("evidence_level", levels[0]), item["required_evidence_level"]
    if levels.index(have) < levels.index(need):
        found.append(("IN_PROGRESS", f"evidence at {have} is below the required {need}"))
    if item.get("invalidated"):
        found.append(("UNKNOWN", "evidence invalidated"))
    if item.get("contradicted_by"):
        found.append(("UNKNOWN", f"contradicted by {item['contradicted_by']}"))
    if item.get("definition_rev") is not None and fresh.get("verified_definition_rev") != item["definition_rev"]:
        found.append(("UNKNOWN", "acceptance definition changed since it was proven"))

    proven_on = fresh.get("verified_version")
    if current_version and proven_on != current_version:
        watch = fresh.get("watch_paths") or []
        changed = changed_paths(proven_on) if callable(changed_paths) else changed_paths
        if not watch or changed is None:
            found.append(("UNKNOWN", f"needs re-confirming: version moved from {proven_on} to {current_version}"))
        else:
            touched = sorted(path for path in changed if _matches(path, watch))
            if touched:
                found.append(("UNKNOWN", f"needs re-confirming: {touched[0]} changed since {proven_on}"))

    verified_at = fresh.get("verified_at")
    if not verified_at:
        found.append(("UNKNOWN", "no verification date"))
    else:
        window = fresh.get("max_age_days")
        if window is None:
            window = (registry.get("freshness_days") or {}).get(have)
        age = (today - datetime.date.fromisoformat(verified_at)).days
        if window is not None and age > window:
            found.append(("UNKNOWN", f"evidence is {age} days old (limit {window})"))

    if not found:
        return "VERIFIED", []
    state = next(s for s in REGRESSION_PRIORITY if any(f[0] == s for f in found))
    return state, [reason for _, reason in found]


def percent(part, total):
    return round(100.0 * part / total, 1) if total else 0.0


def summarize(states):
    total = len(states)
    verified = states.count("VERIFIED")
    working = states.count("IN_PROGRESS")
    blocked = states.count("BLOCKED")
    shares = [percent(verified, total), percent(working, total), percent(blocked, total)]
    return {
        "total": total, "verified": verified, "in_progress": working, "blocked": blocked,
        "unknown_remaining": total - verified - working - blocked,
        "verified_percent": shares[0], "in_progress_percent": shares[1], "blocked_percent": shares[2],
        # The four shares always sum to exactly 100; rounding lands in the unknown segment.
        "unknown_remaining_percent": round(100.0 - sum(shares), 1) if total else 0.0,
    }


def stage_state(summary):
    if summary["total"] == 0:
        return "NOT_STARTED"
    if summary["verified"] == summary["total"]:
        return "VERIFIED"
    if summary["blocked"]:
        return "BLOCKED"
    if summary["in_progress"] or summary["verified"]:
        return "IN_PROGRESS"
    return "UNKNOWN"


def needs_you(item, state):
    owner = str(item.get("owner") or "").lower()
    return state != "VERIFIED" and (bool(item.get("needs_you")) or owner in HUMAN_OWNERS)


def freshness_window(item, registry):
    fresh = item.get("freshness") or {}
    if fresh.get("max_age_days") is not None:
        return fresh["max_age_days"]
    return (registry.get("freshness_days") or {}).get(item.get("evidence_level"))


def compute(registry, today=None, current_version=None, changed_paths=None):
    """Pure function of the registry plus (today, current_version, changed_paths)."""
    validate(registry)
    today = today or datetime.date.today()
    current_version = current_version or registry.get("current_version")
    evaluated = []
    for item in registry["criteria"]:
        state, reasons = effective_state(item, registry, today, current_version, changed_paths)
        evaluated.append({"item": item, "state": state, "regress_reasons": reasons})

    scope_of = {stage["id"]: stage.get("scope", "V1") for stage in registry["stages"]}
    stages = []
    for stage in registry["stages"]:
        rows = [row for row in evaluated if row["item"]["stage"] == stage["id"]]
        substages = {}
        for row in rows:
            substages.setdefault(row["item"].get("substage") or "General", []).append(row)
        summary = summarize([row["state"] for row in rows])
        stages.append({"stage": stage, "summary": summary, "state": stage_state(summary), "substages": substages})

    def scope_summary(scopes):
        return summarize([row["state"] for row in evaluated if scope_of[row["item"]["stage"]] in scopes])

    def open_stage(candidate):
        return candidate["summary"]["total"] > 0 and candidate["state"] != "VERIFIED"

    by_id = {entry["stage"]["id"]: entry for entry in stages}
    gate = by_id.get(registry.get("next_gate"))
    if gate is None or not open_stage(gate):
        gate = next((entry for entry in stages if open_stage(entry)), None)

    return {
        "project": registry.get("project", "Project"),
        "current_version": current_version,
        "today": today.isoformat(),
        "criteria_total": len(evaluated),
        "overall": scope_summary(V1_SCOPES),
        "first_real_use": scope_summary(FIRST_REAL_USE_SCOPES),
        "stages": stages,
        "evaluated": evaluated,
        "next_milestone": None if gate is None else {
            "stage": gate["stage"]["id"],
            "customer_label": gate["stage"].get("milestone_label") or gate["stage"]["customer_label"],
            **gate["summary"]},
    }


# ---- views ---------------------------------------------------------------------------
def _num(value):
    return str(int(value)) if float(value).is_integer() else str(value)


def customer_view(result):
    stages, later, needs, reconfirm = [], [], [], 0
    for stage in result["stages"]:
        summary = stage["summary"]
        if not summary["total"]:
            continue  # extension stages without checks are not shown to customers
        if stage["stage"].get("scope", "V1") not in V1_SCOPES:
            # Outside the headline number: named with its own count, never mixed into it.
            later.append({"label": stage["stage"]["customer_label"], "checks_verified": summary["verified"],
                          "checks_total": summary["total"]})
            continue
        substages = []
        for label, rows in stage["substages"].items():
            items = []
            for row in rows:
                waiting = needs_you(row["item"], row["state"])
                if waiting:
                    needs.append(row["item"]["customer_label"])
                reconfirm += 1 if row["regress_reasons"] else 0
                items.append({"label": row["item"]["customer_label"], "status": CUSTOMER_STATUS[row["state"]],
                              "needs_you": waiting, "needs_reconfirming": bool(row["regress_reasons"])})
            substages.append({"label": label, "items": items})
        stages.append({"label": stage["stage"]["customer_label"], "status": CUSTOMER_STATUS[stage["state"]],
                       "checks_verified": summary["verified"], "checks_total": summary["total"],
                       "substages": substages})
    overall, milestone = result["overall"], result["next_milestone"]
    view = {
        "project": result["project"],
        "verified_percent": overall["verified_percent"],
        "working_percent": overall["in_progress_percent"],
        "blocked_percent": overall["blocked_percent"],
        "not_started_or_unknown_percent": overall["unknown_remaining_percent"],
        "checks_verified": overall["verified"], "checks_total": overall["total"],
        "headline": f"{_num(overall['verified_percent'])}% verified",
        "segments": (f"Verified {_num(overall['verified_percent'])} · Working on {_num(overall['in_progress_percent'])} "
                     f"· Blocked {_num(overall['blocked_percent'])} · Not started {_num(overall['unknown_remaining_percent'])}"),
        "next_milestone": None if milestone is None else {
            "label": milestone["customer_label"], "checks_verified": milestone["verified"],
            "checks_total": milestone["total"], "being_worked_on": milestone["in_progress"],
            "waiting_on_fixes": milestone["blocked"], "not_started_or_unknown": milestone["unknown_remaining"]},
        "needs_you": needs,
        "checks_needing_reconfirmation": reconfirm,
        "stages": stages,
        "after_this": later,
    }
    if reconfirm:
        noun = "check needs" if reconfirm == 1 else "checks need"
        view["reconfirmation_note"] = f"{reconfirm} {noun} re-confirming after a change"
    return view


def dev_view(result, registry):
    today = datetime.date.fromisoformat(result["today"])
    stages, regressions, stale_soon = [], [], []
    for stage in result["stages"]:
        substages = []
        for label, rows in stage["substages"].items():
            items = []
            for row in rows:
                item, fresh = row["item"], dict(row["item"].get("freshness") or {})
                window = freshness_window(item, registry)
                if fresh.get("verified_at"):
                    fresh["age_days"] = (today - datetime.date.fromisoformat(fresh["verified_at"])).days
                    if window is not None:
                        fresh["expires_in_days"] = window - fresh["age_days"]
                        if row["state"] == "VERIFIED" and fresh["expires_in_days"] <= 1:
                            stale_soon.append(item["id"])
                for reason in row["regress_reasons"]:
                    regressions.append(f"{item['id']}: {reason}")
                items.append({
                    "id": item["id"], "title": item.get("title"), "customer_label": item["customer_label"],
                    "declared_state": normalize_state(item["state"]), "effective_state": row["state"],
                    "regress_reasons": row["regress_reasons"],
                    "required_evidence_level": item["required_evidence_level"],
                    "evidence_level": item.get("evidence_level"), "evidence_ref": item.get("evidence_ref"),
                    "evidence_sha": item.get("evidence_sha"), "owner": item.get("owner"), "freshness": fresh,
                    "blocker": item.get("blocker"), "next_action": item.get("next_action"),
                    "source": item.get("source"), "needs_you": needs_you(item, row["state"])})
            substages.append({"substage": label, "items": items})
        stages.append({"stage": stage["stage"]["id"], "scope": stage["stage"].get("scope", "V1"),
                       "state": stage["state"], **stage["summary"], "substages": substages})
    return {"project": result["project"], "current_version": result["current_version"], "today": result["today"],
            "criteria_total": result["criteria_total"], "overall_v1": result["overall"],
            "first_real_use": result["first_real_use"], "next_milestone": result["next_milestone"],
            "regression_log": regressions, "evidence_stale_within_a_day": stale_soon, "stages": stages}


def customer_tree(view):
    marks = {"verified": MARKS["VERIFIED"], "working": MARKS["IN_PROGRESS"], "blocked": "!", "unknown": "?"}
    lines = [f"Project readiness: {view['headline']}", view["segments"]]
    if view["next_milestone"]:
        m = view["next_milestone"]
        lines.append(f"Next milestone: \"{m['label']}\", {m['checks_verified']} of {m['checks_total']} checks verified "
                     f"· {m['being_worked_on']} being worked on · {m['waiting_on_fixes']} waiting on fixes")
    lines.append("Needs you: " + ("; ".join(view["needs_you"]) if view["needs_you"] else "none"))
    if view.get("reconfirmation_note"):
        lines.append(view["reconfirmation_note"])
    lines.append("")
    lines.append(view["project"])
    for stage in view["stages"]:
        lines.append(f"  {marks[stage['status']]} {stage['label']} "
                     f"({stage['checks_verified']} of {stage['checks_total']} verified)")
        for sub in stage["substages"]:
            lines.append(f"      {sub['label']}")
            for item in sub["items"]:
                tail = "  [Needs You]" if item["needs_you"] else ""
                tail += "  [needs re-confirming]" if item["needs_reconfirming"] else ""
                lines.append(f"          {marks[item['status']]} {item['label']}{tail}")
    for stage in view["after_this"]:
        lines.append(f"  After this: {stage['label']} ({stage['checks_verified']} of {stage['checks_total']} verified)")
    return "\n".join(lines)


def dev_tree(view):
    o, f = view["overall_v1"], view["first_real_use"]
    lines = [f"{view['project']} @ {view['current_version']} ({view['today']}), {view['criteria_total']} criteria",
             f"V1 (through clean machine): verified {o['verified']}/{o['total']} = {o['verified_percent']}% | "
             f"in progress {o['in_progress_percent']}% | blocked {o['blocked_percent']}% | "
             f"not started/unknown {o['unknown_remaining_percent']}%",
             f"First real use: verified {f['verified']}/{f['total']} = {f['verified_percent']}%"]
    if view["next_milestone"]:
        m = view["next_milestone"]
        lines.append(f"Next gate {m['stage']}: {m['verified']}/{m['total']} verified, {m['in_progress']} in progress, "
                     f"{m['blocked']} blocked, {m['unknown_remaining']} not started/unknown")
    for entry in view["regression_log"]:
        lines.append(f"REGRESSED {entry}")
    for cid in view["evidence_stale_within_a_day"]:
        lines.append(f"STALE SOON {cid}")
    for stage in view["stages"]:
        lines.append(f"{MARKS[stage['state']]} {stage['stage']} [{stage['scope']}] {stage['verified']}/{stage['total']} "
                     f"({stage['verified_percent']}%)")
        for sub in stage["substages"]:
            lines.append(f"    {sub['substage']}")
            for item in sub["items"]:
                lines.append(f"        {MARKS[item['effective_state']]} {item['id']} {item['effective_state']} | {item['title']} | "
                             f"level {item['evidence_level']}/{item['required_evidence_level']} | ref={item['evidence_ref']} "
                             f"sha={item['evidence_sha']} | owner={item['owner']} | "
                             f"freshness={json.dumps(item['freshness'], sort_keys=True)}")
                if item["blocker"]:
                    lines.append(f"            blocker: {item['blocker']}")
                lines.append(f"            next: {item['next_action']}")
    return "\n".join(lines)


def git_changed_paths(repo):
    """Resolver for --git: files changed between the version a check was proven on and HEAD."""
    cache = {}

    def resolve(proven_on):
        if not proven_on:
            return None
        if proven_on not in cache:
            done = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", f"{proven_on}..HEAD"],
                                  capture_output=True, text=True)
            cache[proven_on] = done.stdout.splitlines() if done.returncode == 0 else None
        return cache[proven_on]

    return resolve


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--view", choices=["customer", "dev"], default="customer")
    parser.add_argument("--format", choices=["json", "tree"], default="tree")
    parser.add_argument("--today", help="ISO date used for freshness (default: today)")
    parser.add_argument("--current-version", help="version the evidence must still hold on")
    parser.add_argument("--changed-path", action="append", help="file changed since the evidence (repeatable)")
    parser.add_argument("--git", action="store_true", help="resolve changed files with git diff <proven>..HEAD")
    args = parser.parse_args(argv)
    registry = load_registry(args.registry)
    today = datetime.date.fromisoformat(args.today) if args.today else None
    changed = git_changed_paths(Path(args.registry).resolve().parent.parent) if args.git else args.changed_path
    try:
        result = compute(registry, today=today, current_version=args.current_version, changed_paths=changed)
    except ValueError as error:
        print(f"registry invalid: {error}", file=sys.stderr)
        return 2
    view = customer_view(result) if args.view == "customer" else dev_view(result, registry)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.format == "json":
        print(json.dumps(view, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(customer_tree(view) if args.view == "customer" else dev_tree(view))
    return 0


if __name__ == "__main__":
    sys.exit(main())
