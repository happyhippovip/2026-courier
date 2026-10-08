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

## OAuth 2.1 (for hosted connectors that require it)

`--oauth --public-url https://<host> --oauth-store <file>` turns on a minimal
authorization server (standard library only):

- Metadata: `/.well-known/oauth-authorization-server` (RFC 8414) and
  `/.well-known/oauth-protected-resource` (RFC 9728). 401 responses carry
  `WWW-Authenticate: Bearer resource_metadata="…"`.
- Public clients only (`token_endpoint_auth_method: none`), PKCE `S256`
  required, scope `courier.read`. Fixed client id `courier-grok`; dynamic
  client registration at `POST /register` (RFC 7591).
- `GET /authorize` shows a consent page; the owner approves by typing the
  server token (`COURIER_MCP_TOKEN`) as approval password. Wrong passwords:
  5 per 10 minutes, then 429.
- Codes: in memory, single use, 120 s, bound to client, redirect URI and
  challenge. Access tokens 1 h, refresh tokens 30 d (rotated on use). Only
  SHA-256 hashes are stored, in the store file (mode 0600).
- `redirect_uri` must be `https` on `grok.com`, `x.ai` or a subdomain.
  Rejected hosts are logged (host only) so the list can be widened.
- The static bearer and the optional path token keep working.
