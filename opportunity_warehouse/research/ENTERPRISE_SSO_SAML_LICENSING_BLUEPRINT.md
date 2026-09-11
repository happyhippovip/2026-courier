# Enterprise SSO & SAML 2.0 / OIDC Licensing Architecture Blueprint

**Target Customer**: Fortune 500 Enterprise IT & Security Architecture Teams  
**Product**: `agent-context-trimmer` Enterprise Team Pack (€199/yr - €799/yr)  
**Standard**: SAML 2.0 / OpenID Connect (OIDC) with Offline Public Key Verification  

---

## 1. Architectural Philosophy: Zero-Egress SSO
Most enterprise tools mandate an always-online cloud auth proxy to check user seats. For privacy-conscious software shops (finance, healthcare, defense), this is unacceptable.

**Symphony's Zero-Egress Architecture**:
1. **IdP Authentication**: Organization authenticates developer once via standard enterprise IdP (Okta, Microsoft Entra ID / Azure AD, Ping Identity).
2. **Signed Token Generation**: Company IT admin dashboard issues an Ed25519-signed offline JWT containing the developer's authorized seat, team scope, and expiration date.
3. **Local CLI Verification**: `agent-context-trimmer` embeds the organization's public key locally. The CLI validates seat integrity in <2ms using zero network calls.

---

## 2. Token Payload Specification

```json
{
  "iss": "symphony.enterprise.issuer",
  "sub": "dev-0429@megacorp.com",
  "aud": "symphony:agent-context-trimmer",
  "orgId": "ORG_CORP_GLOBAL_77",
  "tier": "ENTERPRISE_UNLIMITED",
  "seatsAllocated": 100,
  "iat": 1789123200,
  "exp": 1820659200,
  "features": [
    "ast_syntax_guard",
    "pre_commit_linter",
    "budget_reallocator",
    "differential_privacy_telemetry"
  ],
  "pubKeyId": "symphony_corp_2026_pub_01"
}
```

---

## 3. Supported Identity Providers (IdP)

| Provider | Protocol | Integration Method |
| :--- | :--- | :--- |
| **Microsoft Entra ID (Azure AD)** | OIDC / OAuth2 | SCIM Seat Provisioning + Local JWT Export |
| **Okta** | SAML 2.0 / OIDC | Okta App Integration Wizard + Pre-signed License Injector |
| **Ping Identity / PingFederate** | SAML 2.0 | XML Metadata Exchange + Automated Key Rotation |
| **GitHub Enterprise** | OIDC | Organization Team Mapping (`@org/ai-engineers`) |

---

## 4. Local Verification Flow
1. Developer installs CLI via `npm i -g @symphony/agent-context-trimmer`.
2. Developer activates seat: `trimmer activate --sso-token <JWT_TOKEN>`.
3. CLI reads embedded `enterprise_pubkey.pem`, verifies signature with `crypto.verify`.
4. If valid, writes cached seat confirmation to local protected config directory.
5. All subsequent trims execute immediately with zero external network verification.

---

## 5. Security & Governance Guarantees
- **No Inbound Open Ports**: Zero local daemon listening sockets.
- **Air-Gap Compatible**: Can be provisioned via MDM (Jamf, InTune, Ansible) across 10,000 developer laptops.
- **Revocation**: Supported via local CRL (Certificate Revocation List) update or token expiration timestamps.
