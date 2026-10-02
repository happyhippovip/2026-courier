# Security & Public Sharing Policy

Date: 2026-09-20  
Status: founder operating rule / public-safe

## Default

Treat screenshots, screen recordings, CloudShell output, terminal output, AWS Console pages and infrastructure diagnostics as **INTERNAL BY DEFAULT**.

## Public posting

Before publishing a screenshot/video, redact or crop:
- passwords;
- MFA codes;
- recovery codes;
- private SSH keys;
- AWS/API access keys;
- secret/session tokens;
- cookies;
- signed/private URLs;
- private email/customer data;
- unnecessary account identifiers;
- instance/server identifiers;
- public IP attribution where not needed;
- key-pair names;
- internal paths;
- terminal history;
- local usernames where not needed.

## Risk interpretation

Seeing infrastructure metadata alone is not the same as owning credentials.  
However, metadata can improve reconnaissance, targeting and phishing, so it should still be minimized.

## Root/admin access

Daily cloud work should move toward least-privilege IAM/roles rather than routine root use. Root/admin accounts should have MFA and be reserved for account-level tasks.

## Secrets

Never commit secrets to GitHub.  
Use a secret manager or protected environment variables with access controls.

## Public repository rule

The Agent Warehouse in this repository is PUBLIC-SAFE documentation only.

Do not add:
- private key paths if they reveal sensitive local structure unnecessarily;
- key contents;
- account IDs;
- private customer/project content;
- private emails;
- payment data;
- browser/session credentials.

## Incident trigger

If an actual secret is exposed publicly:
- remove public exposure;
- revoke/rotate the affected secret;
- review audit logs;
- verify no unauthorized activity occurred.

Do not rotate everything merely because non-secret metadata was visible; rotate the credentials that were actually exposed or suspected compromised.

## Future security roadmap

Include:
- MFA everywhere practical;
- IAM least privilege;
- security-group/firewall review;
- audit logging;
- backup/restore testing;
- key/token rotation policy;
- secrets inventory;
- dependency/update policy;
- private/public data classification;
- post-quantum readiness assessment for long-lived sensitive data and cryptographic dependencies.
