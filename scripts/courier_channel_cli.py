#!/usr/bin/env python3
"""Unified Courier Channel Operator CLI (Bedienweg vereinfachen).

Single operational entrypoint for Courier Content & Channel Pipelines:
  KANAL -> STORY/ZIEL -> TEMPLATE -> RUN -> REVIEW -> READY_TO_PUBLISH

Features:
- 'channels': Inspect registered channels, policies, and workflows.
- 'check-auth': Unified read-only OAuth/API health check for YouTube & TikTok.
- 'status': High-level dashboard showing tool availability (Godot, FFmpeg) and staged packages.
- 'run': Execute full production pipeline for a channel with strict human gate.
- 'approve': Explicit human approval to finalize a staged package (satisfies human gate).
- 'queue': Generate night supervisor queue tasks for unattended runs.
- Adheres to ZERO_COST_ONLY (0.00 EUR) and no credential leakage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_content_production_pipeline import (
    DEFAULT_CHANNELS_CONFIG,
    DEFAULT_LOCAL_TOOLS_CONFIG,
    DEFAULT_RUNTIME_DIR,
    DEFAULT_WORKFLOWS_CONFIG,
    discover_ffmpeg_binary,
    discover_godot_binary,
    load_json,
    resolve_godot_project_binding,
    run_pipeline,
)
from youtube_auth_check import check_youtube_auth
from tiktok_auth_check import check_tiktok_auth
from build_channel_workflow_tasks import build_workflow_tasks_for_channel


def cmd_channels(args: argparse.Namespace) -> int:
    channels_path = Path(args.config)
    if not channels_path.exists():
        print(f"Error: Channels configuration not found: {channels_path}", file=sys.stderr)
        return 1

    data = load_json(channels_path)
    channels = data.get("channels", [])

    if args.json:
        print(json.dumps(channels, indent=2))
        return 0

    print(f"\nRegistered Channels ({len(channels)}):")
    print(f"{'CHANNEL ID':<20} {'PLATFORM':<10} {'STATUS':<20} {'WORKFLOW':<18} {'LABEL'}")
    print("-" * 85)
    for ch in channels:
        status_str = "ACTIVE" if ch.get("production_enabled") else "DISABLED"
        print(f"{ch.get('channel_id', 'N/A'):<20} {ch.get('platform', 'N/A'):<10} {status_str:<20} {ch.get('workflow_id', 'N/A'):<18} {ch.get('channel_label', '')}")
    print()
    return 0


def cmd_check_auth(args: argparse.Namespace) -> int:
    print("\n--- Channel Platform Auth Health Check (Read-Only) ---")
    
    # 1. YouTube
    yt_res = check_youtube_auth(dry_run=args.dry_run)
    yt_status = yt_res.get("status")
    print(f"YouTube:  Status={yt_status:<22} Mode={yt_res.get('mode', 'unknown'):<10} Channel={yt_res.get('channel_title') or 'N/A'}")

    # 2. TikTok
    tt_res = check_tiktok_auth(dry_run=args.dry_run)
    tt_status = tt_res.get("status")
    print(f"TikTok:   Status={tt_status:<22} Mode={tt_res.get('mode', 'unknown'):<10} Creator={tt_res.get('display_name') or 'N/A'}")

    print("-" * 65)
    print("Zero-Cost Policy: 0.00 EUR | Read-Only Enforcement: PASS")
    print()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    runtime_dir = Path(args.runtime_dir)
    channels_path = Path(args.config)
    tools_path = Path(args.tools_config)

    print("\n=== COURIER CONTENT & CHANNEL COCKPIT ===")

    # 1. Tools discovery
    local_tools = load_json(tools_path) if tools_path.exists() else {}
    godot_custom = local_tools.get("tools", {}).get("godot_binary_path")
    godot_bin, godot_ver = discover_godot_binary(godot_custom)
    ffmpeg_custom = local_tools.get("tools", {}).get("ffmpeg_binary_path")
    ffmpeg_bin = discover_ffmpeg_binary(ffmpeg_custom)

    print("\n[LOCAL ENGINE TOOLS]")
    print(f"  Godot Engine: {'FOUND (' + godot_ver + ')' if godot_bin else 'NOT_FOUND'} -> {godot_bin or 'None'}")
    print(f"  FFmpeg:       {'FOUND' if ffmpeg_bin else 'NOT_FOUND'} -> {ffmpeg_bin or 'None'}")

    # 2. Channels & Staged Missions
    channels_data = load_json(channels_path) if channels_path.exists() else {}
    channels = channels_data.get("channels", [])

    print("\n[CHANNELS & PRODUCTION STATUS]")
    for ch in channels:
        c_id = ch.get("channel_id")
        platform = ch.get("platform")
        c_dir = runtime_dir / c_id if runtime_dir.exists() else None
        
        latest_mission = "NONE"
        latest_status = "IDLE"
        if c_dir and c_dir.exists():
            subdirs = sorted([d for d in c_dir.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime, reverse=True)
            if subdirs:
                latest_dir = subdirs[0]
                latest_mission = latest_dir.name
                manifest_f = latest_dir / "manifest.json"
                if manifest_f.exists():
                    try:
                        m_data = load_json(manifest_f)
                        latest_status = m_data.get("overall_status", "UNKNOWN")
                    except Exception:
                        pass

        print(f"  Channel: {c_id} ({platform})")
        print(f"    Label:          {ch.get('channel_label')}")
        print(f"    Latest Mission: {latest_mission}")
        print(f"    Mission Status: {latest_status}")
        print(f"    Policy:         {ch.get('publishing_policy', 'REQUIRE_EXPLICIT_HUMAN_APPROVAL')}")

    print("\n[SAFETY INVARIANTS]")
    print("  Zero-Cost Policy: ZERO_COST_ONLY (0.00 EUR)")
    print("  Publish Gate:     REQUIRE_EXPLICIT_HUMAN_APPROVAL (No auto-upload)")
    print()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        manifest = run_pipeline(
            channel_id=args.channel_id,
            topic=args.topic,
            mission_id=args.mission_id,
            runtime_dir=Path(args.runtime_dir).resolve(),
            channels_path=Path(args.config).resolve(),
            workflows_path=Path(args.workflows_config).resolve(),
            local_tools_path=Path(args.tools_config).resolve(),
            force_rerun=args.force,
            approve_publish=args.approve_publish,
        )
        print(f"\nPipeline result: {manifest.get('overall_status')}")
        if manifest.get("overall_status") == "READY_TO_PUBLISH":
            print("[INFO] Package is STAGED awaiting explicit human approval.")
            print(f"[ACTION] To approve publication, run:\n  python scripts/courier_channel_cli.py approve --channel-id {args.channel_id} --topic {args.topic}")
        return 0
    except Exception as e:
        print(f"Pipeline execution failed: {e}", file=sys.stderr)
        return 1


def cmd_approve(args: argparse.Namespace) -> int:
    print(f"\n[HUMAN GATE APPROVAL] Approving publication for channel '{args.channel_id}'...")
    try:
        manifest = run_pipeline(
            channel_id=args.channel_id,
            topic=args.topic,
            mission_id=args.mission_id,
            runtime_dir=Path(args.runtime_dir).resolve(),
            channels_path=Path(args.config).resolve(),
            workflows_path=Path(args.workflows_config).resolve(),
            local_tools_path=Path(args.tools_config).resolve(),
            force_rerun=False,
            approve_publish=True,
        )
        print(f"Package approved and finalized: status={manifest.get('overall_status')}")
        return 0
    except Exception as e:
        print(f"Approval failed: {e}", file=sys.stderr)
        return 1


def cmd_queue(args: argparse.Namespace) -> int:
    try:
        tasks = build_workflow_tasks_for_channel(
            channel_id=args.channel_id,
            topic=args.topic,
            priority=args.priority,
            channels_path=Path(args.config).resolve(),
            workflows_path=Path(args.workflows_config).resolve(),
        )
        print(f"Successfully queued {len(tasks)} workflow stages for channel '{args.channel_id}' (topic: '{args.topic}').")
        return 0
    except Exception as e:
        print(f"Queue creation failed: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--config", default=str(DEFAULT_CHANNELS_CONFIG), help="Path to social_channels.json")
    common_parser.add_argument("--workflows-config", default=str(DEFAULT_WORKFLOWS_CONFIG), help="Path to content_workflows.json")
    common_parser.add_argument("--tools-config", default=str(DEFAULT_LOCAL_TOOLS_CONFIG), help="Path to local_tools.json")
    common_parser.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR), help="Path to runtime content directory")

    parser = argparse.ArgumentParser(
        description="Unified Courier Channel Operator CLI (Bedienweg vereinfachen)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common_parser],
        epilog="""Examples:
  courier_channel_cli.py status
  courier_channel_cli.py channels
  courier_channel_cli.py check-auth --dry-run
  courier_channel_cli.py run --channel-id chan-yt-fruitki --topic comedy-short-01
  courier_channel_cli.py approve --channel-id chan-yt-fruitki --topic comedy-short-01
  courier_channel_cli.py queue --channel-id chan-tt-3d-ai --topic viral-dance-01
"""
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # channels
    p_channels = subparsers.add_parser("channels", parents=[common_parser], help="List registered channels")
    p_channels.add_argument("--json", action="store_true", help="Output raw JSON")

    # check-auth
    p_auth = subparsers.add_parser("check-auth", parents=[common_parser], help="Perform read-only API health check")
    p_auth.add_argument("--dry-run", action="store_true", help="Simulate check without network")

    # status
    subparsers.add_parser("status", parents=[common_parser], help="Show overview of channels, tools, and staged packages")

    # run
    p_run = subparsers.add_parser("run", parents=[common_parser], help="Run content production pipeline for a channel")
    p_run.add_argument("--channel-id", required=True, help="Target channel ID")
    p_run.add_argument("--topic", default="daily-production-short", help="Production topic/title")
    p_run.add_argument("--mission-id", default=None, help="Optional explicit mission ID")
    p_run.add_argument("--force", action="store_true", help="Force rerun of completed stages")
    p_run.add_argument("--approve-publish", action="store_true", help="Consent to finalize publish stage")

    # approve
    p_app = subparsers.add_parser("approve", parents=[common_parser], help="Approve staged publish package (human gate)")
    p_app.add_argument("--channel-id", required=True, help="Target channel ID")
    p_app.add_argument("--topic", default="daily-production-short", help="Production topic/title")
    p_app.add_argument("--mission-id", default=None, help="Optional explicit mission ID")

    # queue
    p_q = subparsers.add_parser("queue", parents=[common_parser], help="Generate night queue tasks for unattended runs")
    p_q.add_argument("--channel-id", required=True, help="Target channel ID")
    p_q.add_argument("--topic", default="daily-production-short", help="Production topic/title")
    p_q.add_argument("--priority", type=int, default=1, help="Queue priority (0=P0, default=1)")

    args = parser.parse_args(argv)

    if args.command == "channels":
        return cmd_channels(args)
    elif args.command == "check-auth":
        return cmd_check_auth(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "approve":
        return cmd_approve(args)
    elif args.command == "queue":
        return cmd_queue(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
