# 73-Worker Target / Performance Mode

## 1. Architektur: Background PTY Modus
Um die Last auf den WindowServer durch 73 offene `Terminal.app` Fenster zu verhindern, wird die `Terminal-Wall` auf `screen` (GNU Screen) umgestellt.
`screen` ist standardmäßig auf macOS installiert und bietet robuste Pseudo-Terminals (PTY) im Hintergrund.

**Vorteile:**
- 0% WindowServer Rendering-Overhead.
- Ein Worker läuft unabhängig vom sichtbaren Fenster sicher weiter.
- Bei Bedarf kann exakt EIN Fenster via `screen -r <slot_id>` live attached (und mit `Ctrl+A, D` wieder detached) werden.

## 2. Inventory und Supervisor
Ein zentrales JSON-Inventory (`~/Downloads/courier_work/wall/pty_inventory.json`) verwaltet die exakten 73 Slots:
- **64 Muse-Worker:** `MUSE-01` bis `MUSE-64` (Befehl bleibt strikt `muse --yolo`)
- **9 CLI-Worker:** `CLI-01` bis `CLI-09` (Befehl `HOME=/Users/user/.gemini_alt agy`)

Das Inventory erfasst für jeden Slot alle geforderten Attribute:
`slot_id`, `provider/account`, `pid`, `tty`, `task_id`, `scope`, `state`, `updated_at`, `proof_ref`, `next_action`, `blocker`.

## 3. Canary-Ramp und Messungen
Ein Canary-Run wurde erfolgreich durchgeführt:
- **Baseline:** WindowServer CPU ~38%, 265k Pages Free.
- **Canary:** 2 Slots (`MUSE-01`, `CLI-01`) via `screen -dmS` im Hintergrund gestartet.
- **Post-Canary:** Prozesse laufen stabil mit eigenen PTYs (`ttys077`, `ttys078`), ohne grafische Fenster zu erzeugen.

## 4. Einhängepunkt (Zentraler Supervisor)
Das neue Skript `scripts/mac_worker/Terminal-Wall-BACKGROUND.py` ersetzt die alten AppleScript-basierten Worker-Spawns. Es fungiert als Supervisor und erlaubt stufenweises Hochfahren (`./Terminal-Wall-BACKGROUND.py ramp <count>`), Statusüberwachung (`status`) und dediziertes Debugging (`attach <slot_id>`). 

## 5. Abnahmeprozess (Micro-Verifikation)
Nach `RESULT_READY` prüft der zentrale Supervisor nur den kleinsten deterministischen Proof aus dem Ledger (via `proof_ref`). Wenn `PASS`, wird sofort die nächste zulässige Aufgabe an den Slot übergeben. Worker bleiben im Status `WORKING` und werden nicht wegen Provider-Timeouts inaktiv geschaltet, sondern behalten ihren reservierten Zustand.

