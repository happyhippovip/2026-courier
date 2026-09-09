# COURIER COORDINATION POLICY: CROSS-DEVICE TASK INTAKE, TEAM MODEL & DONE YES/NO

## 1. One Company / One Team Architecture
Courier coordinates Mac and Windows as execution environments of **ONE organization, ONE canonical project system, and ONE unified team** — not as separate projects.

```text
HUMAN
→ CHIEF
→ COURIER
→ SHARED TEAM
   ├── MAC WORKSPACE
   ├── WINDOWS WORKSPACE
   ├── GEMINI / ANTIGRAVITY (Agent Capability)
   ├── CLI1 (Deterministic Inspection)
   ├── CODEX (High Information Gain Specialist)
   └── CONNECTED REMOTE SERVICES (GitHub, Cloud APIs)
```

- A task may initiate on one host (e.g. Windows) and conclude on another (e.g. Chief / Mac).
- A result from Windows is a team result; a result from Mac is a team result.
- Completion belongs to the **CANONICAL TASK**, not to a single machine in isolation.

---

## 2. Agent (Capability) vs. Host (Environment) Separation
- **AGENT**: The cognitive or algorithmic actor (e.g. `GEMINI`, `CLI1`, `CODEX`, `CHIEF`).
- **HOST**: The physical or execution environment (`WINDOWS`, `MAC`, `REMOTE`, or `UNKNOWN`).
- **Strict Invariant**:
  - `AGENT = GEMINI` can run on `HOST = WINDOWS` or `HOST = MAC`.
  - Never equate `GOOGLE = WINDOWS` or `GOOGLE = MAC`.
  - Host is inferred strictly from evidence (e.g. `C:\Users\...` $\rightarrow$ Windows, `/Users/...` $\rightarrow$ Mac). If evidence is absent, host is `UNKNOWN` (never guessed).

---

## 3. Shared Task Identity & Two-Level Done Model
```text
LOCAL_STEP_ERLEDIGT: JA|NEIN
GESAMTAUFGABE_ERLEDIGT: JA|NEIN
```
- A successful local machine step (`LOCAL_STEP_ERLEDIGT: JA`) does **not** close the overall canonical task if subsequent phases (such as remote sync or integration) remain pending or blocked.
- Overall `ERLEDIGT: JA` requires proof that the requested canonical effect has been verified on the target resource.
- If a step is blocked (e.g. by a local human gate):
  ```text
  LOCAL_STEP_ERLEDIGT: JA
  GESAMTAUFGABE_ERLEDIGT: NEIN
  STATUS: BLOCKED
  ERLEDIGT: NEIN
  ```

---

## 4. Cross-Machine Single Writer (`SINGLE_WRITER = YES`)
- The single writer rule applies **across the entire organization**.
- Concurrent write operations across machines targeting the **same repository, branch, or resource** are strictly forbidden:
  ```text
  MAC writer + WINDOWS writer simultaneously on same resource = CONFLICT (SERIALIZE)
  ```
- Independent read-only analysis and inspection may run concurrently across machines.
- Heavy job bounds remain active: `HEAVY_JOB_LIMIT = 1`.

---

## 5. Machine-Specific Human Gate Isolation
- A human gate (such as GitHub authentication required on Windows) blocks operations requiring that specific machine's credential.
- It does **not** freeze the entire company: safe independent Mac analysis, read-only verifications, local test suites, and unrelated tasks continue normally.
- Invariant: No new writer may target the same shared resource if it could conflict with the blocked operation.

---

## 6. Connected Capability Routing vs. Local Machine Bytes
- **Connected Remote Tooling**: If the Chief has an authorized connector (e.g. GitHub API), remote repository inspection and queries are routed to Chief rather than burdening local machines.
- **Local Machine Bytes**: If unpushed commits or files exist only locally on Windows (e.g. `C:\Users\lol\...`), Chief cannot pretend to have remote access to those unuploaded bytes. The local portion is strictly routed to the machine-local agent.
