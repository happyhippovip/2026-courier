"""Logical-slot supervisor.  It never launches a provider unless explicitly enabled."""
import argparse
import copy
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

from .slot_state import (
    SLOT_STATES,
    SlotLock,
    StateCorruptionError,
    atomic_write,
    default_slot,
    process_matches,
    read_json,
)


class MuseWallSupervisor:
    def __init__(self, root, config=None):
        self.root = Path(root)
        self.config = config or read_json(Path(__file__).with_name("config.json"))
        self.runtime = self.root / "runtime"
        self.slots_root = self.runtime / "slots"

    @property
    def desired_slots(self):
        return int(self.config["desired_slots"])

    def slot_id(self, index):
        return f"MUSE-{index:02d}"

    def slot_dir(self, slot_id):
        return self.slots_root / slot_id

    def state_path(self, slot_id):
        return self.slot_dir(slot_id) / "state.json"

    def initialize(self):
        for index in range(1, self.desired_slots + 1):
            slot_id = self.slot_id(index)
            directory = self.slot_dir(slot_id)
            (directory / "logs").mkdir(parents=True, exist_ok=True)
            workdir = directory / "workdir"
            workdir.mkdir(exist_ok=True)
            if not self.state_path(slot_id).exists():
                atomic_write(self.state_path(slot_id), default_slot(slot_id, workdir))

    def load_slot(self, slot_id):
        value = read_json(self.state_path(slot_id))
        if value.get("slot_id") != slot_id or value.get("state") not in SLOT_STATES:
            raise StateCorruptionError(f"invalid slot state: {slot_id}")
        return value

    def save_slot(self, slot):
        slot["updated_at"] = time.time()
        atomic_write(self.state_path(slot["slot_id"]), slot)

    def reconcile_slot(self, slot_id):
        with SlotLock(self.slot_dir(slot_id) / "slot.lock"):
            slot = self.load_slot(slot_id)
            if slot.get("process") and not process_matches(slot["process"]):
                slot["process"] = None
                if slot["state"] not in {"DONE", "BLOCKED"}:
                    slot["state"] = "CRASHED"
                self.save_slot(slot)
            return slot

    def start_slot(self, slot_id, command=None):
        """Start only a supplied test command; provider starts are default-denied."""
        with SlotLock(self.slot_dir(slot_id) / "slot.lock"):
            slot = self.load_slot(slot_id)
            if slot.get("process") and process_matches(slot["process"]):
                return {"started": False, "reason": "already_running", "slot": slot}
            if not self.config.get("provider_launch_enabled", False):
                return {"started": False, "reason": "provider_launch_disabled", "slot": slot}
            if command is None:
                return {"started": False, "reason": "no_launch_command", "slot": slot}
            process = subprocess.Popen(command, cwd=slot["workdir"], stdin=subprocess.DEVNULL)
            slot["process"] = {
                "pid": process.pid,
                "create_time": psutil.Process(process.pid).create_time(),
                "owner_token": slot["owner_token"],
            }
            slot["state"] = "IDLE"
            self.save_slot(slot)
            return {"started": True, "reason": "started", "slot": slot}

    def stop_slot(self, slot_id):
        with SlotLock(self.slot_dir(slot_id) / "slot.lock"):
            slot = self.load_slot(slot_id)
            process = slot.get("process")
            if not process or not process_matches(process):
                if process:
                    slot["process"] = None
                    slot["state"] = "CRASHED"
                    self.save_slot(slot)
                return {"stopped": False, "reason": "no_matching_owned_process", "slot": slot}
            candidate = psutil.Process(process["pid"])
            candidate.terminate()
            try:
                candidate.wait(timeout=5)
            except psutil.TimeoutExpired:
                candidate.kill()
                candidate.wait(timeout=5)
            slot["process"] = None
            slot["state"] = "READY"
            self.save_slot(slot)
            return {"stopped": True, "reason": "stopped", "slot": slot}

    def admitted_count(self, requested_level):
        if requested_level not in self.config["staged_levels"]:
            raise ValueError("requested level is not an approved stage")
        return min(requested_level, int(self.config["active_limit"]), self.desired_slots)

    def status(self):
        slots = []
        for index in range(1, self.desired_slots + 1):
            slot_id = self.slot_id(index)
            try:
                slots.append(self.load_slot(slot_id))
            except StateCorruptionError:
                slots.append({"slot_id": slot_id, "state": "BLOCKED", "process": None})
        return {
            "desired_slots": self.desired_slots,
            "defined_slots": len(slots),
            "provider_launch_enabled": bool(self.config["provider_launch_enabled"]),
            "active_limit": int(self.config["active_limit"]),
            "states": {state: sum(item["state"] == state for item in slots) for state in sorted(SLOT_STATES)},
        }


def repo_root():
    return Path(__file__).resolve().parent.parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("init", "status", "admit", "stop"))
    # Canonical runtime lives at <repo>/runtime/slots; the wall directory
    # itself is NOT a second truth store (SECOND_TRUTH_STORE=NO).
    parser.add_argument("--root", default=str(repo_root()))
    parser.add_argument("--level", type=int)
    parser.add_argument("--slot")
    arguments = parser.parse_args()
    supervisor = MuseWallSupervisor(arguments.root)
    supervisor.initialize()
    if arguments.command == "init":
        print(supervisor.status())
    elif arguments.command == "status":
        print(supervisor.status())
    elif arguments.command == "admit":
        print({"admitted": supervisor.admitted_count(arguments.level)})
    else:
        print(supervisor.stop_slot(arguments.slot))


if __name__ == "__main__":
    main()
