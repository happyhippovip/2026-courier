# CLI5 Visible Proof — Tonight's Empirical Product Demonstration

- **WORKER_ID**: MAC-GOOGLE-005
- **HOST**: MAC_ONLY (Darwin 25.6.0 x86_64, MacBook-Pro-von-user.local)
- **PROVIDER**: GOOGLE_ANTIGRAVITY
- **MODE**: READ_ONLY_PRODUCT_PREP
- **CANONICAL_HEAD**: `332a42f9edcf1de1535870592da34a7961880991`
- **CANDIDATE_SHA**: `4c1e24ccc522042af826bc4c2b595daf85d097f9` (`origin/candidate-b-1`)
- **FILES_CHANGED**: 0 (Canonical repository remains untouched; single-writer law preserved)
- **EVIDENCE_SOURCE**: Physical Darwin runtime, real server state files, live verifier logs, and hermetic physical canary on port 8081.

---

## 1. Grandma First Sentence & Plain-Language Translation

### Grandma First Sentence (Verbatim)
> **„Ich programmiere etwas Neues.“**

### Oma-Version (Alltagssprache, keine Fachbegriffe)
„Ich programmiere etwas Neues. Der Computer hat seine erste Aufgabe gemacht, sie ganz allein kontrolliert und sofort ohne Hilfe die zweite Aufgabe angefangen. Niemand musste dazwischentreten.“

### Mama-Version (Klar, transparent, ohne Technikjargon)
„Unser neues System hat eigenständig einen zweistufigen Auftrag entgegengenommen, den ersten Schritt ausgeführt, das Ergebnis unabhängig überprüft und ohne jegliche menschliche Weiterleitung sofort den zweiten Schritt gestartet. Außerhalb von echten Rückfragen ist der Mensch komplett befreit.“

---

## 2. Core Visible Proof Contract (Empirical Runtime Facts Only)

All metrics, hashes, and process records below are drawn directly from inspected on-disk state files, real network exchanges on port 8081, and active processes on this physical Mac host. No synthetic passes or estimated timestamps.

```ini
AUFTRAG=goal-canary-01 (Zweistufige Arbeitskette: task-canary-A -> task-canary-B)
A_ERLEDIGT=YES (task-canary-A, worker_id=MAC-01, dispatch_id=dispatch-28864ad081fb47569bcf1f64a543ab76, status=RECONCILED)
A_GEPRUEFT=YES (verifier_id=VERIFIER-01, verdict=PASS, server-side artifact re-hashed and confirmed)
B_AUTOMATISCH_GESTARTET=YES (goal-canary-01 current_step_index advanced 0->1, task-canary-B auto-claimed by MAC-01)
B_ERLEDIGT=YES (task-canary-B, worker_id=MAC-01, dispatch_id=dispatch-4ac4c1fe4f5e4922907862cb5b154244, status=RECONCILED)
A_EXECUTION_COUNT=1 (attempt_id=task-canary-A:attempt:1, zero retry churn)
HUMAN_RELAY_COUNT=0 (Zero manual interventions, zero resume HTTP calls, zero manual prompt refills)
CANDIDATE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
BEWEIS=HERMETIC_PHYSICAL_RUN_PORT_8081_CANDIDATE_B_1; Server PID 98844 / 98845; Artifact A art-6e11306e6144cb9f2b65eac615b461202ebb05e424416a400f55f3aeb4c40a25 (SHA 575114...); Artifact B art-3507749063c58a5e281b24e3d388fe684edfa488c1dce0b7659b5e9f7cef2a67 (SHA 3297be...)
```

---

## 3. Physical Evidence Registry

### A. Artifact Cryptographic Identity & Server Store
- **Task A Output Path**: `canary_A.txt`
  - Byte Sequence: `COURIER-A2B-A` (13 bytes)
  - Computed SHA-256: `575114332fb4ccd482dd9ca60dbaccc15b579afeb372f0c92b6f7eefe219049b`
  - Server Artifact ID: `art-6e11306e6144cb9f2b65eac615b461202ebb05e424416a400f55f3aeb4c40a25`
  - Independent Verifier Verdict: `PASS`
- **Task B Output Path**: `canary_B.txt`
  - Byte Sequence: `COURIER-A2B-B` (13 bytes)
  - Computed SHA-256: `3297be4a21a5b49786920ed3340c4f0dafee54d65e3d863e68d2799e05fc14ed`
  - Server Artifact ID: `art-3507749063c58a5e281b24e3d388fe684edfa488c1dce0b7659b5e9f7cef2a67`
  - Independent Verifier Verdict: `PASS`

### B. Persistent State Files on Physical Disk
1. **Canary Central State**:
   - Location: `/Users/user/.gemini_alt/.gemini/antigravity-cli/brain/f0e8ab57-ee0d-434c-80ed-06b3f3253fc4/scratch/canary_physical_run/state/central_state.json`
   - Content Proof:
     - `tasks.task-canary-A.status`: `"RECONCILED"`
     - `tasks.task-canary-B.status`: `"RECONCILED"`
     - `goals.goal-canary-01.current_step_index`: `1`
     - `tasks.task-canary-A.result.artifacts[0].sha256`: `575114...`
     - `tasks.task-canary-B.result.artifacts[0].sha256`: `3297be...`

### C. Deterministic Restart / No-Replay Evidence
- **Pre-Crash Execution**: Task A completed and reconciled; Task B dispatched to MAC-01.
- **Crash Injection**: Server PID `98844` killed with violent `SIGKILL`.
- **Post-Crash Restart**: Server restarted under PID `98845` loading persistent `central_state.json`.
- **Identity Preservation**: Pre-crash state matches post-crash state byte-for-byte.
- **No-Replay Proof**: Subsequent worker claim returned `WORKER_BUSY` (Task B already dispatched); Task A was strictly never replayed.

### D. Production Process Isolation
- **Production Server (Port 8080)**: PID `69407` (PPID 1), RSS 10.2 MB, CPU 0.0% — undisturbed.
- **Production Verifier**: PID `42002` — undisturbed.
- **Production Mac Worker Daemon**: PID `46250` — undisturbed.
- **34 Background Muse processes**: Active and running undisturbed.

---

## 4. The 60-Second Demo Order (Tonight's Presentation Script)

| Time | Stage | Product View (Grandma / Mama) | Technical Drawer (Inspectable Proof) |
| :--- | :--- | :--- | :--- |
| **00s - 10s** | **Auftrag** | **Start mit einem Satz**: <br>„*Ich programmiere etwas Neues.*“<br>Großes 6-Zustände-Dashboard: <br>`AUFTRAG: 1` · `ARBEITET: 0` · `GEPRÜFT: 0` · `BRAUCHT DICH: 0` · `FERTIG: 0` · `ALS NÄCHSTES: 1` | `GET /goals/goal-canary-01`<br>Zeigt saubere `central_state.json` mit zweistufigem Workflow: <br>`task-canary-A` (Schritt 1) gefolgt von `task-canary-B` (Schritt 2). |
| **10s - 25s** | **Arbeitet & Erledigt** | **Zustand wechselt auf ARBEITET**: <br>„*Schritt 1 wird ausgeführt.*“<br>Keine Buttons, kein Klicken. Der Computer nimmt die Arbeit auf. | Worker-Terminal / REST Log:<br>`POST /tasks/claim` → Worker `MAC-01` erhält `task-canary-A`.<br>`POST /artifacts` lädt Bytes hoch (`art-6e1130...`).<br>`POST /tasks/result` mit SHA `575114...`. Status: `RESULT_RECEIVED`. |
| **25s - 35s** | **Geprüft** | **Zustand wechselt auf GEPRÜFT**: <br>„*Schritt 1 eigenständig kontrolliert.*“<br>Der Computer vertraut sich nicht blind selbst, sondern prüft server-seitige Bytes nach. | Verifier-Terminal (`VERIFIER-01`):<br>Lädt `art-6e1130...` vom Server, berechnet SHA-256 neu (`575114...`), gleicht mit `expected_sha256` ab.<br>`POST /tasks/verify` → `verdict: PASS`. Server quittiert `RECONCILED`. |
| **35s - 50s** | **Autonomer Start von B** | **Der magische Moment (ALS NÄCHSTES wird aktiv)**:<br>„*Schritt 2 startet vollautomatisch.*“<br>**HUMAN_RELAY_COUNT = 0**.<br>Niemand drückt Enter, niemand tippt neue Prompts ein. | Server State & Worker Log:<br>Server rückt `current_step_index` von 0 auf 1 vor.<br>`task-canary-B` wird vollautomatisch von `MAC-01` geclaimt.<br>Worker `MAC-01` beginnt unterbrechungsfrei die Bearbeitung von Schritt 2. |
| **50s - 60s** | **Fertig & Beweis** | **Abschluss & Ruhe**: <br>`FERTIG: Auftrag abgeschlossen.`<br>`BRAUCHT DICH: 0`<br>Oma-Fazit: „*Alles von alleine erledigt, ich musste nichts tun.*“ | Beweiskarte (Layer B):<br>Zeigt Rohdaten-Hashes (`575114...` und `3297be...`), `A_EXECUTION_COUNT: 1`, `HUMAN_RELAY_COUNT: 0`.<br>Durabilitäts-Nachweis: Crash/Restart-Sicherheit unter `SIGKILL` ohne Replay. |

---

## 5. Explicit Verification Boundary Note

> [!IMPORTANT]
> **Canary Verification Scope Disclosure**:
> Die Verifikation (`A_GEPRUEFT`) im Canary basiert auf einem kryptografisch exakten `expected_sha256`-Hash-Abgleich deterministischer Dateiinhalte (`COURIER-A2B-A` und `COURIER-A2B-B`) über den Server-Artifact-Store (`POST /artifacts`). Dies beweist die fehlerfreie mechanische Verkettung (Claim -> Upload -> Result -> Independent Verifier Hash Check -> State Transition -> Auto-Dispatch Next -> Crash Survival without Replay), stellt jedoch **keinen semantischen Verifier für beliebige Freitext-Aufgaben** dar. Diese Grenze wird transparent kommuniziert.
