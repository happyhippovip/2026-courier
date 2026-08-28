#!/bin/sh
set -eu

base_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
created_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
event_id="COURIER_NOOP_055-$(date -u +"%Y%m%dT%H%M%SZ")"
correlation_id="$event_id"
dedupe_key=$(printf '%s' "github_work|COURIER_NOOP|$event_id" | shasum -a 256 | awk '{print $1}')

payload=$(printf '{\n  "event_id": "%s",\n  "correlation_id": "%s",\n  "created_at": "%s",\n  "source": "github_work",\n  "event_type": "COURIER_NOOP",\n  "task_id": "COURIER_NOOP_055",\n  "status": "PENDING",\n  "payload": { "message": "local courier dry-run" },\n  "dedupe_key": "%s",\n  "reply_channel": "control_thread"\n}\n' "$event_id" "$correlation_id" "$created_at" "$dedupe_key")

if [ "${1:-}" = "--write" ]; then
  target="$base_dir/events/incoming/$event_id.json"
  (umask 077; printf '%s' "$payload" > "$target")
  printf '%s\n' "$target"
else
  printf '%s' "$payload"
fi
