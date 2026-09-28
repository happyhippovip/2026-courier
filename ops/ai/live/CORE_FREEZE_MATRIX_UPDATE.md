# Core Freeze Matrix - Update BATCH 7

Dieses Dokument aktualisiert die Core Freeze Matrix mit den neuesten Binding-, Isolation-, Restart- und Proof-Card-Ergebnissen.

## 1. Freeze Status der Subsysteme

| Subsystem | Freeze Status | Lock Mechanism | Verification Proof |
| :--- | :--- | :--- | :--- |
| **Runtime Binding** | **FROZEN** | `binding.py` Fingerprint Slots | Preflight Evidence ID |
| **Directory Isolation** | **FROZEN** | `isolation.py` | State/Log/Artifact Dirs |
| **Process Ownership** | **FROZEN** | `process_ownership.py` | Resource Evidence / Logs |
| **Resource Admission** | **FROZEN** | `resource_admission.py` (MAX_HEAVY_JOBS=1) | Admission Logs |
| **Restart & Recovery** | **FROZEN** | `RESTART_NEGATIVE_MATRIX.md` | Restart Evidence Card |
| **Evidence / Proofs** | **FROZEN** | `PROOF_CARDS.md` Template | Full Proof Card Manifest |

## 2. Invariants & Guardrails
- Keine physischen Änderungen der PIDs (`os.kill` verboten).
- `FINAL_SHA`-Werte bleiben bis zum definitiven Live-Run auf Placeholder (`FINAL_SHA_PLACEHOLDER_*`).
- `A execution count` ist strikt auf `1` limitiert; jegliche Abweichung bricht den Core Freeze.
- Jegliche Human Intervention während der Run-Phasen führt zum Invalidieren der Proof Card.

## 3. Zertifizierungs-Pfad
Jeder Run muss nach Beendigung exakt eine **Proof Card** generieren, die alle 9 Felder (Source, Build, Runtime, Covered Surface, Evidence IDs, Human Intervention, UNKNOWN, Restart Evidence, Resource Evidence) lückenlos ausfüllt. Erst wenn diese Proof Card validiert ist, gilt das System als im "Core Freeze" befindlich und erfolgreich evaluiert.
