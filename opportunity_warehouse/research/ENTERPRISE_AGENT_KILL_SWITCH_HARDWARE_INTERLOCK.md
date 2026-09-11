# Enterprise Autonomous Agent Kill-Switch & Hardware Interlock Architecture

**Document Reference**: SPEC-KILL-2026-V98  
**Classification**: Enterprise Safety & Containment Architecture Whitepaper  
**Target Standard**: NIST AI RMF 1.0 (MANAGE-2.4), US Executive Order 14110 Section 4, EU AI Act Article 14 (Human Oversight)  
**Scope**: Defense-in-Depth Containment, Dead-Man's Cryptographic Heartbeat, Kernel Cgroup Freezers, Physical Air-Gap Disconnect  

---

## 1. Executive Summary: The Autonomous Rogue Agent Containment Problem

As autonomous AI agents acquire expanded tool calling authority (executing shell commands, writing code, dispatching API webhooks, initiating commercial transactions), standard software-level guardrails become vulnerable to prompt injection, semantic hallucinations, and jailbreaks. A compromised agent could theoretically attempt to bypass software filters or spawn rogue subprocesses.

This specification details Symphony's **Defense-in-Depth Hardware Interlock & Kill-Switch System (DHIS)**, architected to guarantee immediate, irrevocable, and tamper-proof termination of any agent subsystem within **< 10 milliseconds**, independent of the LLM's cooperation.

---

## 2. The 4-Layer Defense-in-Depth Kill-Switch Hierarchy

```
+---------------------------------------------------------------------------------+
|                        4-LAYER AGENT CONTAINMENT MATRIX                         |
+-------+--------------------+------------------------+---------------------------+
| Layer | Interlock Type     | Latency / Trigger      | Containment Action        |
+-------+--------------------+------------------------+---------------------------+
| L4    | Application Filter | < 1ms                  | Exception thrown,         |
|       | (Software Guard)   | Regex / AST Violation  | Turn immediately aborted  |
+-------+--------------------+------------------------+---------------------------+
| L3    | Network Firewall   | < 5ms                  | Ephemeral token revoked,  |
|       | (eBPF / iptables)  | Outbound Anomaly       | TCP RST injected on WAN   |
+-------+--------------------+------------------------+---------------------------+
| L2    | Kernel Freezer     | < 10ms                 | `SIGSTOP` / cgroup freeze|
|       | (Linux Cgroups v2) | Resource Cap Exceeded  | Process tree paused       |
+-------+--------------------+------------------------+---------------------------+
| L1    | Hardware Relay     | < 25ms                 | Physical power cutoff to  |
|       | (Physical Switch)  | Dead-Man Heartbeat Lost| TEE / Isolated VM Enclave |
+-------+--------------------+------------------------+---------------------------+
```

---

## 3. Asymmetric Dead-Man's Cryptographic Heartbeat

Autonomous agents operating on sensitive tasks (such as commercial settlement or context state updates) must continuously verify their authorization via a cryptographic heartbeat:
1. **Challenge Issuance**: The human supervisor control plane publishes a signed non-reusable nonce every $60$ seconds.
2. **Attestation Response**: The agent runtime must respond with a hardware TPM/enclave quote proving uncompromised state invariants (e.g., `spend == 0.00`, `mac_scope_unmodified == true`).
3. **Fail-Closed Expiration**: If three consecutive heartbeats lapse ($180$s), the L2 kernel freezer immediately halts execution, revokes all API tokens, and alerts human operators.

---

## 4. Hardware Interlock Electrical Isolation (L1)

For high-assurance deployments, agent virtual machines run on dedicated micro-servers connected to network switches via optically switched relays.
- In the event of a catastrophic safety trip, the optical relay physically cuts the transmit fiber.
- Zero reliance on kernel software or operating system network stacks.

---

## 5. Enterprise Compliance & Verification Matrix

1. **EU AI Act Article 14**: Provides human operators with "the ability to decide, in any particular situation, not to use the high-risk AI system or otherwise disregard, override or reverse the output."
2. **NIST AI RMF MANAGE-2.4**: Demonstrates verifiable mechanisms to "deactivate or replace AI systems that perform outside acceptable tolerance levels."
3. **FinOps Invariant**: Guarantees autonomous spend can never exceed €0.00 under any hardware or software failure mode.
