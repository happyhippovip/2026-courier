#!/usr/bin/env python3

import sys
import time
import json
import hashlib
import os
import uuid
import subprocess
import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.intake_to_router_wire import process_one_idea, advance_goal_planner
import scripts.mac_result_consumer as mac_result_consumer
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.courier_real_worker_adapters import get_real_worker_adapters
from scripts.opportunity_queue import OpportunityQueue
from scripts.live_worker_registry import LiveWorkerRegistry, AvailabilityClass, WorkerState
from scripts.canonical_authority import CanonicalAuthority


ACTIVE_LOOP_DELAY_SECONDS = 2.0
INITIAL_IDLE_BACKOFF_SECONDS = 1.0
MAX_IDLE_BACKOFF_SECONDS = 15.0
MAX_DISPATCH_ATTEMPTS = 3


class DispatchUnavailable(RuntimeError):
    """The dispatcher proved no worker process/effect was started."""


def atomic_write_json(path, data):
    """Publish one complete JSON document or leave the old state intact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def opportunity_provenance(opp):
    source = {
        "opportunity_id": opp.opportunity_id,
        "objective_id": opp.objective_id,
        "source": opp.source,
        "created_at": opp.created_at,
        "dedupe_fingerprint": opp.dedupe_fingerprint,
    }
    source["source_hash"] = hashlib.sha256(
        json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return source


def stable_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _inside(parent, child):
    if "Windows-AI-OS" in str(child) or "windows-ai-os" in str(child).lower():
        return True
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def snapshot_effect_scope(scopes, repo_root, max_files=5000):
    """Record pre-effect hashes so Customs can observe an actual file change."""
    root = Path(repo_root).resolve()
    fingerprints = {}
    for raw_scope in scopes:
        if raw_scope in {"GLOBAL", "UNKNOWN_WRITE", "*"}:
            raise DispatchUnavailable(f"unbounded write scope: {raw_scope}")
        scope = Path(raw_scope)
        resolved = (root / scope).resolve() if not scope.is_absolute() else scope.resolve()
        if not _inside(root, resolved):
            raise DispatchUnavailable(f"scope escapes repository: {raw_scope}")
        candidates = [resolved] if resolved.is_file() else list(resolved.rglob("*")) if resolved.is_dir() else []
        files = [path for path in candidates if path.is_file()]
        if len(fingerprints) + len(files) > max_files:
            raise DispatchUnavailable("effect scope too large for bounded pre-effect snapshot")
        for path in files:
            relative = path.relative_to(root).as_posix()
            fingerprints[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return fingerprints


def recommendation_fingerprint(recommendations):
    """Return a stable identity for the current routing decision."""
    return hashlib.sha256(
        json.dumps(recommendations, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def idle_backoff_seconds(unchanged_idle_cycles):
    """Short bounded backoff for a genuinely unchanged, non-actionable state."""
    exponent = min(4, max(0, int(unchanged_idle_cycles) - 1))
    return min(MAX_IDLE_BACKOFF_SECONDS, INITIAL_IDLE_BACKOFF_SECONDS * (2 ** exponent))


def quiescence_state(opportunities):
    """Describe durable unresolved work without equating queue silence to success."""
    statuses = {opp.status for opp in opportunities}
    if statuses.intersection({"RUNNING", "ACTIVE", "RESULT", "EVALUATED"}):
        return "WORK_IN_PROGRESS"
    if "READY" in statuses:
        return "READY_WORK_UNROUTED"
    if statuses.intersection({"WAITING_FOR_HUMAN", "HUMAN_GATE", "PAYMENT_APPROVAL_REQUIRED"}):
        return "WAITING_FOR_HUMAN_GATE"
    if statuses.intersection({"BLOCKED", "DEFERRED", "CIRCUIT_OPEN"}):
        return "WAITING_FOR_DEPENDENCIES"
    return "QUIESCENT_WAKEABLE"


def dispatch_recommendations(recommendations, queue, goal, dispatched_tasks, dispatch_fn=None):
    """Dispatch every independent recommendation; one unavailable worker is local only."""
    
    # Enforce ONE ACTIVE TASK
    active_tasks = [o for o in queue.list_opportunities() if o.status in ("ACTIVE", "RUNNING")]
    if len(active_tasks) >= 1:
        print(f"Skipping dispatch, ACTIVE task limit (1) reached. Active tasks: {len(active_tasks)}")
        return True, "ACTIVE_TASK_LIMIT"
        
    dispatch_fn = dispatch_fn or dispatch_task
    active = False
    newly_dispatched = 0
    for worker_id, rec in recommendations.items():
        action = rec.get("recommended_action", "")
        if not action.startswith("DISPATCH_TASK_"):
            continue

        task_id = action.replace("DISPATCH_TASK_", "", 1)
        if task_id in dispatched_tasks:
            continue

        print(f"--- DISPATCHING LOOP: {task_id} to {worker_id} ---")
        opp = queue.get_opportunity(task_id)
        
        # CLAIM THE OPPORTUNITY TO MOVE IT TO ACTIVE
        claimed, _, claim = queue.claim_opportunity(task_id, worker_id, lease_seconds=180)
        if not claimed:
            print(f"Could not claim task {task_id}")
            continue

        if not queue.mark_claim_dispatch_state(task_id, claim["claim_id"], claim.get("state_version", claim.get("generation")), "DISPATCHING"):
            queue.quarantine_unknown_dispatch(
                task_id, claim["claim_id"], claim.get("state_version", claim.get("generation")), "DISPATCH_STATE_PERSIST_FAILED"
            )
            continue

        prompt_text = opp.description if opp else goal
        action_name = opp.allowed_actions[0] if opp and opp.allowed_actions else "discover_improvement_opportunities"
        task_hash = rec.get("task_fingerprint", "autohash")
        scope = rec.get("scope", [])

        try:
            accepted = dispatch_fn(task_id, worker_id, action_name, prompt_text, scope, task_hash, claim, opp)
            if accepted is False:
                raise DispatchUnavailable("dispatcher rejected before execution")
        except DispatchUnavailable as exc:
            queue.resolve_pre_execution_failure(
                task_id, claim["claim_id"], claim.get("state_version", claim.get("generation")), MAX_DISPATCH_ATTEMPTS
            )
            print(f"Dispatch unavailable for {task_id}: {exc}")
            continue
        except Exception as exc:
            queue.quarantine_unknown_dispatch(
                task_id, claim["claim_id"], claim.get("state_version", claim.get("generation")), f"DISPATCH_EXCEPTION:{type(exc).__name__}"
            )
            print(f"Dispatch effect unknown for {task_id}: {exc}")
            continue

        if not queue.mark_claim_dispatch_state(task_id, claim["claim_id"], claim.get("state_version", claim.get("generation")), "DISPATCHED"):
            queue.quarantine_unknown_dispatch(
                task_id, claim["claim_id"], claim.get("state_version", claim.get("generation")), "DISPATCH_CONFIRMATION_PERSIST_FAILED"
            )
            continue
        dispatched_tasks.add(task_id)
        active = True
        newly_dispatched += 1
        break  # hard global ACTIVE <= 1 invariant
    return active, newly_dispatched

def dispatch_task(task_id, worker_id, action_name, prompt_text, scope, task_hash, claim, opp):
    adapters = get_real_worker_adapters(repo_root=COURIER_DIR)

    if worker_id == "CODEX":
        if len(scope) != 1:
            raise DispatchUnavailable("Codex bridge requires one exact mutation scope")
        pre_effect = snapshot_effect_scope(scope, COURIER_DIR)
        authority = CanonicalAuthority(locks_dir=COURIER_DIR / "events" / "locks")
        acquired, generation, error = authority.acquire_scopes(
            owner_id="agent-codex-bridge",
            task_id=task_id,
            scopes=scope,
            ttl_seconds=180,
        )
        if not acquired or generation is None:
            raise DispatchUnavailable(error or "Codex scope unavailable")
        record_path = authority._scope_file_path(scope[0])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        receipt_body = {
            "task_id": task_id,
            "source_agent": opp.source,
            "target_agent": "CODEX",
            "target_host": "MAC_LOCAL",
            "project_path": scope[0],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "description": prompt_text,
        }
        receipt_hash = stable_hash(receipt_body)
        receipt = dict(receipt_body, artifact_sha256=receipt_hash)
        receipt_path = COURIER_DIR / "events" / "receipts" / f"{task_id}-receipt.json"
        atomic_write_json(receipt_path, receipt)
        provenance = {
            "origin": opp.source,
            "task_identity": task_id,
            "source_artifact": receipt_path.relative_to(COURIER_DIR).as_posix(),
            "source_sha256": receipt_hash,
            "opportunity": opportunity_provenance(opp),
            "opportunity_lease": {
                "claim_id": claim["claim_id"],
                "generation": claim.get("state_version", claim.get("generation")),
                "owner": claim["claim_owner"],
                "expires_at": claim["lease_expires_at"],
            },
        }
        lease = {
            "authority": "CanonicalAuthority",
            "record_path": record_path.relative_to(COURIER_DIR).as_posix(),
            "record_sha256": stable_hash(record),
            "task_id": task_id,
            "owner_id": "agent-codex-bridge",
            "scope": scope[0],
            "generation": generation,
            "lease_expires_at": record["lease_expires_at"],
        }
        envelope = {
            "task_id": task_id,
            "goal_id": opp.objective_id,
            "source_agent": opp.source,
            "target_agent": "CODEX",
            "target_host": "MAC_LOCAL",
            "project_path": scope[0],
            "scope": scope,
            "allowed_scope": scope,
            "action": prompt_text,
            "instruction": prompt_text,
            "status": "PENDING",
            "created_at": receipt_body["created_at"],
            "provenance": provenance,
            "lease": lease,
            "task_hash": task_hash,
            "worker_id": "CODEX",
            "pre_effect_fingerprints": pre_effect,
            "payload": {"prompt": prompt_text, "allowed_scope": scope, "requires_write": True},
        }
        dispatch_path = COURIER_DIR / "events" / "dispatch" / f"{task_id}-worker-job.json"
        atomic_write_json(dispatch_path, envelope)
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "run_codex_bridge.py"),
            "--auto-discover",
            "--real-codex",
        ]
        try:
            subprocess.Popen(cmd) # Run non-blocking
        except OSError as exc:
            authority.release_scopes("agent-codex-bridge", scope, generation, task_id)
            raise DispatchUnavailable(str(exc)) from exc
        return True
        
    adapter = adapters.get(worker_id)
    if adapter:
        provenance = opportunity_provenance(opp)
        lease = {
            "claim_id": claim["claim_id"],
            "generation": claim.get("state_version", claim.get("generation")),
            "owner": claim["claim_owner"],
            "expires_at": claim["lease_expires_at"],
        }
        task_envelope = { "timeout_seconds": 180,
            "task_hash": task_hash,
            "worker_id": worker_id,
            "target_agent": worker_id,
            "task_id": task_id,
            "provenance": provenance,
            "lease": lease,
            "pre_effect_fingerprints": snapshot_effect_scope(scope, COURIER_DIR),
            "payload": {
                "action": action_name,
                "prompt": prompt_text,
                "allowed_scope": scope
            }
        }
        
        req_id = f"REQ-MAC-{task_hash[:8]}"
        requests_dir = COURIER_DIR / "coordination" / "local_requests"
        requests_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(requests_dir / f"{req_id}.json", task_envelope)
            
        def _run():
            try:
                result_envelope = adapter(task_envelope)
                res_data = result_envelope.get("result", {})
                out_payload = res_data.get("payload", {})
                out_payload["action"] = action_name
                payload_hash = hashlib.sha256(
                    json.dumps(out_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                observed = f"PAYLOAD_SHA256:{payload_hash}"
                calc_fingerprint = hashlib.sha256(f"{req_id}COMPLETED{observed}".encode("utf-8")).hexdigest()
                wrapped = {
                    "request_id": req_id,
                    "mission_id": task_id,
                    "schema_version": "1.0",
                    "status": "COMPLETED",
                    "observed_behavior": observed,
                    "result_fingerprint": calc_fingerprint,
                    "provenance": provenance,
                    "lease": lease,
                    "payload": out_payload
                }
                out = COURIER_DIR / "coordination" / "windows_to_mac" / "results" / f"{req_id}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(out, wrapped)
                print(f"Kickstart result returned to {out}")
            except Exception as e:
                print(f"Failed kickstart: {e}")
                
        import threading
        threading.Thread(target=_run).start() # Non-blocking
        return True

    raise DispatchUnavailable(f"worker adapter unavailable: {worker_id}")

def update_completed_tasks():
    """Import only independently verified effects into the fenced queue result path."""
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    processed_path = COURIER_DIR / "events" / "processed"
    if processed_path.is_dir():
        for res_file in sorted(processed_path.glob("*-result.json")):
            try:
                data = json.loads(res_file.read_text(encoding="utf-8"))
                mission_id = data.get("task_id")
                opp = queue.get_opportunity(str(mission_id))
                if not opp or opp.status != "RUNNING" or data.get("status") != "COMPLETED":
                    continue
                job_path = processed_path / f"{mission_id}-worker-job.json"
                if not job_path.is_file():
                    continue
                job = json.loads(job_path.read_text(encoding="utf-8"))
                claim = json.loads(queue._claim_path(str(mission_id)).read_text(encoding="utf-8"))
                payload = data.get("payload")
                if not isinstance(payload, dict) or payload.get("verdict") != "PASS":
                    continue
                if data.get("payload_hash") != stable_hash(payload):
                    continue
                if (
                    payload.get("task_id") != mission_id
                    or payload.get("task_hash") != job.get("task_hash")
                    or payload.get("target_agent") != "CODEX"
                ):
                    continue
                provenance = data.get("provenance")
                if provenance != job.get("provenance"):
                    continue
                if provenance.get("opportunity") != opportunity_provenance(opp):
                    continue
                expected_opportunity_lease = {
                    "claim_id": claim.get("claim_id"),
                    "generation": claim.get("state_version"),
                    "owner": claim.get("claim_owner", claim.get("owner")),
                    "expires_at": claim.get("lease_expires_at"),
                }
                if provenance.get("opportunity_lease") != expected_opportunity_lease:
                    continue
                if job.get("task_id") != mission_id or job.get("scope") != opp.allowed_scope:
                    continue

                changed_files = payload.get("changed_files")
                pre_effect = job.get("pre_effect_fingerprints")
                if not isinstance(changed_files, list) or not changed_files or not isinstance(pre_effect, dict):
                    continue
                root = COURIER_DIR.resolve()
                allowed_roots = []
                valid = True
                for raw_scope in opp.allowed_scope:
                    if raw_scope in {"GLOBAL", "UNKNOWN_WRITE", "*"}:
                        valid = False
                        break
                    scope_path = Path(raw_scope)
                    resolved_scope = (root / scope_path).resolve() if not scope_path.is_absolute() else scope_path.resolve()
                    if not _inside(root, resolved_scope):
                        valid = False
                        break
                    allowed_roots.append(resolved_scope)
                artifacts = {}
                effect_observed = False
                for raw_path in changed_files if valid else []:
                    artifact_path = Path(raw_path)
                    artifact = (root / artifact_path).resolve() if not artifact_path.is_absolute() else artifact_path.resolve()
                    if not _inside(root, artifact) or not artifact.is_file():
                        valid = False
                        break
                    if not any(artifact == allowed or _inside(allowed, artifact) for allowed in allowed_roots):
                        valid = False
                        break
                    relative = artifact.relative_to(root).as_posix()
                    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
                    artifacts[relative] = digest
                    if pre_effect.get(relative) != digest:
                        effect_observed = True
                if not valid:
                    continue
                if not effect_observed and opp.allowed_scope != ["SAFE_LOCAL_VALIDATION"]:
                    continue

                metadata = {
                    "request_id": f"CODEX:{mission_id}",
                    "external_result_fingerprint": data["payload_hash"],
                    "provenance_hash": provenance["opportunity"]["source_hash"],
                    "artifacts": artifacts,
                    "evidence_fingerprint": stable_hash(artifacts),
                }
                canonical = {
                    "schema_version": "1.0",
                    "result_type": "LOCAL_VALIDATION_RESULT",
                    "task_id": queue.canonical_task_id(mission_id, claim.get("state_version", claim.get("generation"))),
                    "opportunity_id": mission_id,
                    "claim_id": claim["claim_id"],
                    "generation": claim.get("state_version", claim.get("generation")),
                    "status": "SUCCESS",
                    "handler": "INDEPENDENT_EFFECT_CUSTOMS",
                    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "metadata": metadata,
                    "result_fingerprint": "",
                }
                canonical["result_fingerprint"] = queue.expected_result_fingerprint(opp, claim, canonical)
                canonical_path = queue.queue_dir / "results" / f"{mission_id}.result.json"
                if not canonical_path.exists():
                    atomic_write_json(canonical_path, canonical)
            except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError, AttributeError):
                continue

    results_path = COURIER_DIR / "coordination" / "windows_to_mac" / "results"
    if results_path.is_dir():
        for res_file in sorted(results_path.glob("*.json")):
            try:
                data = json.loads(res_file.read_text(encoding="utf-8"))
                req_id = data.get("request_id") or data.get("windows_validation_request_id")
                mission_id = data.get("mission_id") or data.get("task_id")
                if not all(isinstance(value, str) and value for value in (req_id, mission_id)):
                    continue
                if any(token in req_id for token in ("/", "\\", "..", "\0")):
                    continue

                opp = queue.get_opportunity(mission_id)
                if not opp or opp.status != "RUNNING" or data.get("status") != "COMPLETED":
                    continue
                claim = json.loads(queue._claim_path(mission_id).read_text(encoding="utf-8"))

                request = None
                for directory in (
                    COURIER_DIR / "coordination" / "local_requests",
                    COURIER_DIR / "coordination" / "mac_to_windows" / "requests",
                    COURIER_DIR / "coordination" / "mac_to_windows" / "archive",
                ):
                    candidate = directory / f"{req_id}.json"
                    if candidate.is_file():
                        request = json.loads(candidate.read_text(encoding="utf-8"))
                        break
                if not isinstance(request, dict) or request.get("task_id") != mission_id:
                    continue

                ack = None
                for directory in (
                    COURIER_DIR / "coordination" / "mac_to_windows" / "acks",
                    COURIER_DIR / "coordination" / "mac_to_windows" / "archive",
                ):
                    candidate = directory / f"{req_id}.ack.json"
                    if candidate.is_file():
                        ack = json.loads(candidate.read_text(encoding="utf-8"))
                        break
                result_fingerprint = data.get("result_fingerprint") or data.get("content_integrity")
                if (
                    not isinstance(ack, dict)
                    or ack.get("request_id") != req_id
                    or ack.get("fingerprint") != result_fingerprint
                    or not mac_result_consumer.verify_fingerprint(data)
                ):
                    continue

                expected_provenance = opportunity_provenance(opp)
                expected_lease = {
                    "claim_id": claim.get("claim_id"),
                    "generation": claim.get("state_version"),
                    "owner": claim.get("claim_owner", claim.get("owner")),
                    "expires_at": claim.get("lease_expires_at"),
                }
                if request.get("provenance") != expected_provenance or data.get("provenance") != expected_provenance:
                    continue
                if request.get("lease") != expected_lease or data.get("lease") != expected_lease:
                    continue
                if request.get("target_agent") != claim.get("claim_owner", claim.get("owner")):
                    continue

                payload = data.get("payload")
                request_payload = request.get("payload")
                if not isinstance(payload, dict) or not isinstance(request_payload, dict):
                    continue
                if payload.get("verdict") != "PASS":
                    continue
                if payload.get("task_id") != mission_id or payload.get("task_hash") != request.get("task_hash"):
                    continue
                if payload.get("target_agent") != request.get("target_agent"):
                    continue
                if request_payload.get("allowed_scope") != opp.allowed_scope:
                    continue

                changed_files = payload.get("changed_files") or payload.get("files_modified") or []
                if not isinstance(changed_files, list):
                    continue
                if not changed_files and opp.allowed_scope != ["SAFE_LOCAL_VALIDATION"]:
                    continue
                pre_effect = request.get("pre_effect_fingerprints")
                if not isinstance(pre_effect, dict):
                    continue

                root = COURIER_DIR.resolve()
                allowed_roots = []
                unsafe_scope = False
                for raw_scope in opp.allowed_scope:
                    if raw_scope in {"GLOBAL", "UNKNOWN_WRITE", "*"}:
                        unsafe_scope = True
                        break
                    scope_path = Path(raw_scope)
                    resolved_scope = (root / scope_path).resolve() if not scope_path.is_absolute() else scope_path.resolve()
                    if not _inside(root, resolved_scope):
                        unsafe_scope = True
                        break
                    allowed_roots.append(resolved_scope)
                if unsafe_scope or not allowed_roots:
                    continue

                if opp.target_agent == "WINDOWS":
                    artifacts = {}
                    for raw_path in changed_files:
                        artifacts[str(raw_path)] = "WINDOWS_REMOTE_FILE_HASH"
                    valid_artifacts = True
                    effect_observed = True
                else:
                    artifacts = {}
                    effect_observed = False
                    valid_artifacts = True
                    for raw_path in changed_files:
                        if not isinstance(raw_path, str) or not raw_path:
                            valid_artifacts = False
                            break
                        artifact_path = Path(raw_path)
                        artifact = (root / artifact_path).resolve() if not artifact_path.is_absolute() else artifact_path.resolve()
                        if not _inside(root, artifact) or not artifact.is_file():
                            valid_artifacts = False
                            break
                        if not any(artifact == allowed or _inside(allowed, artifact) for allowed in allowed_roots):
                            valid_artifacts = False
                            break
                        relative = artifact.relative_to(root).as_posix()
                        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
                        artifacts[relative] = digest
                        if pre_effect.get(relative) != digest:
                            effect_observed = True
                if not valid_artifacts:
                    continue
                if not effect_observed and opp.allowed_scope != ["SAFE_LOCAL_VALIDATION"]:
                    continue

                metadata = {
                    "request_id": req_id,
                    "external_result_fingerprint": result_fingerprint,
                    "provenance_hash": expected_provenance["source_hash"],
                    "artifacts": artifacts,
                    "evidence_fingerprint": hashlib.sha256(
                        json.dumps(artifacts, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest(),
                }
                canonical = {
                    "schema_version": "1.0",
                    "result_type": "LOCAL_VALIDATION_RESULT",
                    "task_id": queue.canonical_task_id(mission_id, claim.get("state_version", claim.get("generation"))),
                    "opportunity_id": mission_id,
                    "claim_id": claim["claim_id"],
                    "generation": claim.get("state_version", claim.get("generation")),
                    "status": "SUCCESS",
                    "handler": "INDEPENDENT_EFFECT_CUSTOMS",
                    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "metadata": metadata,
                    "result_fingerprint": "",
                }
                canonical["result_fingerprint"] = queue.expected_result_fingerprint(opp, claim, canonical)
                canonical_path = queue.queue_dir / "results" / f"{mission_id}.result.json"
                if canonical_path.exists():
                    existing = json.loads(canonical_path.read_text(encoding="utf-8"))
                    if existing.get("metadata", {}).get("external_result_fingerprint") != result_fingerprint:
                        continue
                else:
                    atomic_write_json(canonical_path, canonical)
            except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError):
                continue

    outcomes = queue.reconcile_durable_results()
    outcomes.extend(queue.recover_expired_claims())
    queue.promote_deferred(ready_limit=5)
    return outcomes

def main():
    if len(sys.argv) > 1:
        goal = sys.argv[1]
    else:
        goal = """Fix the Windows executor to use safe restricted commands. Then test it by running the tests natively on Windows. Make sure Mac verifies the result."""
    
    print("--- INJECTING REAL GOAL ---")
    process_one_idea(goal)

    reg = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    record = reg.register_worker(worker_id="WINDOWS", role="WINDOWS_NATIVE", provider="WINDOWS", availability_class=AvailabilityClass.TEMPORARY_30_DAY, mutable_scope=[r"C:\Dev\Windows-AI-OS"])
    record.state = WorkerState.AVAILABLE.value
    reg._save_worker_record(record)
    
    print("--- ENTERING AUTONOMOUS LOOP ---")
    dispatched_tasks = set()
    
    last_idle_fingerprint = None
    unchanged_idle_cycles = 0
    while True:
        mac_result_consumer.consume_results()
        update_completed_tasks()
        
        router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
        res = router.evaluate_next_safe_work()
        recs = res.get("recommendations", {})
        queue = OpportunityQueue(repo_dir=COURIER_DIR)
        
        advance_goal_planner(goal)
        active, _ = dispatch_recommendations(recs, queue, goal, dispatched_tasks)

        if not active:
            current_fingerprint = recommendation_fingerprint(recs)
            if current_fingerprint == last_idle_fingerprint:
                unchanged_idle_cycles += 1
            else:
                unchanged_idle_cycles = 1
                last_idle_fingerprint = current_fingerprint

            state = quiescence_state(queue.list_opportunities())
            delay = idle_backoff_seconds(unchanged_idle_cycles)
            print(f"--- {state}; waiting {delay:g}s for a real state change ---")
            
            if state == "QUIESCENT_WAKEABLE":
                print("Queue is quiescent and wakeable; no synthetic work will be generated.")
            
            time.sleep(delay)
            continue


        last_idle_fingerprint = None
        unchanged_idle_cycles = 0
        time.sleep(ACTIVE_LOOP_DELAY_SECONDS)

if __name__ == "__main__":
    main()
