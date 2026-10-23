# Universal Auto-Continue V1 · Claude Opus · 23.10.2026 · Checkpoint 1

Scope: Ledger, CostGate, Queue, Controller-Verträge, Replay. Basis aller Patches: `integration/v1` `d5b19f1dffe5f5478476bf090c522b38bfc7164e` (geprüft: unverändert). Alle Patches liegen nur hier als Datei vor. Es gab keine Änderung an fremden Branches, keinen Push auf fremde Branches, keinen PR und keinen Merge.

Status-Wörter: VERIFIED heißt, ich habe es selbst ausgeführt (Befehl und Ergebnis stehen in `evidence/`).

| Workkey | Owner (Writer) | Dateien | Patch | SHA256 | Rot → Grün | Regression |
|---|---|---|---|---|---|---|
| **WQ-1b** sichere Lease-Rückgewinnung | Queue (work_queue/queue_feed, L1/L3) | `courier_core/work_queue.py`, `courier_worker/queue_feed.py`, `tests/test_queue_lease_recovery.py` (neu), enthält WQ-1 (`tests/test_queue_feed_foreign_lease.py`) | `WQ-1b_lease_recovery.diff` (ersetzt WQ-1-Diff, enthält ihn) | `16b5ed56…f99e6` | VERIFIED 21 rot / 1 grün → 31 grün | VERIFIED 106 Queue/Feed/LedgerTick grün; auf #826-Head `7686b97f6` 102 grün |
| **H12** local_shell ohne Worker-Credentials | L4 Adapter | `adapters/local_shell.py`, `tests/test_local_shell_env_allowlist.py` (neu) | `H12_local_shell_env_allowlist.diff` | `fea9f5cc…cc43c` | VERIFIED 26 rot / 2 grün → 28 grün | VERIFIED 235 grün / 1 skip (alle 17 Testdateien mit `local_shell`), golden + L3 74 grün / 1 skip |
| **WIN-COST-1** `included_quota` ≠ 0 € | Cursor Windows (`windows_worker/daemon.py`) | `scripts/windows_worker/daemon.py`, `tests/test_windows_costgate_and_writer_lease.py` | `WIN-COST-1_included_quota_unknown.diff` | `cf9097a2…0d5f` | VERIFIED 2 rot → 9 grün | VERIFIED 105 grün / 7 skip |
| ~~MAC-COST~~ 0.0-Default `mac_worker/daemon.py:504` | Cursor Mac | — | **nicht erstellt** | — | bereits in #826 behoben (`estimate = task.get("estimated_cost_eur")`, kein 0.0-Default) | Doppelarbeit vermieden |

## WQ-1b — was der Patch tut
- `claim(..., announce=True)`: Der Feed verspricht ATTACH vor der Übergabe. `feed_once` schreibt **ATTACH vor ASSIGNED**. Ein abgelaufener fremder Lease ohne ATTACH beweist deshalb, dass nichts übergeben wurde, und darf übernommen werden. Ein Legacy-Claim ohne `announce` bleibt fail-closed.
- Bei ATTACH entscheidet ein injizierter `probe(item_id, attached)`. `COMPLETE_VERIFIED` setzt das Item auf DONE (kein neuer Task). `FAILED`/`CANCELLED` gibt es frei. Alles andere, kein Probe oder ein Fehler → `foreign_expired`. Der Kern lehnt `claim` mit `ATTACHED_ELSEWHERE` ab.
- `work_queue reclaim --item --actor --reason`: Der Mensch-Ausweg funktioniert nur bei abgelaufenem Lease, auch für tote `claim_once`-Kinder. Der alte Holder bekommt das Item nicht still zurück (`reclaimed_away`). Ein später RENEW/RELEASE des alten Holders wirkt beim Replay nicht mehr. Ein doppelt geschriebenes RECLAIM beendet nicht den Lease des nächsten Holders.
- Ein unabhängiger Subagent-Review fand **keinen Weg zu einem zweiten ASSIGNED**. Seine Befunde sind behoben und mit Tests belegt:
  - R1 (sticky ATTACH ließ das Ledger wachsen);
  - R3 (verlorenes Rennen brach den Pass ab);
  - R4 (`reclaimed` blieb für immer stehen);
  - R5 (eigene abgelaufene Arbeit kommt zuerst);
  - R6 (`claim_once` war nicht reclaimbar);
  - R9 (`has_open_work` zählte nicht nehmbare Items).
- Die Mutationsprobe tötet alle 5 Mutanten (siehe `evidence/WQ-1b_red_green.log`).

**Offen, Owner-Entscheidung:**
- R2: Einführung nur, wenn alle Homes zugleich aktualisiert werden. Alte Homes lesen ATTACH als `UNREADABLE`, also fail-closed, aber dann stehen sie still.
- R7: Der direkte CLI/API-`claim` übernimmt weiterhin einen nicht angekündigten fremden Lease. Das ist bewusst der Mensch-/CLI-Weg.
- R8: Ein produktiver Probe (`GET <controller>/v1/tasks/<id>`) ist nicht verdrahtet. Ohne ihn wartet jedes angehängte fremde Item auf `reclaim`. Ein zukünftiger Probe darf „unbekannt/noch nicht gepostet“ nie als CANCELLED melden.

## H12 — was der Patch tut
- Das Kind bekommt nur `INHERITED_ENV` (PATH, SYSTEMROOT, TEMP, HOME, LANG …) plus `params.env`. Provider-Keys, `GITHUB_TOKEN`, AWS-Credentials und der Controller-Token des Workers kommen nicht mehr an.
- `params.env` darf keine Credential-Namen tragen, weil Task-Parameter im Journal stehen. Außerdem darf es keine Pfad- oder Loader-Variablen überschreiben (PATH, PYTHONPATH, LD_PRELOAD, NODE_OPTIONS …).
- Grenze: Ein Befehl kann über `HOME` weiter lokale CLI-Konfigurationen lesen. local_shell bleibt deshalb in F-C1 `metered`, also kostenpflichtig, bis eine Kostenangabe vorliegt.

## WIN-COST-1 — was der Patch tut
Ein Windows-Task mit `cost_class`/`routing_decision.COST_CLASS = "included_quota"` ohne `estimated_cost_eur` lief bisher als 0,00 € und startete PowerShell. Das widerspricht der Gründerentscheidung 1 vom 23.10. Er ist jetzt UNKNOWN_COST, und PowerShell startet nicht. `free`/`local` bleiben unverändert. Ein expliziter 0,0-Wert mit `included_quota` läuft weiter. Der bestehende Test wurde entsprechend angepasst.

## Konflikte mit offenen PRs (VERIFIED per GitHub-Dateilisten)
| Datei | offene PRs | Lage |
|---|---|---|
| `courier_core/work_queue.py` | #826 (Symlink-Härtung) | WQ-1b passt auf #826 (3-way), 102 Tests grün |
| `adapters/local_shell.py` | #826 (`timeout_s` bool) | H12 passt auf #826, grün |
| `scripts/windows_worker/daemon.py` | #827, #829, #788 | keine dieser PRs ändert die Kostenzeilen; WIN-COST-1 ist ein eigener Hunk |

## Nächste Schritte
- Owner wenden die Patches an. Merges brauchen ein MERGE-GO.
- Restqueue siehe Memory-Handoff, Abschnitt 15.
