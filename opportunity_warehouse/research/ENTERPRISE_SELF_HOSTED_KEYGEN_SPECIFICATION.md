# Symphony Enterprise Self-Hosted Keygen & Air-Gapped Licensing Architecture

**Target Audience**: Enterprise Security Engineers, Platform Architects, Air-Gapped Infrastructure Operators  
**Standard**: Asymmetric Cryptographic License Generation (Ed25519)  
**Security Boundary**: 100% Offline / Zero-Internet Connectivity Required  

---

## 1. Architectural Overview

Certain enterprise and defense environments operate under strict SCIF, air-gapped VPC, or FedRAMP High boundaries where connecting to external SaaS billing or license activation portals is strictly forbidden.

`@symphony/agent-context-trimmer` supports an **Enterprise Self-Hosted Keygen Authority**:
- The enterprise generates its own offline master Ed25519 signing keypair.
- The company's central IT or security platform issues signed license tokens for developer seats.
- Local developer installations verify tokens against the enterprise's public key without network calls.

```
  +-------------------------------------------------------------+
  |               Enterprise Air-Gapped Security Enclave        |
  |                                                             |
  |   +-----------------------+     +-----------------------+   |
  |   | Enterprise Root CA /  | --> | Master Ed25519 Keygen |   |
  |   | HashiCorp Vault / KMS |     | Authority (Self-Host) |   |
  |   +-----------------------+     +-----------+-----------+   |
  |                                             |               |
  |                                             v               |
  |                                   [Signed Seat License]     |
  |                                             |               |
  |                  +--------------------------+               |
  |                  |                                          |
  |                  v                                          |
  |       +---------------------+                               |
  |       | Developer DevBox    |                               |
  |       | @symphony/trimmer   | <-- Validates via local       |
  |       | (Offline Engine)    |     enterprise public key     |
  |       +---------------------+                               |
  +-------------------------------------------------------------+
```

---

## 2. Cryptographic Token Specification

Self-hosted enterprise license payloads adhere to the following signed JSON schema:
```json
{
  "header": {
    "alg": "Ed25519",
    "typ": "SYMPHONY-SEAT-V1"
  },
  "claims": {
    "enterprise_id": "ENT-ACME-CORP-9812",
    "department": "AI-INFRA-TEAM",
    "seat_id": "SEAT-DEV-412",
    "max_concurrent_sessions": 4,
    "valid_from": "2026-01-01T00:00:00Z",
    "valid_until": "2027-12-31T23:59:59Z",
    "feature_flags": {
      "ast_pruning": true,
      "stream_compression": true,
      "pii_redactor": true,
      "custom_rule_engine": true
    }
  },
  "signature": "3b2e5f...ed25519_hex_signature..."
}
```

---

## 3. Local Air-Gapped Validation Workflow

When `agent-context-trimmer` executes on a developer's workstation:
1. It reads the local license file from `~/.symphony/license.json` or environment variable `SYMPHONY_ENTERPRISE_LICENSE`.
2. It verifies the signature against the pre-configured enterprise public key in `/etc/symphony/enterprise_pub.pem`.
3. If valid and not expired, execution proceeds with enterprise features unlocked.
4. **Zero network calls occur**.

---

## 4. Revocation & Seat Deprovisioning in Air-Gapped Networks

In zero-trust offline networks, seat deprovisioning is managed via:
1. **Short-Lived Seat Tokens**: Certificates expire on a 30-day or 90-day rolling basis, refreshed via corporate SSO/LDAP artifact distribution.
2. **Local CRL (Certificate Revocation List)**: Distributed through existing corporate IT configuration management (Ansible, Puppet, Chef, Jamf).

---

## 5. Commercial Packaging & Pricing Model
- **Enterprise Self-Hosted Tier**: €799 / year (Includes unlimited internal keygen authority rights, up to 100 developer seats, and dedicated architectural review).
