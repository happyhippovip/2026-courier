# Courier MCP server (read-only)

`python -m courier_mcp` serves a read-only Model Context Protocol endpoint over
Streamable HTTP at `POST /mcp` (JSON responses, no SSE stream, no sessions).

Implementation: standard library only (`http.server`). The official MCP Python
SDK is not in the pinned dependency set, and pins change only through L1.

## Tools

| Tool | Returns |
| --- | --- |
| `courier_about` | Public product text ("Ideas travel further.") |
| `courier_status` | One card: RUNNING, IDLE, BLOCKED, ATTENTION, NOT_CONFIGURED |
| `list_missions` | Missions with status, newest first (`status`, `limit` ≤ 100) |
| `get_mission` | One mission by `mission_id` |
| `list_receipts` | Missions with an accepted result (`limit` ≤ 100) |
| `receipts_summary` | Counts per status, receipt count, latest update |

No write tools, no commands, no arbitrary paths. The only file read is
`<state_dir>/ledger_bridge_state.json` (1 MiB cap, no symlinks). Unknown
status/reason values, bad JSON, duplicate task ids or bad timestamps make the
state `UNREADABLE` and return no missions.

## Running

```bash
# real state: token (>= 32 chars) and state dir are required
export COURIER_MCP_TOKEN=...            # never commit or log it
python -m courier_mcp --state-dir /path/to/courier-home --port 8765

# demo: bundled synthetic data only; without a token only on loopback
python -m courier_mcp --demo
```

Default bind is `127.0.0.1`. To reach it from a hosted client (for example a
custom connector in the Grok app), put an HTTPS tunnel or reverse proxy in
front of the loopback port.

Auth is `Authorization: Bearer <token>`. `--allow-path-token` additionally
accepts `POST /mcp/<token>` for clients that cannot send a header; the token
is then part of the URL, so use it with demo data or a short-lived token only.
Browser `Origin` headers are rejected unless allow-listed (`--allow-origin`).

Follow-up: switch the reader to `courier_core.receipt_read_model` once
`lane/L2-receipt-read-model` is merged (same file, same fail-closed rules).
