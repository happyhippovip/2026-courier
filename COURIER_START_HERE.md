# Courier Bootstrap

To start or resume Courier execution autonomously as a fresh worker without requiring previous chat history or context pasting:

1. Run the canonical continuation entrypoint:
   ```bash
   python3 scripts/courier_continue.py
   ```

## Architecture Invariants

* **Motor** = sole runtime scheduler and authority.
* **Ledger** = durable coordination, evidence, and zero-chat handoff mechanism. Never a second scheduler.
* **Canonical Ledger Location**: `agent_handoff_ledger.json`

Do not duplicate runtime state or reconstruct chat memory. The entrypoint provides the Minimal Task Packet required.
