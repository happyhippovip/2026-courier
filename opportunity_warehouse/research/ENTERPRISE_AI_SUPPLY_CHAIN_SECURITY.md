# Enterprise AI Supply Chain Security & Attestation Specification (SLSA Level 3 & in-toto)

**Document Reference**: SPEC-SEC-2026-V80  
**Classification**: Enterprise Security & Compliance Whitepaper  
**Target Standard**: SLSA v1.0 (Build Level 3), in-toto Attestation Framework, CycloneDX v1.6 AI-BOM  
**Scope**: Autonomous Multi-Agent Systems, LLM Prompt Chains, Dynamic Context Windows & Packaging  

---

## 1. Executive Summary: The Agentic Software Supply Chain Attack Surface

As enterprise engineering organizations transition from isolated machine learning models to autonomous multi-agent systems, the software supply chain attack surface undergoes a qualitative paradigm shift. Traditional application security focuses on binary provenance, third-party package dependencies (e.g., npm, PyPI, crates.io), and static code analysis. In contrast, autonomous agent architectures introduce dynamic runtime attack vectors:

1. **Non-Hermetic Runtime Dependencies**: External retrieval-augmented generation (RAG) indices, dynamic tool invocation registries, and live API endpoints.
2. **Prompt Injection & Adversarial Payloads**: Indirect prompt injection embedded within ingested documentation or multi-turn conversational history.
3. **Model Weight & Tokenizer Tampering**: Silent backdoors in open-weights checkpoints, compromised embedding models, and unpinned fine-tuned adapters.
4. **Agent Orchestration Tampering**: In-flight modification of context window assembly buffers, execution plan graphs, and tool invocation arguments.

This whitepaper establishes the authoritative architectural blueprint for securing autonomous agent software pipelines to **SLSA (Supply-chain Levels for Software Artifacts) Build Level 3** and implementing cryptographic **in-toto provenance attestations** across the entire lifecycle of agent artifact creation, distribution, and execution.

---

## 2. SLSA Level 3 Compliance for Autonomous AI Systems

The SLSA framework categorizes supply chain integrity into three progressive build levels. Achieving SLSA Level 3 guarantees that build platforms are hardened against insider threats, tampering, and forged provenance metadata.

```
+---------------------------------------------------------------------------------+
|                        SLSA LEVEL 3 COMPLIANCE MATRIX                           |
+---------------------+-----------------------------------------------------------+
| Requirement         | Enterprise Implementation                                 |
+---------------------+-----------------------------------------------------------+
| Source Integrity    | Cryptographically signed Git commits (Ed25519)            |
|                     | Two-person code review enforced via branch protection     |
+---------------------+-----------------------------------------------------------+
| Hermetic Build      | Isolated container execution with zero internet access    |
|                     | All dependencies resolved via cryptographically pinned    |
|                     | content-addressed lockfiles (SHA-256)                     |
+---------------------+-----------------------------------------------------------+
| Ephemeral Builder   | Every artifact built in a clean, disposable VM/container  |
|                     | Secrets never persisted across build boundaries           |
+---------------------+-----------------------------------------------------------+
| Verifiable Provenance| in-toto attestation generated directly by the trusted    |
|                     | builder, signed with KMS hardware security module (HSM)   |
+---------------------+-----------------------------------------------------------+
```

### 2.1 Hermetic Context & Model Assembly
To satisfy SLSA Level 3, the agent packaging process (including context trimmer engines, rule compilations, and prompt template freezes) must execute in a strictly hermetic environment:
- Network isolation: All external network egress is blocked during build time (`iptables -P OUTPUT DROP`).
- Explicit inputs: Every model parameter, base prompt, and rule file is passed as an immutable, hash-addressed artifact.
- Deterministic output: Identical source inputs and dependency lockfiles produce bit-for-bit identical distribution packages (`SOURCE_DATE_EPOCH` normalization).

---

## 3. in-toto Cryptographic Attestation Architecture

The in-toto framework ensures that every step in the software supply chain is performed exclusively by authorized functionaries according to a strictly defined layout.

```
+------------------+       +-------------------+       +--------------------+
|  Step 1: Author  | ----> |  Step 2: Package  | ----> |  Step 3: Release   |
|  (Git Signing)   |       |  (Hermetic Build) |       |  (Cosign / KMS)    |
+------------------+       +-------------------+       +--------------------+
        |                            |                           |
   git_commit.link             build_agent.link            release_pkg.link
        \                            |                          /
         +---------------------------+-------------------------+
                                     |
                          [in-toto root.layout]
                                     |
                          [Verification Gatekeeper]
```

### 3.1 Attestation Predicate Format
Every agent build emits a standardized in-toto attestation adhering to the SLSA Provenance v1.0 specification:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "agent-context-trimmer-v1.0.0.tar.gz",
      "digest": {
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://symphony.enterprise.ai/slsa/v1",
      "externalParameters": {
        "sourceUri": "git+https://github.com/enterprise/agent-core.git",
        "commit": "a1b2c3d4e5f67890123456789abcdef012345678"
      },
      "internalParameters": {
        "hermetic": true,
        "builderImage": "ghcr.io/enterprise/agent-builder@sha256:7f83b1..."
      }
    },
    "runDetails": {
      "builder": {
        "id": "https://symphony.enterprise.ai/builders/hsm-builder-01"
      },
      "metadata": {
        "invocationId": "inv-2026-09-11-884920",
        "startedOn": "2026-09-11T10:00:00Z",
        "finishedOn": "2026-09-11T10:01:15Z"
      }
    }
  }
}
```

---

## 4. AI-BOM: CycloneDX & SPDX Extensions for Autonomous Systems

Standard SBOMs list software libraries, but fail to capture the critical AI-specific components that dictate agent runtime behavior. Symphony requires an **AI-BOM (Artificial Intelligence Bill of Materials)** incorporating:

1. **Prompt Template Hashes**: Cryptographic SHA-256 hashes of system prompts, agent persona definitions, and safety boundaries.
2. **Tokenizer Configurations**: Explicit vocabulary tables, byte-pair encodings, and normalization rules.
3. **Embedding Model Fingerprints**: Checksums and quantization schemas of local semantic search models.
4. **Tool Capability Manifests**: Canonical schemas of all accessible MCP tools and executable sandbox commands.

---

## 5. Continuous Verification & Deployment Gateways

Before an agent package or context trimmer engine is permitted to execute in production:
1. **Signature Verification**: Validate the cryptographic signature using Sigstore / Cosign against corporate hardware keys.
2. **Provenance Policy Enforcement**: Validate using Open Policy Agent (OPA) that `hermetic == true` and builder identity matches the authorized enterprise PKI.
3. **Tamper Detection**: Verify that no uncommitted modifications exist in the runtime environment.

---

## 6. Conclusion & Operational Roadmap

By coupling SLSA Level 3 hermetic builds with in-toto cryptographic provenance attestations and CycloneDX AI-BOMs, autonomous multi-agent environments achieve mathematically verifiable supply chain integrity. Enterprise deployments eliminate prompt tampering, dependency hijacking, and unauthorized code execution, ensuring full compliance with European Union AI Act Article 15 (Accuracy, Robustness and Cybersecurity) and US Executive Order 14110.
