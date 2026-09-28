#!/usr/bin/env python3
"""Persistent Courier UI/reviewer window-capacity policy.

This controls admission budget for parallel advisory/UI sessions. It never raises
mutable-writer or heavy-job concurrency; those remain independently capped at 1.
"""
from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_FILE = ROOT / "config" / "window_capacity_policy.json"
STATE_FILE = ROOT / "events" / "runtime-state" / "window_capacity_state.json"
ALLOWED_SLOTS = (8, 12, 16, 32)

DEFAULT = {
    "target_window_slots": 16,
    "paused": False,
    "controls_hidden": False,
    "max_mutable_writers": 1,
    "max_heavy_jobs_per_host": 1,
}

def _read(path: Path) -> dict[str, Any]:
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    os.replace(tmp,path)

def load_policy() -> dict[str, Any]:
    cfg={**DEFAULT, **_read(DEFAULTS_FILE), **_read(STATE_FILE)}
    slots=int(cfg.get("target_window_slots",16))
    if slots not in ALLOWED_SLOTS: slots=16
    return {
        "target_window_slots": slots,
        "paused": bool(cfg.get("paused",False)),
        "controls_hidden": bool(cfg.get("controls_hidden",False)),
        "max_mutable_writers": 1,
        "max_heavy_jobs_per_host": 1,
        "allowed_window_slots": list(ALLOWED_SLOTS),
        "updated_at": cfg.get("updated_at"),
    }

def update_policy(*,slots:int|None=None,paused:bool|None=None,controls_hidden:bool|None=None)->dict[str,Any]:
    cur=load_policy()
    if slots is not None:
        if slots not in ALLOWED_SLOTS: raise ValueError(f"slots must be one of {ALLOWED_SLOTS}")
        cur["target_window_slots"]=slots
    if paused is not None: cur["paused"]=bool(paused)
    if controls_hidden is not None: cur["controls_hidden"]=bool(controls_hidden)
    cur["max_mutable_writers"]=1
    cur["max_heavy_jobs_per_host"]=1
    cur["updated_at"]=datetime.now(timezone.utc).isoformat()
    _atomic_write(STATE_FILE,cur)
    return load_policy()

def admission(policy:dict[str,Any], active_windows:int)->dict[str,Any]:
    target=int(policy["target_window_slots"])
    paused=bool(policy["paused"])
    allow=(not paused) and active_windows < target
    return {
        "allow_new_window": allow,
        "mode": "PAUSED" if paused else ("DRAINING" if active_windows>target else "RUNNING"),
        "target_window_slots": target,
        "active_windows": active_windows,
        "remaining_slots": 0 if paused else max(0,target-active_windows),
        "max_mutable_writers": 1,
        "max_heavy_jobs_per_host": 1,
    }

def main()->int:
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest="cmd",required=True)
    sp.add_parser("show")
    s=sp.add_parser("set"); s.add_argument("--slots",type=int,choices=ALLOWED_SLOTS)
    s.add_argument("--pause",action="store_true"); s.add_argument("--resume",action="store_true")
    s.add_argument("--hide",action="store_true"); s.add_argument("--show-controls",action="store_true")
    args=ap.parse_args()
    if args.cmd=="show": print(json.dumps(load_policy(),indent=2)); return 0
    p=update_policy(slots=args.slots,
        paused=True if args.pause else (False if args.resume else None),
        controls_hidden=True if args.hide else (False if args.show_controls else None))
    print(json.dumps(p,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
