# Family 13: Data Inventory, Privacy Boundaries & Pilot Operations

Status: FACTUAL INVENTORY (Non-legal factual specification)
Scope: Data classification, retention, privacy boundary, and secret isolation.

---

## 1. Data Classification Matrix

| Data Category | Specific Elements | Storage Location | Providers Receiving Data | Retention Period | Deletion Mechanism |
|---|---|---|---|---|---|
| **Goal Contracts** | Goal text, step instructions, file targets | Local `server/state/central_state.json` | Configured LLM provider (Google Gemini / Anthropic Claude / OpenAI) for task planning | Duration of pilot + 30 days audit | Atomic file removal via `courier purge` |
| **Artifact Bytes** | Generated code, test outputs, text reports | Local `server/state/artifacts/` or staging store | Stored locally on server; NEVER sent to external third parties unless explicitly configured | Session lifetime + audit archive | Directory wipe |
| **Execution Telemetry** | Task IDs, Attempt IDs, timestamps, SHA-256 hashes | Local `ops/ai/wall_ledger/ledger.jsonl` | Stored locally; may be synced to private GitHub coordination branch | Permanent ledger audit | Git history prune / branch deletion |
| **API Keys & Secrets** | LLM API keys, verifier bearer tokens | Environment variables, macOS Keychain, Windows Credential Manager | Never transmitted to LLM prompt context or logged to disk | Ephemeral (process memory only) | Immediate session termination |
| **Worker Logs** | stdout, stderr, process return codes | Local `scripts/mac_worker/logs/`, `courier_work/` | Local filesystem only | 7 days rotating | Automatic truncation |

---

## 2. Secrets & Privacy Boundary Enforcements

1. **Zero Secret Leakage in Prompts**:
   - `daemon.py` and `muse_supervisor.py` filter environment variables before passing instruction context to headless agents.
   - API keys are injected via HTTP Authorization headers or isolated keychain references.
2. **Local-First Artifact Storage**:
   - User code and file artifacts are hashed and stored locally. Only task metadata and cryptographic hashes traverse the verifier boundary.
3. **Pilot User Consent Requirements**:
   - Pilot user must explicitly authorize local folder read/write access.
   - Pilot user is informed which LLM provider model endpoint receives prompt text.
