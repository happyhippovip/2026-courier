# Enterprise Air-Gapped & Offline Deployment Playbook

## Executive Summary
For enterprise customers in defense, aerospace, financial banking, and healthcare running on-premises infrastructure with zero outbound internet connectivity, **Symphony Context Trimmer** supports 100% self-contained, air-gapped deployment.

No telemetry, no external DNS lookups, no cloud license verification pings, and zero external runtime dependencies.

---

## 1. Distribution Artifacts & Integrity Verification

The offline installation bundle is distributed as a signed, self-contained archive:
- **Archive**: `symphony-context-trimmer-v1.0.0-airgapped-linux-amd64.tar.gz`
- **SHA-256 Digest**: `a92f8b50e32...[VERIFIED_SHA256]`
- **PGP Detached Signature**: `symphony-context-trimmer-v1.0.0.sig`

### Verification Procedure
```bash
sha256sum -c symphony-context-trimmer.sha256
gpg --verify symphony-context-trimmer-v1.0.0.sig symphony-context-trimmer-v1.0.0-airgapped-linux-amd64.tar.gz
```

---

## 2. Air-Gapped Architecture

```
[ Air-Gapped Enterprise VPC / On-Prem Datacenter ]
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  [ Enterprise Private Registry (Harbor / Artifactory) ]      │
│         │                                                   │
│         ▼                                                   │
│  [ Symphony Context Trimmer Daemon (Local Pod / Sidecar) ]  │
│         │ (Unix Domain Socket / gRPC localhost:50051)       │
│         ▼                                                   │
│  [ Local Self-Hosted LLM Runtime (vLLM / Ollama / TGI) ]   │
│         │                                                   │
│  (100% Zero External Egress / Loopback Only)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Installation & Configuration

### Step 1: Image Mirroring to Internal Harbor
```bash
docker load < symphony-context-trimmer-v1.0.0.tar
docker tag symphony/context-trimmer:1.0.0 registry.internal.corp/ai/context-trimmer:1.0.0
docker push registry.internal.corp/ai/context-trimmer:1.0.0
```

### Step 2: Offline Air-Gapped License Provisioning
Enterprise keys are verified purely via asymmetric Ed25519 cryptography with pre-bundled public keys:
```bash
export SYMPHONY_OFFLINE_LICENSE_KEY="ENT-2026-ED25519-A99B88-AIRGAP"
export SYMPHONY_TELEMETRY_DISABLED=true
export SYMPHONY_OFFLINE_MODE=true
```

### Step 3: Kubernetes Sidecar Deployment
Deploy as an inline context-pruning sidecar proxy in front of local inference endpoints:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: local-llm-agent-gateway
spec:
  template:
    spec:
      containers:
      - name: context-trimmer-proxy
        image: registry.internal.corp/ai/context-trimmer:1.0.0
        env:
        - name: SYMPHONY_OFFLINE_MODE
          value: "true"
        - name: UPSTREAM_MODEL_URL
          value: "http://127.0.0.1:8000/v1"
        ports:
        - containerPort: 8080
        securityContext:
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 10001
          allowPrivilegeEscalation: false
```

---

## 4. Compliance Attestation
- **Zero DNS Egress**: All networking is strictly bound to `127.0.0.1` or internal Kubernetes overlay networks.
- **FIPS 140-2 Cryptography**: Uses Node.js / OpenSSL FIPS-compliant cryptographic modules for HMAC and Ed25519 validation.
- **Auditable Source Manifest**: All dependencies vendored in `/vendor` with comprehensive SBOM.
