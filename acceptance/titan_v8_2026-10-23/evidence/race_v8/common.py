import json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

T0 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
SPEC = {"adapter": "synthetic", "params": {"write": "out.txt", "content": "a"}, "effect_class": "idempotent",
        "max_attempts": 1, "lease_ttl_s": 10}


def setup(root, n_homes=4, items=("WKA",), ttl=60):
    root = Path(root)
    idir = root / "items"
    idir.mkdir(parents=True)
    for it in items:
        (idir / f"{it}.json").write_text(json.dumps({
            "id": it, "title": it, "lane": "L1", "branch": f"lane/L1-{it.lower()}", "files_scope": [f"out/{it}/"],
            "depends_on": [], "acceptance": ["x"], "provider_hints": [], "status": "READY", "lease": None}))
    ledger = root / "queue.jsonl"
    homes = []
    for i in range(n_homes):
        h = root / f"home{i}"
        h.mkdir()
        (h / "work_queue_feed.json").write_text(json.dumps({
            "items_dir": str(idir), "ledger": str(ledger), "holder": f"holder-{i}", "ttl_s": ttl,
            "specs": {it: SPEC for it in items}}))
        homes.append(h)
    return idir, ledger, homes


def assigned_lines(home):
    p = Path(home) / "coordination_ledger.jsonl"
    out = []
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("event_type") == "ASSIGNED":
            out.append(d["mission_id"])
    return out


def assigned_by_item(homes):
    by = {}
    for i, h in enumerate(homes):
        for m in assigned_lines(h):
            by.setdefault(m, []).append(i)
    return by


def clock_now(clock_path):
    return T0 + timedelta(seconds=int(Path(clock_path).read_text() or 0))
