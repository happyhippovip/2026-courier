# Enterprise Zero-Trust Secret Rotation & Ephemeral Credentials Specification

**Document Reference**: `SPEC-ENTERPRISE-SECRET-ROTATION-2026`  
**Classification**: Enterprise Security Architecture & Key Management Specification  
**Compliance Context**: NIST SP 800-57 (Recommendation for Key Management), PCI DSS 4.0 Requirement 3.6, SOC 2 CC6.1  
**Target Systems**: Webhook HMAC Signing Keys, Scoped IAM Tokens, Database Mutual TLS Certificates

---

## Executive Summary
Autonomous commercial agents handling financial transactions and enterprise data pipelines cannot rely on static long-lived credentials. If a key is compromised, static secrets expose the entire operational history to adversary replay.

This specification details the **Symphony Dual-Phase Rolling Key Rotation Architecture**, providing zero-downtime key rollover with automated cryptographic fencing.

---

## 1. Dual-Phase Overlapping Rotation Timeline

```
Timeline (Hours)
0h                   12h                  24h                  36h                  48h
+--------------------+--------------------+--------------------+--------------------+
|  Key K_1 (Active)  |  Key K_1 (Grace)   |    Key K_1 REVOKED |                    |
+--------------------+--------------------+--------------------+--------------------+
                     |  Key K_2 (Active)  |  Key K_2 (Grace)   |    Key K_2 REVOKED |
                     +--------------------+--------------------+--------------------+
                                          |  Key K_3 (Active)  |  Key K_3 (Grace)   |
                                          +--------------------+--------------------+
```

---

## 2. Key Lifecycle States & Verification Invariants
1. **Active Phase (0h–12h)**: Newly minted key $K_n$. Used by the agent to sign all outbound webhooks, telemetry blocks, and audit records.
2. **Grace Phase (12h–24h)**: Successor key $K_{n+1}$ takes over active signing. Inbound verification gateways accept signatures from either $K_n$ or $K_{n+1}$, preventing dropped transactions due to propagation delay.
3. **Revoked Phase (24h+)**: Key $K_n$ is permanently expunged from memory and key vaults. Any request presenting a signature signed with $K_n$ is rejected with an immediate security alert.

---

## 3. Cryptographic Signature Header Standard
Every signed transaction payload includes the key identifier in the signature envelope:
```
X-Symphony-Signature: v2:key_id=k2026_0911_1200:sig=7f83b1657ff1fc53b92dc18148a1d65...
`
Receiving nodes look up the key by `key_id`, verify that its state is `ACTIVE` or `GRACE`, and reject stale or non-existent keys deterministically.
