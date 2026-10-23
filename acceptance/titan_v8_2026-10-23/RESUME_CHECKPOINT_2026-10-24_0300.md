# RESUME_CHECKPOINT 2026-10-24 03:00 (Europe/Berlin) · Claude Opus

**Wiederaufnahme-Mechanismus (VERIFIED):** eine einmalige Erinnerung in **dieser** Claude-Code-Sitzung (`send_later`, Trigger `trig_01LpPtEx628tcpztAwvCPaeN`) am **2026-10-24 01:00 UTC = 03:00 MESZ**. Sie ist im bestehenden Abo enthalten, verursacht keine PAYG-Kosten und läuft einmalig ohne Wiederholung. Sie läuft nur, wenn die Sitzung dann noch existiert. Andernfalls startet man manuell mit diesem Dokument.

## Stand bei Erstellung
| Was | Wert |
|---|---|
| Trunk `integration/v1` | `d5b19f1df` |
| PR #830 | `claude/ledger-engine-v1` @ `8932d287f` (Draft, CI nach Push noch nicht geprüft) |
| Acceptance-Branch | `claude/ledger-autonomy-acceptance-2026-10-23`, Ordner `acceptance/titan_v8_2026-10-23/` |
| Memory | `happyhippovip/2026-project-memory`, Handoff-Abschnitt 17 |
| Uncommittete Änderungen | keine im Repo; Scratch-Worktrees gehen beim Container-Ende verloren, alle Patches liegen als Diff auf dem Branch |

## Restqueue (in dieser Reihenfolge, nur ohne fremde Lease)
1. #830-CI auf `8932d287f` prüfen; bei Rot die Ursache in den eigenen Dateien beheben.
2. A03-Matrix mit den v2-Patches gegen die dann aktuellen Heads neu fahren (`matrix.sh`-Logik: `git apply --3way` + eigene Tests).
3. Kombinierte Volllauf-Probe: Trunk + F-C1 + WQ-1b v2 + H12 v2 + WIN-COST-1 v2 + VC-1 + CDX-COST-1 + PE-1 (ohne POL-1), ein schwerer Job.
4. Crash-Punkte in `queue_feed` (FINAL_DONE→release, release→next claim, claim→assign) als reguläre Tests in den WQ-1b-Patch aufnehmen.
5. Unabhängiges Subagenten-Review von H12 v2 (Fehlalarme und Umgehungen der Provider-CLI-Sperre) und WIN-COST-1 v2.
6. F-C1: Prüfung zusätzlich zur Lease-Zeit (`adapter_runner` vor `local_shell.run`), nur als Vorschlag mit Tests.
7. Abschluss: Evidence-Matrix aktualisieren, Memory-Abschnitt schreiben, ein Bericht.

## Nicht tun
Kein Merge; keine fremden Branches; kein Provider-Aufruf; keine neue Automation über diese eine Erinnerung hinaus; POL-1 nicht anwenden ohne Entscheidung von Dennis; owner_token-Werte nie kopieren.
