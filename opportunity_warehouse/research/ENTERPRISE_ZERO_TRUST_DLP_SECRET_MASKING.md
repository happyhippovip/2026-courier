# Enterprise Zero-Trust Data Loss Prevention (DLP) & Secret Masking Specification

**Document Reference**: `SPEC-ENTERPRISE-ZERO-TRUST-DLP-2026`  
**Classification**: Enterprise Information Security & Data Governance Whitepaper  
**Compliance Context**: NIST SP 800-53 (SC-28 Protection of Information at Rest), PCI DSS 4.0, HIPAA Security Rule §164.312  
**Target Systems**: Autonomous Context Window Ingestion, Shell Command Execution, and Outbound Webhooks

---

## Executive Summary
Autonomous agents process external user requests, database query outputs, and third-party API logs. If sensitive secrets (AWS keys, database passwords, private keys, credit cards) inadvertently enter the LLM context window, they risk exfiltration through model transcripts, prompt injection attacks, or downstream logging.

This specification details the **Symphony Context DLP & Secret Masking Architecture**, enforcing pre-ingestion redaction with zero token overhead.

---

## 1. Multi-Stage DLP Filtering Pipeline

```
+-----------------------+
|  Raw Ingestion Stream | (Tool output, shell stdout, user prompt)
+-----------------------+
            |
            v
+-----------------------+
| Regex Heuristic Match | --> Detects known key formats (AKIA..., sk-proj-..., ghp_...)
+-----------------------+
            |
            v
+-----------------------+
| Shannon Entropy Gate  | --> Flags strings with H > 4.2 bits/char (Base64/Hex secrets)
+-----------------------+
            |
            v
+-----------------------+         Stores mapping locally
| Secure Vault Tokenizer| -------------------------------------> [ Local Ephemeral Key Vault ]
+-----------------------+                                        (In-memory, wiped on exit)
            |
            | Emits synthetic token (e.g. [MASKED_SECRET_AWS_KEY_01])
            v
+-----------------------+
| LLM Context Window    |
+-----------------------+
```

---

## 2. Key Capabilities
1. **Zero Raw Secret Exposure**: The LLM prompt receives only synthetic opaque tokens (`[MASKED_SECRET_01]`).
2. **Deterministic Tool Detokenization**: When the agent passes the synthetic token to an authorized local tool (e.g. calling an internal database), the tool gateway swaps the token back to the real secret inside the secure localhost process memory without exposing it to the model.
3. **Entropy-Based Unknown Secret Detection**: Scans arbitrary alphanumeric tokens $> 20$ chars; if Shannon entropy $H > 4.2$, marks the token as high-risk secret and redacts it automatically.
