# V44.4 · Ledger-Integrationsabnahme · Claude Opus · 24.10.2026

Basis: `integration/v1` `81bbf224b` und #846 `2a07219c2`, beide unverändert seit V43. Pakete mit unveränderter Basis habe ich **nicht** erneut getestet.

## Neue Belege
| ID | Frage | Ergebnis | Beleg |
|---|---|---|---|
| E1 | Tritt R1 (die Bridge postet eine abgelehnte Mission endlos) schon **ohne** #846 auf? | **Nein.** Ungültige Felder lehnt die Bridge schon vor dem Claim ab. Einen unbekannten Adapter nimmt der Trunk-Controller an (201, 1 POST, `POSTED`). Erst #846 erzeugt die neue 400-Klasse `cost_blocked` für Adapter ohne `COST_CLASS`. Die Reihenfolge **R1-Fix vor oder mit #846** ist damit belegt | `evidence/probe_r1_trunk.py` (5 Specs auf 81bbf224b) |
| E2 | Gleiches Problem im **LedgerEngine**-Pfad, also in meinem eigenen Code aus #830? | **Ja, latent.** Das Kosten-Gate der Engine prüft nur `params`, das Controller-Gate auch die `COST_CLASS` des Adapters. Mit #846 bricht `ApiError 400 cost_blocked` aus `submit` aus, der Workkey bleibt CLAIMED und `next()` liefert ihn endlos erneut. Auf dem Trunk wird der Task angelegt. Das Risiko ist latent, weil es keinen produktiven Engine-Runner gibt | `evidence/probe_engine_controller_refusal.py` |
| E3 | Fix für E2 | Ein `cost_blocked` vom Controller wird wie das eigene Gate behandelt: Der Workkey wird mit `COST_BLOCKED: controller cost_blocked: …` geparkt und `CostBlocked` ausgelöst. Andere Controller-Fehler bleiben unverändert. Der Vertrag ist um einen Satz ergänzt | Branch `claude/v44-engine-controller-refusal` @ `89a66ed6b` (auf #846). Diff `V44_engine_controller_refusal.diff`, sha256 `475bc387602e6ece74bc7003867aefd8c961b4647c06b252dd8c8e8db09576b6`. Neuer Test rot → grün. Lokal 123 passed / 1 xfailed (`test_ledger_engine`, `test_host_loop`, `test_provider_events`, `test_ctrl_cost_admission`). **v1-CI [40081963656](https://github.com/happyhippovip/2026-courier/actions/runs/40081963656) success**, Ubuntu und Windows |

## Urteile je Paket (Reihenfolge R1 → #846 → F-C1b → PE-1/CDX → GUARD-1 → WIN → H12 → WQ-1b)
| Schritt | Paket | Urteil | Owner-Gate |
|---|---|---|---|
| R1 | Bridge-Fix (Mission bei 4xx auf BLOCKED setzen) | **fehlt**; Pin-Vorschlag `dbc11e2e…` (V43) | Bridge-Owner (Cursor A→B→C / L1) |
| 1 | #846 F-C1 + Folgepatch | Kandidat; CI 7/7 | L2-Abnahme + MERGE-GO + owner_token-Gate; **vor oder mit R1** |
| 1a | V44-Engine-Fix (neu, mein Code) | bereit zur Abnahme, CI grün | L1-Review; gehört zu #846 (ohne #846 wird der Pfad nie ausgelöst, er ist dann harmlos) |
| 2 | F-C1b | bereit (CI grün auf #846-Basis) | L3 |
| 3 | PE-1 / CDX-COST-1 | bereit (CI grün) | L3 / L1 (#810-Reihenfolge) |
| 4 | GUARD-1 v3 | bereit (CI grün) | Codex/Grok 57,50 |
| 5 | WIN-COST-1 v3 | bereit (CI grün) | Cursor Windows (#788-Reihenfolge) |
| 6 | H12 v3 | **BLOCKED**: instabile Windows-Daemon-Tests | Windows-Test-Owner (#843) + grüner Lauf |
| 7 | WQ-1b v2 | bereit (CI grün); parkt erst nach dem R1-Fix wirksam | L1/L3 + Rollout auf allen Homes |

Kein Paket ist unabhängig abgenommen. Es gibt keinen Merge, keine fremde Lease und keinen fremden Produktcode: E3 betrifft `courier_runtime/ledger_engine.py` und liegt in meiner eigenen Spur aus #830.
