#!/usr/bin/env python3
"""Channel Onboarding CLI & Engine for Social Media Channels (094).

Registers new YouTube and TikTok channels into the persistent channel registry
with automatic workflow binding and zero credential storage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent

DEFAULT_CHANNELS_CONFIG = COURIER_DIR / "config/social_channels.json"
DEFAULT_WORKFLOWS_CONFIG = COURIER_DIR / "config/content_workflows.json"
DEFAULT_CHANNEL_SCHEMA = COURIER_DIR / "schemas/social_channel_registry.schema.json"

SECRET_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|api[_-]?key|bearer|oauth|private[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
]


def fail(message: str) -> None:
    raise SystemExit(f"CHANNEL_REGISTRATION_ERROR: {message}")


def check_secrets(text: str) -> None:
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            fail("Sensitive credential or secret pattern detected in channel registration input! Credentials must NEVER be stored in the channel registry.")


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:24]


def register_channel(
    platform: str,
    channel_label: str,
    content_project: str = "NEW_CHANNEL_PENDING",
    workflow_id: str | None = None,
    config_path: Path = DEFAULT_CHANNELS_CONFIG,
    workflows_path: Path = DEFAULT_WORKFLOWS_CONFIG,
    automation_status: str = "NEW_CHANNEL_PENDING",
    production_enabled: bool = True,
) -> dict:
    # 1. Secret Guard on all inputs
    for val in [platform, channel_label, content_project, workflow_id or "", automation_status or ""]:
        check_secrets(str(val))

    platform_upper = platform.upper().strip()
    if platform_upper not in ("YOUTUBE", "TIKTOK"):
        fail(f"Unsupported platform: '{platform}'. Allowed platforms are YOUTUBE, TIKTOK.")

    if not channel_label or len(channel_label.strip()) < 2:
        fail("channel_label must have at least 2 characters.")

    # 2. Workflow resolution & validation
    if not workflow_id:
        if platform_upper == "YOUTUBE":
            workflow_id = "fruitki-youtube" if content_project == "FruitKI" else "fruitki-youtube"
        elif platform_upper == "TIKTOK":
            workflow_id = "3d-ai-tiktok" if content_project in ("3D-KI-Videos", "3D-KI-TikTok") else "3d-ai-tiktok"
        else:
            workflow_id = "generic-staging-workflow"

    # Validate workflow exists in workflows config if file exists
    if workflows_path.exists():
        try:
            wf_data = json.loads(workflows_path.read_text(encoding="utf-8"))
            known_wfs = {w["workflow_id"] for w in wf_data.get("workflows", [])}
            if workflow_id not in known_wfs and workflow_id != "generic-staging-workflow":
                fail(f"Workflow '{workflow_id}' is not defined in {workflows_path.name}.")
        except Exception as e:
            if isinstance(e, SystemExit):
                raise
            pass

    # 3. Generate channel ID
    prefix = "yt" if platform_upper == "YOUTUBE" else "tt"
    slug = slugify(channel_label)
    channel_id = f"chan-{prefix}-{slug}"

    # 4. Load or initialize registry
    if config_path.exists():
        registry_data = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        registry_data = {
            "schema_version": "2.0",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "channels": []
        }

    # Check for duplicate channel_id
    for existing in registry_data.get("channels", []):
        if existing.get("channel_id") == channel_id:
            fail(f"Channel with ID '{channel_id}' is already registered in {config_path.name}!")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cred_ref = f"MACOS_KEYCHAIN_{platform_upper}_{slug.replace('-', '_').upper()}_PILOT"

    new_channel = {
        "channel_id": channel_id,
        "platform": platform_upper,
        "channel_label": channel_label.strip(),
        "content_project": content_project.strip(),
        "workflow_id": workflow_id,
        "automation_status": automation_status,
        "production_enabled": production_enabled,
        "publishing_policy": "REQUIRE_EXPLICIT_HUMAN_APPROVAL",
        "credential_reference_metadata": cred_ref,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    registry_data["channels"].append(new_channel)
    registry_data["updated_at"] = now_iso

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(registry_data, indent=2) + "\n", encoding="utf-8")

    return new_channel


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a social media channel (YouTube / TikTok)")
    parser.add_argument("--platform", required=True, help="Platform: YOUTUBE or TIKTOK")
    parser.add_argument("--label", required=True, help="Channel label/name")
    parser.add_argument("--project", default="NEW_CHANNEL_PENDING", help="Content project name")
    parser.add_argument("--workflow", default=None, help="Workflow ID (optional, auto-derived if omitted)")
    parser.add_argument("--config", default=str(DEFAULT_CHANNELS_CONFIG), help="Path to social_channels.json")
    parser.add_argument("--workflows-config", default=str(DEFAULT_WORKFLOWS_CONFIG), help="Path to content_workflows.json")
    args = parser.parse_args()

    channel = register_channel(
        platform=args.platform,
        channel_label=args.label,
        content_project=args.project,
        workflow_id=args.workflow,
        config_path=Path(args.config).resolve(),
        workflows_path=Path(args.workflows_config).resolve(),
    )
    print(json.dumps(channel, indent=2))


if __name__ == "__main__":
    main()
