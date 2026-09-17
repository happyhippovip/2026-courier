#!/bin/bash
# Fail-closed IDE task registry audit.
#
# Process age and a command-name pattern are not proof that Courier owns a
# process.  Cleanup is therefore permitted only through the existing registry,
# which binds an exact PID to its observed process identity and owner.  This
# watchdog only removes dead/stale registry entries; an explicit owner-scoped
# cleanup command is required to terminate a registered live process.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

echo "$(date): Auditing Courier-owned IDE task registry..."
python3 "$SCRIPT_DIR/agent_session_manager.py" audit
