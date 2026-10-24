# URLAUB_ENDBERICHT · FENSTER 7 – Claude Opus · 24.10.2026

Basis `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a`. Gesamtlauf: `18 passed, 26 xfailed`, Exit 0. 0 €. Kein Push, kein Merge, kein PR, kein CI-Lauf, keine Provider-Aufrufe, keine Automation. Keine Repo-Datei geändert. Gearbeitet wurde nur in einer temporären Scratch-Worktree.

## Erledigt: 17/17
| ID | Ergebnis | Priorität |
|---|---|---|
| O7-01 | Spec ohne Schätzung blockiert die Queue (`queue_feed.py:136-142`) | P2 |
| O7-02 | Windows-Daemon: None→0.0 bei behaupteter Klasse (`windows_worker/daemon.py:359-361`) | P1 |
| O7-03 | gleicher Holder auf zwei Hosts = zwei Writer (`work_queue.py:101-103`) | P2 |
| O7-04 | LeaseStore vergibt Lease ohne Besitzer-ID (`lease.py:125-170`, `holder_ok` ungenutzt) | P1 |
| O7-05 | Feed gibt DONE nur aus State-Datei frei, ohne Journal (`queue_feed.py:125-128`) | P2 |
| O7-06 | pending-ID landet in `accepted_result_id` (`ledger_v1_bridge.py:376-379`) | P2 |
| O7-07 | Controller legt Hop B ohne sha256 an (`controller.py:347-360`) | P2 |
| O7-08 | TOCTOU: B wird FINAL über veränderte A-Bytes | P2 |
| O7-09 | Overlay öffnet erledigten Task bei at-least-once-Duplikat (`state_machine.py:19-46`) | P2 |
| O7-10 | Neustart nach 300 s dispatcht bereits gelaufenen Auftrag erneut (`intake_dispatcher.py:269-283`) | P1 |
| O7-11 | Basis: nicht gefunden. Regressionstest; rot auf #836-Head `ad50f362a` | – |
| O7-12 | Provider-Signal `TURN_ENDED outcome=DONE` setzt DONE ohne Proof (`continuity.py:225-230`) | P1 |
| O7-13 | Feed übergibt nie done_prs/open_pr_files (Basis `:77/137/139`, WQ-1b v2 `:90/179/203`) | P2 |
| O7-14 | Feed erneuert abgelehnte Mission endlos (auch WQ-1b v2) | P1 |
| O7-15 | Bridge postet abgelehnte Mission endlos = R1 (`ledger_v1_bridge.py:342-369`) | P1 |
| O7-16 | 2xx ohne ACK = DELIVERED, Ergebnis gelöscht (`windows_worker/daemon.py:202-224, 771-774`) | P1 |
| O7-17 | Gesamtliste, sha256 `2ef699e4b7b43b44c5c50707cc268227748142f2cbeeace932649c40b7c5f4ab` | – |

## Blocker: keine
Keine `_BLOCKER.md` nötig.

## Abweichungen (begründet, nicht verschwiegen)
- **O7-11:** kein strict xfail, sondern ein normaler Test. Auf der Basis gibt es den Defekt nicht; ein strict xfail würde dort XPASS melden und wäre ein falscher Befund.
- **„nicht gefunden“ an Katalog-Inputs:**
  - `cost_transparency.py` liest `estimated_cost_eur` nicht (O7-02).
  - `automation_wake_coalescing.py` hat weder Lock noch `finish_turn` (O7-11, O7-12).
  - Die Bridge-FINAL-Pfade sind korrekt geschützt (O7-05, O7-06).
  - Das Hop-B-sha256-Gate der Bridge greift (O7-07).
  - Der Controller-Idempotenzschutz greift (O7-09).
- **Zeilenangaben des Katalogs:** G1 (90/179/203) und G2 (157–176) beziehen sich auf WQ-1b v2 `a2a6dfabd`, nicht auf die Basis. Die Basis-Zeilen stehen jeweils im Ergebnis.
- Einen ersten O7-09-Entwurf habe ich verworfen, weil er Bus-Einträge zählte. Das verbietet der Bus-Vertrag ausdrücklich.

## Offen (Owner-Gates, unverändert)
- MERGE-GO: #846 MERGE_GO=NO.
- R1-Fix vor oder mit #846.
- owner_token-Rotation.
- POL-1: hängt mit O7-02 `free`/`local` zusammen.
- #836 nur mit Deadlock-Fix.
- W14 nicht angewendet; der Patch liegt nicht in der Cloud.

## Ablage
Alle Dateien liegen im Cloud-Spiegel `GrokBot/WORKKEYS/ERGEBNISSE/` (Scratchpad). Der Mac-Pfad `~/Desktop/GrokBot/…` ist aus der Cloud nicht erreichbar, deshalb übergebe ich die Dateien per Datei-Übergabe.
sha256: 5305c0760346f39add780ea6ba5989f1115ce63a50dad11b22cfc18b504421fc
