# Enterprise Kubernetes Operator & Sidecar Proxy Architecture

## Executive Overview
In enterprise platform engineering environments deploying agentic clusters across Amazon EKS, Google GKE, and Red Hat OpenShift, engineering teams cannot manually modify hundreds of developer pod manifests to integrate context pruning.

The **Symphony Kubernetes Operator** provides declarative, cluster-wide context optimization via Kubernetes Custom Resources and automated Mutating Admission Webhooks.

---

## 1. The `SymphonyContextProxy` Custom Resource (CRD)

```yaml
apiVersion: symphony.io/v1alpha1
kind: SymphonyContextPolicy
metadata:
  name: engineering-squad-standard
  namespace: agent-workloads
spec:
  targetPods:
    matchLabels:
      role: ai-agent
  pruningProfile: "aggressive-ast"
  tokenBudget:
    maxWindowTokens: 128000
    perTurnThreshold: 24000
  rateLimiting:
    burstCapacityTokens: 50000
    sustainedTokensPerSec: 5000
  kmsEncryption:
    enabled: true
    vaultPath: "secret/data/symphony/keys"
```

---

## 2. Mutating Webhook Injection Flow

```
[ Developer kubectl apply / Helm Deploy ]
                   │
                   ▼
     [ K8s API Server Admission ]
                   │
                   ▼
     [ Symphony Mutating Webhook ]
   • Checks pod labels for 'role: ai-agent'
   • Injects 'symphony-trimmer-sidecar' container
   • Re-routes loopback port 8000 -> sidecar port 8080
                   │
                   ▼
     [ Pod Scheduled & Running ]
┌───────────────────────────────────────────────┐
│ Pod: coder-agent-7f98b                        │
│ ┌───────────────────┐   ┌───────────────────┐ │
│ │  Agent Container  │──►│ Trimmer Sidecar   │ │
│ │  (Prompt Origin)  │   │ (AST & KMS Gate)  │ │
│ └───────────────────┘   └─────────┬─────────┘ │
│                                   │           │
└───────────────────────────────────┼───────────┘
                                    ▼
                         [ Remote Inference Endpoint ]
```

---

## 3. Production Hardening Guarantees
- **Zero-Downtime Sidecar Failover**: If the sidecar container runs out of memory or crashes, the envoy proxy automatically bypasses to raw upstream inference (fail-open) while tripping a SEV-3 alert.
- **Rootless Security Context**: Runs under UID `10001`, `readOnlyRootFilesystem: true`, and dropped `ALL` Linux capabilities.
