# Enterprise Post-Quantum Cryptography (PQC) Migration & Hybrid Key Encapsulation Architecture

**Document Reference**: SPEC-PQC-2026-V92  
**Classification**: Enterprise Quantum-Resilience Whitepaper  
**Target Standard**: NIST FIPS 203 (ML-KEM), NIST FIPS 204 (ML-DSA), NIST FIPS 205 (SLH-DSA), BSI TR-02102-1  
**Scope**: Agent State Encryption, Commercial Settlement Signatures, Ephemeral Key Encapsulation, HNDL Threat Mitigation  

---

## 1. Executive Summary: The "Harvest Now, Decrypt Later" Threat

Adversarial nation-states and well-resourced threat actors currently intercept and store encrypted enterprise telemetry, proprietary agent state checkpoints, and intellectual property. The advent of Cryptanalytically Relevant Quantum Computers (CRQCs) running Shor's Algorithm will retroactively break traditional public-key cryptography (RSA-2048/4096 and ECDSA/Ed25519 on NIST P-256 and Curve25519).

To protect Symphony's commercial trade secrets, license key verifications, and financial settlement audit trails against **Harvest Now, Decrypt Later (HNDL)** attacks, this whitepaper establishes the enterprise blueprint for transitioning to **NIST-standardized Post-Quantum Cryptography (PQC)** using a dual-layer **hybrid classical/quantum key encapsulation** architecture.

---

## 2. NIST Post-Quantum Cryptography Standards Matrix

```
+---------------------------------------------------------------------------------+
|                         NIST PQC STANDARDIZATION MATRIX                         |
+-------------------+---------------------+---------------------------------------+
| NIST Standard     | Algorithm / Family  | Symphony Enterprise Deployment Target |
+-------------------+---------------------+---------------------------------------+
| FIPS 203          | ML-KEM              | Ephemeral Session Key Encapsulation   |
|                   | (Module-Lattice)    | (Hybrid X25519 + ML-KEM-768)          |
+-------------------+---------------------+---------------------------------------+
| FIPS 204          | ML-DSA              | High-Throughput Agent Action Signing  |
|                   | (Dilithium-based)   | (ML-DSA-65 for Commercial Invariants) |
+-------------------+---------------------+---------------------------------------+
| FIPS 205          | SLH-DSA             | Long-Term Root Authority / Firmware   |
|                   | (SPHINCS+ stateless)| (SLH-DSA-SHAKE-128s for Master Keys)  |
+-------------------+---------------------+---------------------------------------+
```

---

## 3. Hybrid Key Encapsulation Mechanism (X25519 + ML-KEM-768)

To guarantee that quantum migration introduces zero risk of regressions should an unproven lattice weakness emerge, Symphony mandates a hybrid composite scheme:

```
  [ Client Agent ]                                         [ Server / Gateway ]
         |                                                           |
         | --- 1. Client Hello (pk_classical, pk_mlkem768) --------> |
         |                                                           |
         |                                     2. Server Encapsulates:
         |                                        - ss_c = X25519(pk_c, sk_c_serv)
         |                                        - (ct_q, ss_q) = ML-KEM-Enc(pk_q)
         |                                                           |
         | <--- 3. Server Reply (pk_c_serv, ct_q) -------------------|
         |                                                           |
  4. Client Decapsulates:                                            |
     - ss_c = X25519(...)                                            |
     - ss_q = ML-KEM-Dec(sk_q, ct_q)                                 |
         |                                                           |
         +-----------------------------+-----------------------------+
                                       |
                   [ Shared Secret Derivation ]
          K = HKDF-SHA256(ss_classical || ss_mlkem768 || salt)
                                       |
                   [ AES-256-GCM Ephemeral Session Key ]
```

### 3.1 Security Invariant
Even if an adversary possesses a CRQC capable of computing discrete logarithms in Curve25519, the derived key $K$ remains unconditionally secure unless the adversary simultaneously breaks the Short Integer Solution (SIS) and Learning With Errors (LWE) lattice problems underpinning ML-KEM-768.

---

## 4. Performance & Token Overhead Benchmarking

- **ML-KEM-768 Public Key**: 1,184 bytes (vs 32 bytes X25519).
- **ML-KEM-768 Ciphertext**: 1,088 bytes.
- **ML-DSA-65 Signature**: 3,309 bytes (vs 64 bytes Ed25519).
- **Inference Impact**: Hybrid key exchange adds less than 1.4ms of latency over pure classical TLS, with zero measurable impact on LLM prompt token throughput.

---

## 5. Enterprise Roadmap & Compliance Gateways

1. **Phase 1 (Hybrid Telemetry)**: All cross-machine agent synchronization and state checkpoint replication enforce hybrid X25519 + ML-KEM-768 encryption.
2. **Phase 2 (Dual-Signed Evidence)**: Every `EvidenceLedger` entry carries dual classical (Ed25519) and post-quantum (ML-DSA-65) signatures.
3. **Phase 3 (Full PQC Cutover)**: Complete decommissioning of non-quantum-resistant public key infrastructure by 2030, in compliance with CNSA 2.0 timelines.
