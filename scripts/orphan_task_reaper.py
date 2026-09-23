#!/usr/bin/env python3
import json
import os
from pathlib import Path
import psutil
import time

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_canonical_state_path(state_file: str = None) -> Path:
    if state_file:
        return Path(state_file).resolve()
    env_file = os.environ.get("COURIER_STATE_FILE")
    if env_file:
        return Path(env_file).resolve()
    default_server = REPO_ROOT / "server" / "state" / "central_state.json"
    if default_server.exists():
        return default_server
    root_candidate = REPO_ROOT / "central_state.json"
    if root_candidate.exists():
        return root_candidate
    return default_server


def get_worker_state_path(worker_state_file: str = None) -> Path:
    if worker_state_file:
        return Path(worker_state_file).resolve()
    env_file = os.environ.get("COURIER_WORKER_STATE_FILE")
    if env_file:
        return Path(env_file).resolve()
    local_candidate = Path("worker_state.json").resolve()
    if local_candidate.exists():
        return local_candidate
    mac_worker_state = REPO_ROOT / "scripts" / "mac_worker" / "state" / "worker_state.json"
    if mac_worker_state.exists():
        return mac_worker_state
    windows_worker_state = REPO_ROOT / "scripts" / "windows_worker" / "state" / "worker_state.json"
    if windows_worker_state.exists():
        return windows_worker_state
    return local_candidate


def atomic_save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def safely_terminate_pid(pid: int) -> bool:
    """Terminate a process and its children safely, avoiding system, self, or parent PIDs."""
    if not isinstance(pid, int) or pid <= 1:
        return False
    if pid == os.getpid() or pid == os.getppid():
        return False
    try:
        p = psutil.Process(pid)
        for child in p.children(recursive=True):
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        p.terminate()
        return True
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except psutil.AccessDenied:
        return False


def check_task_health(state_file: str = None, worker_state_file: str = None) -> dict:
    s_path = get_canonical_state_path(state_file)
    w_path = get_worker_state_path(worker_state_file)

    # 1. Load canonical tasks
    valid_task_ids = set()
    if s_path.exists():
        try:
            with open(s_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                for goal_id, goal_data in state.get("goals", {}).items():
                    if isinstance(goal_data, dict):
                        for t in goal_data.get("workflow_plan", []):
                            if isinstance(t, dict) and t.get("status") in ["RUNNING", "WAITING_PROVIDER", "WAITING"]:
                                tid = t.get("task_id")
                                if tid:
                                    valid_task_ids.add(tid)
        except Exception as e:
            print(f"Warning: Failed to load canonical state {s_path}: {e}")

    # 2. Check UI handles sourced from worker state (not hardcoded)
    ui_handles: list = []
    if w_path.exists():
        try:
            with open(w_path, "r", encoding="utf-8") as f:
                _wstate_peek = json.load(f)
            ui_handles = list(_wstate_peek.get("ui_handles", []))
            active = _wstate_peek.get("active_ui_handle")
            if active and active not in ui_handles:
                ui_handles.append(active)
        except Exception:
            pass  # Will be handled again when w_path is loaded below

    stale_ui_handles = []
    for handle in ui_handles:
        if handle not in valid_task_ids:
            print(f"[STALE_UI_HANDLE] UI handle {handle} found but no canonical backend task. Removing UI handle only.")
            stale_ui_handles.append(handle)

    # 3. Check orphaned processes
    cleaned = False
    orphaned_task_id = None
    terminated_pids = []

    if w_path.exists():
        try:
            with open(w_path, "r", encoding="utf-8") as f:
                wstate = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load worker state {w_path}: {e}")
            return {
                "cleaned": False,
                "stale_ui_handles": stale_ui_handles,
                "error": f"corrupt worker state: {e}",
            }

        current_task = wstate.get("current_task")
        owned_pids = wstate.get("owned_pids", [])
        last_heartbeat = wstate.get("last_heartbeat", 0)

        if current_task and isinstance(current_task, dict):
            task_id = current_task.get("task_id")
            heartbeat_stale = (time.time() - last_heartbeat) > 300 if last_heartbeat else False
            canonical_missing = task_id not in valid_task_ids

            if heartbeat_stale or canonical_missing:
                print(f"[ORPHANED_EXECUTION] Task {task_id} is stale or invalid.")
                orphaned_task_id = task_id
                for pid in list(owned_pids):
                    if safely_terminate_pid(pid):
                        terminated_pids.append(pid)

                # Release ownership and mark cleanup
                wstate["current_task"] = None
                wstate["owned_pids"] = []
                wstate["cleanup_evidence"] = f"Cleaned orphaned task {task_id} at {time.time()}"

                atomic_save_json(w_path, wstate)
                cleaned = True
            else:
                print(f"[VALID_RUNNING_EXECUTION] Task {task_id} is healthy and running. Do not terminate.")

    return {
        "cleaned": cleaned,
        "orphaned_task_id": orphaned_task_id,
        "stale_ui_handles": stale_ui_handles,
        "terminated_pids": terminated_pids,
    }


if __name__ == "__main__":
    check_task_health()
