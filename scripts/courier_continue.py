from __future__ import annotations

import argparse
import sys
import subprocess
import os
import json
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

try:
    from scripts.resource_policy import (
        ChiefContextPackageBuilder,
        FileManifestTracker,
        TaskDedupeEngine
    )
    from scripts.agent_handoff_ledger import freshness, load_bundle, update
except ImportError as e:
    print(f"Failed to import required primitives: {e}")
    sys.exit(1)

def get_runtime_truth():
    import subprocess
    import os
    import json
    if "MOCK_SHA" in os.environ:
        return os.environ["MOCK_SHA"]
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    truth_script = os.path.join(repo_root, "scripts", "runtime_truth.py")
    try:
        out = subprocess.check_output(["python3", truth_script], stderr=subprocess.DEVNULL).decode()
        info = json.loads(out)
        return info.get("ACTUAL_SERVING_RUNTIME_SHA", "UNKNOWN")
    except Exception:
        return "UNKNOWN"

def get_runtime_identity():
    import os
    import socket
    # Stable machine identity, not git SHA and not per-process:
    # a pid changes on every run and would keep the ledger permanently stale.
    injected = os.environ.get("COURIER_RUNTIME_IDENTITY", "")
    if injected.strip():
        return injected.strip()
    if "MOCK_LEDGER" in os.environ:
        try:
            from scripts.agent_handoff_ledger import load_bundle
            from pathlib import Path
            b = load_bundle(Path(os.environ["MOCK_LEDGER"]))
            return b["record"].get("RUNTIME_IDENTITY") or b["acceptance_guard"]["binding"].get("runtime_identity")
        except Exception:
            pass
    # Prefer an explicitly injected identity from the launcher.
    if "MOCK_RUNTIME_IDENTITY" in os.environ and os.environ["MOCK_RUNTIME_IDENTITY"].strip():
        return os.environ["MOCK_RUNTIME_IDENTITY"].strip()
    if "MOCK_SHA" in os.environ:
        return os.environ["MOCK_SHA"]
    return socket.gethostname()

def get_git_info():
    if "MOCK_SHA" in os.environ and "MOCK_BRANCH" in os.environ:
        return os.environ["MOCK_BRANCH"], os.environ["MOCK_SHA"]
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
        sha = subprocess.check_output([
            "git", "log", "-1", "--format=%H", "--", ".", ":(exclude)agent_handoff_ledger.json"
        ]).decode().strip()
        if not sha:
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        return branch, sha
    except subprocess.CalledProcessError:
        return "UNKNOWN", "UNKNOWN"


def check_freshness(ledger_path, branch, sha):
    bundle = load_bundle(ledger_path)
    runtime_id = get_runtime_identity()
    
    # NEW: Determine actual serving runtime SHA

    actual_runtime_sha = get_runtime_truth()
    if actual_runtime_sha != "UNKNOWN" and actual_runtime_sha != sha:
        print(f"ERROR: Acceptance for SHA {sha} while actual runtime is SHA {actual_runtime_sha}: FAIL CLOSED.")
        print("You must deploy the new code using the canonical authorized deployment mechanism first!")
        sys.exit(1)

    else:
        result = freshness(bundle, branch, sha, "NO_FURTHER_ACTION", [], runtime_id)
        
    if result.get("FRESHNESS") == "STALE":

        print(f"ERROR: Ledger is stale. Fail closed. Runtime or SHA changed. Reasons: {result}")

        updates = {"CURRENT_SHA": sha, "BRANCH": branch, "RUNTIME_IDENTITY": runtime_id}
        guard = bundle["acceptance_guard"]
        guard["transition_state"] = "PROVISIONAL"
        guard["binding"]["current_sha"] = sha
        guard["binding"]["branch"] = branch
        guard["binding"]["runtime_identity"] = runtime_id
        guard["evidence"] = [ev for ev in guard.get("evidence", []) if ev.get("source_type") != "MACHINE_ARTIFACT"]
        if "ISSUE_STATE" in guard["acceptance_predicate"]["results"]:
            guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
            guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = []

        if not guard["evidence"]:
            guard["evidence"].append({
                "source_type": "GITHUB_COMMIT",
                "source_url": f"https://github.com/happyhippovip/2026-courier/commit/{sha}",
                "observed_at": "2026-09-17T12:00:00Z",
                "evidence_sha": sha,
                "runtime_binding": f"{branch}@{sha}",
                "validity": "UNKNOWN",
                "reason": "Latest commit"
            })
        
        bundle = update(ledger_path, bundle["revision"], updates, "Google-Antigravity", 5.0, guard)
    return bundle

def compute_frontier(record: dict):
    proven = set(record.get("PROVEN_EDGES", []))
    unproven = record.get("UNPROVEN_EDGES", [])
    
    capability_map = {
        "LEDGER/HANDOFF": ["git", "file_write"],
        "PR41 ACCEPTANCE": ["git_merge", "code_analysis", "reasoning"],
        "RELEASE - SAFE_AUTOMATABLE_PREPARATION": ["shell", "build_tools"],
        "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION": ["github_actions", "api"],
        "PUBLICATION VERIFICATION": ["http_client"],
        "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION": ["email_processing"],
        "SALES PACKAGE - SAFE_AUTOMATABLE_PREPARATION": ["markdown", "file_write", "reasoning"],
        "FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION": ["intake_execution", "reasoning"],
        "PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION": ["payment_mechanism"],
        "POST-PILOT HARDENING - SAFE_AUTOMATABLE_PREPARATION": ["refactoring", "testing", "reasoning"],
        "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION": ["social_api", "press_api"],
        "ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION": ["shell", "build_tools"]
    }
    
    # Durable state is both the membership and ordering authority.  A desired
    # or static plan would reorder actual work or hide previously unknown edges.
    tasks = []
    for edge in unproven:
        if edge not in proven:
            scope = "dependent"
            if "independent" in edge.lower() or any(k in edge for k in ["PUBLIC DEPLOYMENT", "PUBLICATION VERIFICATION", "PILOT INTAKE", "SALES PACKAGE", "POST-PILOT HARDENING", "FIRST PILOT", "PAYMENT", "ONBOARD"]):
                scope = "independent"

            task_digest = hashlib.sha256(edge.encode("utf-8")).hexdigest()[:16]
            tasks.append({
                "id": f"TASK-{task_digest}",
                "instruction": f"Prove edge: {edge}",
                "scope": scope,
                "edge_name": edge,
                "capabilities": capability_map.get(edge, [])
            })

    return tasks


def _is_human_or_external_gate(edge_name: str) -> bool:
    upper = edge_name.upper()
    return any(
        marker in upper
        for marker in (
            "IRREVERSIBLE_HUMAN_ACTION",
            "AUTHORIZED_MACHINE_ACTION",
            "PAYMENT_ONLY_WHEN_ACTUALLY_REQUIRED",
            "PAYMENT ONLY WHEN ACTUALLY REQUIRED",
            "ONBOARD_FIRST_PILOT_CUSTOMER",
        )
    ) and "SAFE_AUTOMATABLE_PREPARATION" not in upper


def select_safe_frontier(
    record: dict,
    tasks: list[dict],
    blocked_edges: set[str] | None = None,
    running_edges: set[str] | None = None,
    worker_capabilities: set[str] | None = None,
) -> list[dict]:
    """Return currently executable work without treating one blocker globally."""
    blocked_edges = blocked_edges or set()
    running_edges = running_edges or set()
    collision_scope = set(record.get("COLLISION_SCOPE", []))
    selected = []
    selected_chains = set()

    def collides_with_owned_scope(edge_name: str) -> bool:
        """Match canonical logical scopes, not only literal task names.

        Durable ownership commonly names a scope such as ``Ledger`` while the
        task frontier names a child edge such as ``LEDGER/HANDOFF``.  Literal
        equality would let the child edge bypass the active writer claim.
        Delimiter-aware matching avoids both that bypass and broad substring
        matches (for example, ``RELEASE`` must not match ``PRE-RELEASE``).
        """
        edge_key = edge_name.strip().casefold()
        for owned_scope in collision_scope:
            scope_key = str(owned_scope).strip().casefold()
            if not scope_key:
                continue
            if edge_key == scope_key or any(
                edge_key.startswith(scope_key + delimiter)
                for delimiter in ("/", " - ", ":")
            ):
                return True
        return False

    for task in tasks:
        edge = task["edge_name"]
        if edge in blocked_edges or edge in running_edges or collides_with_owned_scope(edge):
            continue
        if _is_human_or_external_gate(edge):
            continue
        required = set(task.get("capabilities", []))
        if worker_capabilities is not None and not required.issubset(
            worker_capabilities
        ):
            continue

        # Preserve sequential execution inside one chain, but only an actually
        # selected safe task occupies that chain.  A human/provider-blocked
        # earlier item must not hide safe preparation or unrelated work.
        chain = edge.split(" - ", 1)[0]
        if chain in selected_chains:
            continue
        selected_chains.add(chain)
        selected.append(task)

    return selected


def derive_frontier_updates(
    record: dict,
    guard: dict,
    tasks: list[dict],
    safe_tasks: list[dict],
    running_edges: set[str] | None = None,
) -> dict:
    """Derive durable NEXT/idle truth solely from current observable state."""
    running_edges = running_edges or set()
    updates = {}
    guard_accepted = guard.get("transition_state") == "CANONICAL_ACCEPTED"
    binding = guard.get("binding", {})
    has_bound_machine_evidence = any(
        item.get("source_type") == "MACHINE_ARTIFACT"
        and item.get("validity") == "VALID"
        and item.get("evidence_sha") == binding.get("current_sha")
        and item.get("runtime_binding") == binding.get("runtime_identity")
        for item in guard.get("evidence", [])
    )
    status = record.get("STATUS", "")
    blocker = str(record.get("FIRST_CAUSAL_BLOCKER", "")).strip()
    checkpoint = str(record.get("CONTINUATION_CHECKPOINT", "")).strip().lower()
    checkpoint_pending = checkpoint not in {"", "none", "complete", "completed"}
    resumable_wait = status == "WAITING_PROVIDER" or "WAITING_PROVIDER" in str(
        record.get("FIRST_CAUSAL_BLOCKER", "")
    )
    blocker_pending = blocker not in {"", "NONE", "NO_FURTHER_ACTION"}
    nonterminal_status = status not in {"DONE", "COMPLETED", "CLEAN_IDLE"}
    unfinished = bool(
        tasks
        or safe_tasks
        or running_edges
        or checkpoint_pending
        or resumable_wait
        or blocker_pending
        or record.get("ACTIVE_WRITERS")
        or nonterminal_status
    )

    if safe_tasks:
        next_action = safe_tasks[0]["instruction"]
    elif running_edges:
        next_action = "Await and reconcile running work: " + ", ".join(
            sorted(running_edges)
        )
    elif resumable_wait:
        next_action = "Resume provider-waiting work from durable checkpoint"
    elif checkpoint_pending:
        next_action = "Recover pending durable continuation checkpoint"
    elif tasks:
        next_action = "Waiting for eligibility/authority: " + tasks[0]["edge_name"]
    elif status in {"READY", "RUNNING", "DISPATCHED"}:
        next_action = f"Reconcile recorded {status} work"
    elif blocker_pending:
        next_action = "Resolve durable blocker: " + blocker
    elif record.get("ACTIVE_WRITERS"):
        next_action = "Reconcile active writers: " + ", ".join(
            sorted(record["ACTIVE_WRITERS"])
        )
    elif nonterminal_status:
        next_action = "Reconcile nonterminal status: " + status
    elif not guard_accepted and not has_bound_machine_evidence:
        next_action = "Obtain independently authenticated physical evidence"
    elif not guard_accepted:
        next_action = "Independent Acceptance Guard must establish completion"
    else:
        next_action = "NONE"

    if record.get("NEXT_EXECUTABLE_ACTION") != next_action:
        updates["NEXT_EXECUTABLE_ACTION"] = next_action

    clean_idle = "YES" if guard_accepted and not unfinished else "NO"
    if record.get("CLEAN_IDLE") != clean_idle:
        updates["CLEAN_IDLE"] = clean_idle
    queue_independent = "YES" if clean_idle == "YES" else "NO"
    if record.get("QUEUE_INDEPENDENT") != queue_independent:
        updates["QUEUE_INDEPENDENT"] = queue_independent

    if not guard_accepted and not tasks and not running_edges:
        if resumable_wait:
            target_status = "WAITING_PROVIDER"
        elif has_bound_machine_evidence:
            target_status = "WAITING_ACCEPTANCE_GUARD"
        else:
            target_status = "WAITING_PHYSICAL_PROOF"
            if record.get("FIRST_CAUSAL_BLOCKER") != "MISSING_PHYSICAL_ACCEPTANCE_EVIDENCE":
                updates["FIRST_CAUSAL_BLOCKER"] = "MISSING_PHYSICAL_ACCEPTANCE_EVIDENCE"
        if record.get("STATUS") != target_status:
            updates["STATUS"] = target_status

    return updates

def execute_task(task, ledger_path, record):
    import os
    print(f"Executing/Delegating task: {task['instruction']}")
    edge = task["edge_name"]

    if edge in ["SALES PACKAGE", "SALES_PACKAGE"]:
        import os
        sales_file = "public/SALES_PACKAGE.md"
        if not os.path.exists("public"):
            os.makedirs("public")
        with open(sales_file, "w") as f:
            f.write("# Courier Pilot Sales Package\n\nContact us for the first pilot.\nRequirements: Must have a public repository.\n")
        print("Execution candidate completed; independent evidence required: SALES PACKAGE")
        return task, True, None

    elif edge in ["POST-PILOT HARDENING", "POST_PILOT_HARDENING"]:
        return task, False, "UNVERIFIED_EXTERNAL_EFFECT_POST-PILOT HARDENING"

    elif edge in ["PR41 ACCEPTANCE", "PR41_ACCEPTANCE"]:
        try:
            import subprocess as sp
            current_head = sp.check_output(["git", "rev-parse", "HEAD"], timeout=10).decode().strip()
            sp.check_output(["git", "merge-base", "--is-ancestor", "6170850b", current_head], timeout=10)
            print("Local ancestry check passed; independent evidence required: PR41 ACCEPTANCE")
            return task, True, None
        except Exception:
            return task, False, "UNVERIFIED_EXTERNAL_EFFECT_PR41 ACCEPTANCE"

    elif edge == "LEDGER/HANDOFF":
        import os
        if not os.path.exists(ledger_path):
            return task, False, "UNVERIFIED_EXTERNAL_EFFECT_LEDGER/HANDOFF"
        return task, True, None

    elif edge in ["PAYMENT ONLY WHEN ACTUALLY REQUIRED", "PAYMENT_ONLY_WHEN_ACTUALLY_REQUIRED"]:
        return task, False, "MONEY_REQUIRED_PAYMENT_PROOF"

    elif edge == "ONBOARD_FIRST_PILOT_CUSTOMER":
        return task, False, "HUMAN_REQUIRED_PILOT_ONBOARDING"

    elif edge in ["RELEASE", "PUBLIC DEPLOYMENT", "PUBLIC_DEPLOYMENT", "FIRST PILOT", "FIRST_PILOT", "PILOT INTAKE", "PILOT_INTAKE", "EXTERNAL_PUBLICATION"]:
        # Bare external names fail closed with external-effect semantics even
        # even though split stage names are preferred; the generic fallback
        # alone would mislabel these known-dangerous edges.
        return task, False, f"UNVERIFIED_EXTERNAL_EFFECT_{edge}"

    elif "SAFE_AUTOMATABLE_PREPARATION" in edge:
        return task, False, f"UNIMPLEMENTED_SAFE_PREPARATION_{edge}"

    elif "AUTHORIZED_MACHINE_ACTION" in edge:
        return task, False, f"UNVERIFIED_EXTERNAL_EFFECT_{edge}"

    elif "IRREVERSIBLE_HUMAN_ACTION" in edge:
        return task, False, f"UNVERIFIED_EXTERNAL_EFFECT_{edge}"
        
    elif edge == "PUBLICATION VERIFICATION":
        return task, False, "UNVERIFIED_EXTERNAL_EFFECT_PUBLICATION VERIFICATION"

    else:
        # Fallback for unrecognized test edges: fail closed
        return task, False, f"UNRECOGNIZED_OR_UNVERIFIED_TASK_{edge}"

def update_ledger(ledger_path, edge_name, blocker, bundle):
    revision = bundle["revision"]
    record = bundle["record"]
    proven = list(record.get("PROVEN_EDGES", []))
    unproven = list(record.get("UNPROVEN_EDGES", []))
    
    updates = {}
    if blocker:
        updates["FIRST_CAUSAL_BLOCKER"] = blocker
        updates["STATUS"] = "BLOCKED"
        updates["CLEAN_IDLE"] = "NO"
    else:
        if edge_name and edge_name != "CLEAN_IDLE_ACHIEVED":
            # An execution result is a candidate fact, not independent proof.
            # This legacy continuation path has no authenticated evidence
            # admission boundary, so it must not promote its own work into
            # PROVEN_EDGES or remove it from the durable frontier.
            updates["FIRST_CAUSAL_BLOCKER"] = (
                f"AWAITING_INDEPENDENT_EVIDENCE_{edge_name}"
            )
            updates["NEXT_EXECUTABLE_ACTION"] = (
                f"Independent verifier must authenticate evidence for: {edge_name}"
            )
            updates["QUEUE_INDEPENDENT"] = "NO"
            updates["CLEAN_IDLE"] = "NO"
            updates["STATUS"] = "WAITING_ACCEPTANCE_GUARD"
            
    guard = bundle["acceptance_guard"]
    binding = guard["binding"]
    
    has_physical_proof = any(
        e.get("source_type") == "MACHINE_ARTIFACT" and
        e.get("evidence_sha") == binding["current_sha"] and
        e.get("validity") == "VALID"
        for e in guard.get("evidence", [])
    )
    
    if not unproven:
        if has_physical_proof:
            updates["NEXT_EXECUTABLE_ACTION"] = (
                "Independent Acceptance Guard must authenticate the bound "
                "physical evidence"
            )
            updates["QUEUE_INDEPENDENT"] = "NO"
            updates["CLEAN_IDLE"] = "NO"
            updates["STATUS"] = "WAITING_ACCEPTANCE_GUARD"
            guard["transition_state"] = "PROVISIONAL"
        else:
            updates["QUEUE_INDEPENDENT"] = "NO"
            updates["CLEAN_IDLE"] = "NO"
            updates["STATUS"] = "WAITING_PHYSICAL_PROOF"
            updates["FIRST_CAUSAL_BLOCKER"] = "MISSING_PHYSICAL_ACCEPTANCE_EVIDENCE"
            guard["transition_state"] = "PROVISIONAL"
            if "ISSUE_STATE" in guard["acceptance_predicate"]["results"]:
                guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
                guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["observed_value"] = "NO_FURTHER_ACTION"
    elif "ISSUE_STATE" in guard["acceptance_predicate"]["results"]:
        guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["observed_value"] = "NO_FURTHER_ACTION"

    new_bundle = update(
        ledger_path,
        revision,
        updates,
        "Google-Antigravity",
        5.0,
        guard
    )
    return new_bundle

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run unattended mode")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()
    
    mock_iters = 0

    repo_dir = Path(__file__).parent.parent.resolve()
    blocked_tasks_this_run = set()
    ledger_path_str = os.environ.get("MOCK_LEDGER")
    ledger_path = Path(ledger_path_str) if ledger_path_str else repo_dir / "agent_handoff_ledger.json"
    
    if not ledger_path.exists():
        print("ERROR: agent_handoff_ledger.json not found.")
        sys.exit(1)

    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    running_tasks = {} # mapping task edge_name to future
    
    while True:
        branch, sha = get_git_info()
        bundle = check_freshness(ledger_path, branch, sha)
        record = bundle["record"]

        # Reconcile completed executions before deriving or dispatching from
        # the frontier.  Otherwise a result arriving between snapshots can
        # cause stale work to be dispatched once more.
        completed_edges = [
            edge for edge, future in running_tasks.items() if future.done()
        ]
        if completed_edges:
            for edge_name in completed_edges:
                future = running_tasks.pop(edge_name)
                try:
                    task, success, new_blocker = future.result()
                except Exception as exc:
                    # Uncertainty is durable blocked state, never implicit idle.
                    current = load_bundle(ledger_path)
                    if edge_name in current["record"].get("UNPROVEN_EDGES", []):
                        update_ledger(
                            ledger_path,
                            edge_name,
                            f"EXECUTION_EXCEPTION_{type(exc).__name__}",
                            current,
                        )
                    blocked_tasks_this_run.add(edge_name)
                    print(f"Task {edge_name} failed closed: {type(exc).__name__}")
                    continue

                print(f"\n=== FINISHED TASK: {task['edge_name']} ===")
                current = load_bundle(ledger_path)
                if task["edge_name"] in current["record"].get(
                    "UNPROVEN_EDGES", []
                ):
                    update_ledger(
                        ledger_path,
                        task["edge_name"],
                        new_blocker,
                        current,
                    )
                # Successful execution is still waiting for independent
                # evidence, so it must not be re-executed in this process.
                blocked_tasks_this_run.add(task["edge_name"])

            # A completion changes the authoritative frontier.  Reload before
            # any selection instead of using the pre-result cached snapshot.
            continue

        tasks = compute_frontier(record)
        worker_caps_env = os.environ.get("COURIER_WORKER_CAPABILITIES", "all")
        worker_capabilities = (
            None
            if worker_caps_env == "all"
            else {item for item in worker_caps_env.split(",") if item}
        )
        safe_executable_tasks = select_safe_frontier(
            record,
            tasks,
            blocked_tasks_this_run,
            set(running_tasks),
            worker_capabilities,
        )

        frontier_updates = derive_frontier_updates(
            record,
            bundle["acceptance_guard"],
            tasks,
            safe_executable_tasks,
            set(running_tasks),
        )
        if frontier_updates:
            try:
                update(
                    ledger_path,
                    bundle["revision"],
                    frontier_updates,
                    "Google-Antigravity",
                    5.0,
                )
            except Exception as exc:
                if "revision conflict" in str(exc):
                    continue
                raise
            # The durable NEXT/status transition is now newer than this local
            # snapshot.  Reload and rederive before dispatch.
            continue

        first_blocker = record.get("FIRST_CAUSAL_BLOCKER", "")

        if not args.run:
            print(f"Goal: {record.get('GOAL')}")
            print(f"Branch/SHA: {branch} / {sha}")
            print(f"Active Writers: {record.get('ACTIVE_WRITERS', [])}")

        if not safe_executable_tasks:
            if tasks:
                print(f"WAITING: No safe, unowned, independent executable tasks exist.")
                print(f"Blockers: {first_blocker}")
            else:
                print("NO EXECUTABLE FRONTIER: acceptance remains authoritative.")
                if (
                    bundle["record"].get("CLEAN_IDLE") == "YES"
                    and bundle["acceptance_guard"].get("transition_state")
                    == "CANONICAL_ACCEPTED"
                ):
                    print("GLOBAL STOP: CLEAN_IDLE. All tasks completed.")
                else:
                    print(
                        "WAITING: Empty frontier is not accepted completion; "
                        f"status={bundle['record'].get('STATUS')}."
                    )
            if args.once and not running_tasks:
                sys.exit(0)
            if "MOCK_SHA" in os.environ:
                mock_iters += 1
                if mock_iters >= 3:
                    sys.exit(0)
            import time
            time.sleep(1.0)
            continue
            
        if not args.run:
            next_task = safe_executable_tasks[0]
            print(f"Selected Next Action: {next_task['instruction']}")
            manifest = FileManifestTracker.build_manifest([str(ledger_path.resolve())], repo_dir)
            dedupe_engine = TaskDedupeEngine(repo_dir)
            task_hash = dedupe_engine.compute_task_hash(
                "continuation", next_task["instruction"], "Google-Antigravity", [str(ledger_path.resolve())]
            )
            package = ChiefContextPackageBuilder.build_compact_package(
                record.get("GOAL", "TEST"), next_task["id"], next_task["instruction"],
                [str(ledger_path.resolve())], 1, {"file_manifest": manifest, "task_dedupe_hash": task_hash}, repo_dir
            )
            print("\n--- MINIMAL TASK PACKET ---")
            print(json.dumps(package, indent=2))
            sys.exit(0)
            
        # Submit new tasks
        newly_submitted = []
        for t in safe_executable_tasks:
            if (
                t["edge_name"] not in running_tasks
                and t["edge_name"] not in blocked_tasks_this_run
            ):
                print(f"\n=== SUBMITTING TASK: {t['edge_name']} ===")
                running_tasks[t["edge_name"]] = executor.submit(execute_task, t, ledger_path, record)
                newly_submitted.append(t["edge_name"])
        
        if newly_submitted:
            once_dispatched = True
        if newly_submitted or running_tasks:
            print(f"\nCurrently running {len(running_tasks)} tasks concurrently.")
            
        import time
        time.sleep(1)

        
        if args.once and not running_tasks and 'once_dispatched' in locals():
            sys.exit(0)
        if "MOCK_SHA" in os.environ:
            mock_iters += 1
            if mock_iters >= 3:
                sys.exit(0)
        import time
        time.sleep(1.0)

if __name__ == "__main__":
    main()
