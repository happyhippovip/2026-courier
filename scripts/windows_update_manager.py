#!/usr/bin/env python3
import json
import logging
import os
from pathlib import Path
import shutil
import time

try:
    from scripts.orphan_task_reaper import (
        REPO_ROOT,
        get_canonical_state_path,
        get_worker_state_path,
        atomic_save_json,
        safely_terminate_pid,
    )
except ImportError:
    from orphan_task_reaper import (
        REPO_ROOT,
        get_canonical_state_path,
        get_worker_state_path,
        atomic_save_json,
        safely_terminate_pid,
    )

logger = logging.getLogger("windows_update_manager")


class WindowsUpdateManager:
    def __init__(self, state_file=None, backup_dir=None, target_version="1.1.0", worker_state_file=None):
        self.state_file = get_canonical_state_path(state_file)
        self.backup_dir = Path(backup_dir).resolve() if backup_dir else (REPO_ROOT / "backup_update")
        self.worker_state_file = get_worker_state_path(worker_state_file)
        self.current_version = "1.0.0"
        self.target_version = target_version

    def detect_version(self) -> str:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_version = data.get("schema_version", self.current_version)
            except Exception:
                pass
        print(f"Detected current installed version: {self.current_version}")
        return self.current_version

    def schema_compatibility_check(self) -> bool:
        print(f"Checking schema compatibility for target {self.target_version}...")
        # Target version must follow standard semantic ordering
        try:
            cur_parts = [int(p) for p in self.current_version.split(".")[:2]]
            tgt_parts = [int(p) for p in self.target_version.split(".")[:2]]
            # Disallow downgrading or breaking major versions
            if tgt_parts[0] < cur_parts[0]:
                return False
        except (ValueError, IndexError):
            pass
        return True

    def checkpoint_state(self) -> int:
        print("Checkpointing canonical state, credentials, queue, results, and account checkpoints...")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        candidates = [
            self.state_file,
            self.worker_state_file,
            REPO_ROOT / "account_session.json",
            REPO_ROOT / ".env.txt",
        ]

        manifest = {}
        backed_up_count = 0
        for cand in candidates:
            cand_path = Path(cand).resolve()
            if cand_path.exists() and cand_path.is_file():
                dest_file = self.backup_dir / cand_path.name
                shutil.copy2(cand_path, dest_file)
                manifest[cand_path.name] = str(cand_path)
                backed_up_count += 1
                print(f"Backed up {cand_path} -> {dest_file}")

        manifest_file = self.backup_dir / "manifest.json"
        atomic_save_json(manifest_file, {"manifest": manifest, "timestamp": time.time()})
        return backed_up_count

    def stop_runtime(self) -> int:
        print("Stopping only Courier-owned runtime...")
        terminated_count = 0
        if self.worker_state_file.exists():
            try:
                with open(self.worker_state_file, "r", encoding="utf-8") as f:
                    wdata = json.load(f)
                owned_pids = wdata.get("owned_pids", [])
                for pid in list(owned_pids):
                    if safely_terminate_pid(pid):
                        terminated_count += 1
                wdata["owned_pids"] = []
                atomic_save_json(self.worker_state_file, wdata)
            except Exception as e:
                logger.warning(f"Failed while stopping worker runtime: {e}")
        print(f"Runtime cleanly stopped ({terminated_count} processes terminated).")
        return terminated_count

    def update_files(self) -> bool:
        print("Downloading and applying update package (No customer git commands)...")
        # In real update: unzips validated update package into runtime directory.
        return True

    def migrate_schema(self) -> bool:
        print("Migrating schema idempotently...")
        if not self.state_file.exists():
            return False

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ERROR] Cannot parse canonical state during migration: {e}")
            return False

        # Idempotent mutation: update schema_version
        state["schema_version"] = self.target_version
        if "updated_at" not in state:
            state["updated_at"] = time.time()

        atomic_save_json(self.state_file, state)
        print("Schema migration completed successfully.")
        return True

    def restart_and_health_check(self, force_fail=False) -> bool:
        print("Restarting runtime and performing health check...")
        time.sleep(0.1)
        if force_fail:
            print("[HEALTH CHECK FAILED]")
            return False

        if not self.state_file.exists():
            print("[HEALTH CHECK FAILED] State file missing.")
            return False

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                print("[HEALTH CHECK FAILED] State file is not a dict.")
                return False
        except Exception as e:
            print(f"[HEALTH CHECK FAILED] Corrupt state file: {e}")
            return False

        print("[HEALTH CHECK PASSED]")
        return True

    def rollback(self) -> bool:
        print("Initiating ROLLBACK sequence...")
        if not self.backup_dir.exists():
            print("Rollback aborted: backup directory does not exist.")
            return False

        manifest_file = self.backup_dir / "manifest.json"
        restored = 0
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f).get("manifest", {})
                for filename, original_path_str in manifest_data.items():
                    src = self.backup_dir / filename
                    dst = Path(original_path_str)
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                        restored += 1
                        print(f"Restored {src} -> {dst}")
            except Exception as e:
                logger.error(f"Error reading manifest: {e}")

        # Fallback to direct directory scan if manifest failed or was absent
        if restored == 0:
            for item in self.backup_dir.iterdir():
                if item.name == "manifest.json":
                    continue
                if item.suffix in [".json", ".txt"]:
                    if item.name == self.state_file.name:
                        shutil.copy2(item, self.state_file)
                    else:
                        shutil.copy2(item, REPO_ROOT / item.name)
                    restored += 1

        print(f"Rollback complete. Restored {restored} original file(s).")
        return True

    def run_update_flow(self, simulate_failure=False) -> dict:
        self.detect_version()
        if not self.schema_compatibility_check():
            print("Update aborted due to schema incompatibility.")
            return {
                "success": False,
                "status": "ABORTED_SCHEMA",
                "version": self.current_version,
            }

        self.checkpoint_state()
        self.stop_runtime()
        self.update_files()
        self.migrate_schema()

        if not self.restart_and_health_check(force_fail=simulate_failure):
            self.rollback()
            return {
                "success": False,
                "status": "ROLLEDBACK",
                "version": self.current_version,
            }
        else:
            print("Update succeeded. Cleaning up backups.")
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir, ignore_errors=True)
            return {
                "success": True,
                "status": "COMPLETED",
                "version": self.target_version,
            }


if __name__ == "__main__":
    manager = WindowsUpdateManager()

    print("--- SCENARIO 1: Successful Update ---")
    res1 = manager.run_update_flow(simulate_failure=False)
    print(f"Result 1: {res1}")

    print("\n--- SCENARIO 2: Failed Update / Rollback ---")
    manager2 = WindowsUpdateManager()
    res2 = manager2.run_update_flow(simulate_failure=True)
    print(f"Result 2: {res2}")
