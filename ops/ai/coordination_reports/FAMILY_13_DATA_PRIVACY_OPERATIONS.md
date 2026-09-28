# Family 13: Data Inventory & Privacy Operations

**Status**: FACTUAL INVENTORY AUDIT  
**Scope**: First Friendly Pilot Cohort Data Flow

---

## 1. Factual Data Inventory

| Data Category | Specific Elements | Storage Location | Accessible Providers | Retention Policy |
|---|---|---|---|---|
| **Goal Input** | Natural language instructions, repository paths | `state/central_state.json` (Local) | Model API (OpenAI / Google / Anthropic) when prompted | Durably retained until user deletes goal or workspace |
| **Artifact Blobs** | Code files, test outputs, text reports | `server/state/artifacts/blobs/` | Local server store only; NOT forwarded to model APIs unless explicitly quoted | Retained locally for verification history |
| **Ledger Telemetry** | Task IDs, Attempt IDs, timestamps, SHA-256 hashes | `ops/ai/wall_ledger/ledger.jsonl` | Local filesystem | Append-only audit trail; purgeable upon goal archive |
| **Credentials & Secrets** | `COURIER_API_KEY`, `COURIER_VERIFIER_API_KEY`, Provider keys | Environment variables only; NEVER stored in state JSON or ledger | Not persisted to disk; transient memory only | Lifespan of process execution |

---

## 2. Pilot Privacy & Consent Protocol
1. **Local-First Boundary**: The Courier server runs locally on `127.0.0.1`. No external cloud relay or centralized tracking database is active.
2. **Provider Transparency**: The pilot user is informed of which LLM provider API receives prompts.
3. **Data Deletion Protocol**: A single CLI command `courier clean --goal <id>` removes state records and associated artifact blobs from disk.
4. *Note*: Formal legal terms / GDPR compliance documentation requires independent professional legal review prior to commercial release.
