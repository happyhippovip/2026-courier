# Physical Canary Proof: A -> VERIFY -> B & Deterministic Restart

HOST=MAC (Darwin 25.6.0 x86_64, MacBook-Pro-von-user.local)
ROLE=PHYSICAL_CANARY_PREPARATION_OWNER
DATE=2026-09-26
TIME=17:32 CET

## 1. Physical Verification Truth

- **AUFTRAG**: `goal-canary-01`
- **A_ERLEDIGT**: `YES`
- **A_GEPRUEFT**: `YES`
- **B_AUTOMATISCH_GESTARTET**: `YES`
- **B_ERLEDIGT**: `YES`
- **A_EXECUTION_COUNT**: `1`
- **HUMAN_RELAY_COUNT**: `0`
- **CANDIDATE_SHA**: `4c1e24ccc522042af826bc4c2b595daf85d097f9` (origin/candidate-b-1)
- **BEWEIS**: `HERMETIC_PHYSICAL_RUN_PORT_8081_CANDIDATE_B_1`

---

## 2. Hardware & Runtime Evidence

| Metric / Dimension | Measured Physical Reality |
|---|---|
| **Server Port** | `8081` (Hermetic isolated test port; port 8080 production undisturbed) |
| **Server PID (Run 1)** | `98844` |
| **Server PID (Run 2)** | `98845` (Restarted after `SIGKILL`) |
| **Worker Identity** | `MAC-01` |
| **Verifier Identity** | `VERIFIER-01` |
| **Canary A Artifact** | `canary_A.txt` (13 bytes: `COURIER-A2B-A`) |
| **Canary A SHA-256** | `575114332fb4ccd482dd9ca60dbaccc15b579afeb372f0c92b6f7eefe219049b` |
| **Canary A Server ID** | `art-6e11306e6144cb9f2b65eac615b461202ebb05e424416a400f55f3aeb4c40a25` |
| **Canary A Dispatch** | `dispatch-28864ad081fb47569bcf1f64a543ab76` |
| **Canary A Result** | `ACK_RESULT_RECEIVED` -> `VERIFIER-01` PASS -> `RECONCILED` |
| **Canary B Artifact** | `canary_B.txt` (13 bytes: `COURIER-A2B-B`) |
| **Canary B SHA-256** | `3297be4a21a5b49786920ed3340c4f0dafee54d65e3d863e68d2799e05fc14ed` |
| **Canary B Server ID** | `art-3507749063c58a5e281b24e3d388fe684edfa488c1dce0b7659b5e9f7cef2a67` |
| **Canary B Dispatch** | `dispatch-4ac4c1fe4f5e4922907862cb5b154244` |
| **Canary B Result** | `ACK_RESULT_RECEIVED` -> `VERIFIER-01` PASS -> `RECONCILED` |
| **Human Relay Interventions** | `0` (Automated step transition via REST verifier callback) |
| **Restart Proof** | `SIGKILL` on PID 98844 -> state reloaded on PID 98845 -> zero replay of Task A |

---

## 3. Grandma Test Alignment

### First Sentence:
> *"Ich programmiere etwas Neues."*

### 60-Second Demo Order:
1. **0:00 - 0:10 (The Vision)**: Show Grandma the single Courier control card. Explain: Courier solves complex tasks by letting specialized agents write code, verify each other's work independently, and proceed automatically.
2. **0:10 - 0:25 (Task A Execution & Independent Verification)**: Show Task A completing. Point to the independent Verifier (not the worker) inspecting the real cryptographic digest (`575114...`) on the server. The Verifier says PASS.
3. **0:25 - 0:38 (Zero Human Relay)**: Without touching the keyboard or mouse, show Task B starting automatically (`HUMAN_RELAY_COUNT=0`). The step index advances from 0 to 1 on screen.
4. **0:38 - 0:50 (Crash Resilience / No-Replay)**: Simulate a power failure by violently killing the server (`SIGKILL`). Restart the server. Show that Task A is NOT repeated; the system resumes exactly at Task B.
5. **0:50 - 1:00 (Visible Outcome)**: Show Task B completing and being verified PASS. Both tasks reach `RECONCILED`. The full workflow goal is done.
