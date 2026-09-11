# Enterprise Resilient Agent Telemetry & OpenTelemetry OTLP/gRPC Ingestion Pipeline

## Executive Summary
In complex autonomous multi-agent environments, debugging non-deterministic hallucinations, tracking distributed token budgets, and maintaining audit compliance across asynchronous task chains requires standardized observability.
This architectural specification details the enterprise implementation of OpenTelemetry (OTel) GenAI semantic conventions, distributed context propagation (W3C TraceContext), and resilient OTLP/gRPC batch exporting with local ring-buffer fault tolerance.

---

## 1. Architectural Topology

```
+-------------------------------------------------------------+
|         Multi-Agent Swarm (Windows & Mac Lanes)             |
|   - Agent Context Trimmer                                   |
|   - Opportunity Warehouse Settlement Daemon                 |
|   - Distributed Mutex Arbiter                               |
+-------------------------------------------------------------+
                            |
           [W3C TraceContext: traceparent & baggage]
                            |
   +------------------------v-----------------------------+
   |          Local OTel In-Memory Ring Buffer            |
   |          - Bounded 16MB Non-Blocking Queue           |
   |          - Exponential Backoff Re-attempt            |
   +------------------------------------------------------+
                            |
           [OTLP/gRPC Protobuf Batch Export]
                            |
   +------------------------v-----------------------------+
   |        Enterprise OpenTelemetry Collector           |
   |   +-----------------------------------------------+  |
   |   | PII Scrubbing / Prompt Redaction Pipeline     |  |
   |   | Token Usage Aggregator & Cost Accounting      |  |
   |   | Jaeger / Prometheus / Splunk Exporters        |  |
   |   +-----------------------------------------------+  |
   +------------------------------------------------------+
```

---

## 2. Standardized GenAI Attributes & Semantic Conventions
All spans produced by autonomous agent operations adhere to OTel Semantic Conventions for GenAI:
- `gen_ai.system`: Identifies the underlying LLM provider (e.g., `anthropic`, `openai`, `gemini`).
- `gen_ai.request.model`: Target model string (e.g., `claude-3-5-sonnet`, `gemini-1.5-pro`).
- `gen_ai.usage.prompt_tokens`: Monotonically counted input tokens.
- `gen_ai.usage.completion_tokens`: Monotonically counted output tokens.
- `gen_ai.usage.total_cost_eur`: Real-time financial attribution (strictly €0.00 for autonomous loops).
- `agent.phase_id`: Explicit workflow milestone phase identifier (e.g., `Phase-298`).
- `agent.lane_id`: Machine partition origin (`WINDOWS_LANE_PRIMARY` vs `MAC_LANE_PRIMARY`).

---

## 3. Resilience & Zero-Spend Constraints
1. **Local Ring-Buffer Drop Semantics**: If the enterprise telemetry endpoint is unreachable, spans are stored in a bounded 16MB ring buffer. Once full, lowest-priority debug traces are discarded to prevent process memory exhaustion.
2. **Deterministic Anonymization**: Outgoing traces pass through high-speed regex sanitizers stripping personal identifiers, API authorization bearer tokens, and private client hashes before crossing the network boundary.
3. **Zero Autonomous Cloud Cost**: Spans route directly to internal localhost / LAN collectors or mock persistent jsonl sinks without creating billable egress or cloud telemetry fees.

```json
{
  "telemetryStandard": "OpenTelemetry 1.28.0 OTLP/gRPC",
  "w3cTracePropagation": true,
  "localBufferMaxMb": 16,
  "dropPolicy": "DiscardOldestNonCritical",
  "piiScrubbing": "StrictRegexAndDeterministicHash",
  "autonomousCloudCost": "EUR 0.00"
}
```
