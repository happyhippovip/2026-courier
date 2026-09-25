#!/usr/bin/env python3
"""Channel Workflow Task Builder (094).

Generates schema-valid Night Supervisor tasks in events/night-queue/
for a registered channel and its bound content workflow.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent

DEFAULT_CHANNELS_CONFIG = COURIER_DIR / "config/social_channels.json"
DEFAULT_WORKFLOWS_CONFIG = COURIER_DIR / "config/content_workflows.json"
DEFAULT_QUEUE_DIR = COURIER_DIR / "events/night-queue"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:32]


def map_project_name(content_project: str, platform: str) -> str:
    if content_project in ("FruitKI", "FruitKI-YouTube") or platform == "YOUTUBE":
        return "FruitKI-YouTube"
    if content_project in ("3D-KI-Videos", "3D-KI-TikTok") or platform == "TIKTOK":
        return "3D-KI-TikTok"
    return "2026-courier"


def build_workflow_tasks_for_channel(
    channel_id: str,
    topic: str = "daily-production-short",
    priority: int = 1,
    queue_dir: Path = DEFAULT_QUEUE_DIR,
    channels_path: Path = DEFAULT_CHANNELS_CONFIG,
    workflows_path: Path = DEFAULT_WORKFLOWS_CONFIG,
) -> list[dict]:
    if not channels_path.exists():
        raise FileNotFoundError(f"Channel registry not found: {channels_path}")
    if not workflows_path.exists():
        raise FileNotFoundError(f"Workflow registry not found: {workflows_path}")

    channels_data = load_json(channels_path)
    workflows_data = load_json(workflows_path)

    # 1. Locate channel
    channel = None
    for ch in channels_data.get("channels", []):
        if ch.get("channel_id") == channel_id:
            channel = ch
            break

    if not channel:
        raise ValueError(f"Channel '{channel_id}' not found in {channels_path.name}")

    if not channel.get("production_enabled", False):
        raise ValueError(f"Channel '{channel_id}' has production_enabled=False. Workflow generation skipped.")

    # 2. Locate workflow
    workflow_id = channel.get("workflow_id")
    workflow = None
    for wf in workflows_data.get("workflows", []):
        if wf.get("workflow_id") == workflow_id:
            workflow = wf
            break

    if not workflow:
        raise ValueError(f"Workflow '{workflow_id}' for channel '{channel_id}' not found in {workflows_path.name}")

    topic_slug = slugify(topic)
    chan_slug = slugify(channel_id.replace("chan-", ""))
    project_enum = map_project_name(channel.get("content_project", ""), channel.get("platform", ""))

    production_steps = workflow.get("production_steps", [])
    created_tasks = []
    parent_task_id = None
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    queue_dir.mkdir(parents=True, exist_ok=True)

    for idx, step_name in enumerate(production_steps):
        step_slug = slugify(step_name)
        task_id = f"TASK-{chan_slug.upper()}-{topic_slug.upper()}-{step_slug.upper()}"
        task_file = queue_dir / f"{task_id}.json"

        # Deduplication check: Do not recreate task if already existing in queue
        if task_file.exists():
            existing = load_json(task_file)
            existing_status = existing.get("status")
            if existing_status in ("QUEUED", "RUNNING", "COMPLETED", "HUMAN_GATE"):
                print(f"DEDUPED: Task {task_id} already exists with status '{existing_status}'. Skipping creation.")
                parent_task_id = task_id
                continue

        # Formulate clear instruction for the agent
        instruction = f"Execute workflow stage [{step_name}] for channel [{channel['channel_label']}] on platform [{channel['platform']}]. Topic: {topic}."

        task_record = {
            "schema_version": "2.0",
            "task_id": task_id,
            "priority": priority,
            "instruction": instruction,
            "project": project_enum,
            "status": "QUEUED",
            "created_at": now_iso,
            "attempt_count": 0,
            "max_attempts": 2,
            "parent_task_id": parent_task_id,
            "requires_human": False,
            "last_result_id": None,
            "cost_policy": "ZERO_COST_ONLY",
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
            "target_agent": "ANTIGRAVITY",
        }

        save_json(task_file, task_record)
        created_tasks.append(task_record)
        parent_task_id = task_id

    return created_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build night queue tasks for a registered channel workflow")
    parser.add_argument("--channel-id", required=True, help="Registered channel ID")
    parser.add_argument("--topic", default="daily-production-short", help="Production topic / title")
    parser.add_argument("--priority", type=int, default=1, help="Task priority (0=P0 highest, default=1)")
    parser.add_argument("--queue-dir", default=str(DEFAULT_QUEUE_DIR), help="Path to events/night-queue")
    parser.add_argument("--config", default=str(DEFAULT_CHANNELS_CONFIG), help="Path to social_channels.json")
    parser.add_argument("--workflows-config", default=str(DEFAULT_WORKFLOWS_CONFIG), help="Path to content_workflows.json")
    args = parser.parse_args()

    tasks = build_workflow_tasks_for_channel(
        channel_id=args.channel_id,
        topic=args.topic,
        priority=args.priority,
        queue_dir=Path(args.queue_dir).resolve(),
        channels_path=Path(args.config).resolve(),
        workflows_path=Path(args.workflows_config).resolve(),
    )
    print(f"Generated {len(tasks)} workflow tasks for channel '{args.channel_id}':")
    for t in tasks:
        print(f"  - {t['task_id']}: {t['instruction']}")


if __name__ == "__main__":
    main()
