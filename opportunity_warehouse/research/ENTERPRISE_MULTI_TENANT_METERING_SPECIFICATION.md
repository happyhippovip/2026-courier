# Symphony Enterprise Multi-Tenant Billing & Metering Specification

**Document Version**: 1.0.0-ENTERPRISE  
**Standard**: FinOps Open Cost Standard, Stripe Usage Billing, AWS Marketplace Metering  
**Target Audience**: Enterprise FinOps Leads, Cloud Cost Optimization Directors, Engineering Managers  

---

## 1. Metering Philosophy & Cost Attribution

In modern software engineering organizations running dozens of autonomous AI coding agents, unmonitored LLM token consumption is a leading source of cloud cost overruns.

`@symphony/agent-context-trimmer` introduces **Local Zero-Trust Usage Metering**:
1. **Cryptographically Sealed Usage Records**: Every execution logs token consumption and trimming savings into an append-only JSON Lines ledger signed with an internal HMAC-SHA256 signature.
2. **Multi-Dimensional Cost Centers**: Attribution is tagged by:
   - `organization_id` (e.g., "ACME-CORP")
   - `department_id` (e.g., "FINTECH-CORE")
   - `repository_id` (e.g., "payments-service")
   - `developer_seat_id` (e.g., "dev-alice-981")
   - `model_target` (e.g., "claude-3-5-sonnet")

---

## 2. Ledger Record Schema (`metering_event.jsonl`)

```json
{
  "record_id": "MTR-2026-09-11-98124",
  "timestamp": "2026-09-11T09:34:00Z",
  "tenant": {
    "org_id": "ORG-ENTERPRISE-01",
    "team_id": "AI-INFRA",
    "user_id": "eng_lead_42"
  },
  "metrics": {
    "raw_tokens": 128450,
    "trimmed_tokens": 78200,
    "tokens_saved": 50250,
    "efficiency_ratio": 0.391,
    "model": "claude-3-5-sonnet"
  },
  "financials": {
    "gross_cost_usd": 0.3853,
    "net_cost_usd": 0.2346,
    "dollar_savings_usd": 0.1507
  },
  "signature": "e7b91a...hmac_sha256..."
}
```

---

## 3. FinOps & Chargeback Integration Workflow

1. **Daily Aggregation Daemon**: A local cron job aggregates `metering_event.jsonl` into monthly team chargeback reports.
2. **Internal API Ingestion**: Enterprise platforms can ingest the sealed records via REST webhook or S3/GCS bucket sync.
3. **Automated ROI Audit**: Platform teams verify that `agent-context-trimmer` pays for itself (typically 5–10x ROI over monthly license cost).
