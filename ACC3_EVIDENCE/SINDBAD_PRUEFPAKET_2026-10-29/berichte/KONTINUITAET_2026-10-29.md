# KONTINUITÄT – Pflichtfelder je Agentenfile · 29.10.2026 19:10 MEZ (read-only geprüft, Agenten tragen fehlende Felder selbst nach)
Pflicht: offene+erledigte Keys · Belege · Owner · Lease · BLOCKED/GO · letzter Checkpoint · nächster freigegebener Key

| Agent | Keys | ERLEDIGT | Belege sha OK | letzter gültiger Beleg | nächster OFFEN | fehlende Felder | mtime |
|---|---|---|---|---|---|---|---|
| PRUEFER | 14 | 5 | 6/9 | WK-PRUEFER-009 GESAMTURTEIL.md fb573edc | WK-PRUEFER-003 | Owner, Lease, Checkpoint | 18:56 |
| DOKU | 14 | 11 | 9/12 | WK-DOKU-012 GIT_REFS.md 398096f4 | WK-DOKU-013 | Owner, Lease, Checkpoint | 18:57 |
| PRODUKT | 14 | 8 | 8/8 | WK-PRODUKT-008 YOUTUBE_AUTH_CHECK_PFAD.md bb0ff2d0 | WK-PRODUKT-011 | Owner, Lease, Checkpoint | 18:11 |
| UMSATZ | 14 | 9 | 9/9 | WK-UMSATZ-011 FEEDBACK_BOGEN.md 5d6fee11 | – (Rest BLOCKIERT_GO) | Owner, Lease, Checkpoint, nächster freigegebener Key (keiner OFFEN) | 18:56 |
| WEBSITE | 12 | 8 | 8/8 | WK-WEBSITE-012 IMPRESSUM_FRAGEN.md e378170e | – (Rest BLOCKIERT_GO) | Owner, Lease, Checkpoint, nächster freigegebener Key (keiner OFFEN) | 18:56 |
| INTEGRATOR | 14 | 8 | 12/12 | WK-INTEGRATOR-012 SHA256SUMS_012.txt 412c16ed | WK-INTEGRATOR-011 | Lease, Checkpoint | 18:57 |
| INTEGRATION | 11 | 4 | 8/8 | WK-INTEGRATION-009 LUECKE_01_009_TEST.log 519f87ab | WK-INTEGRATION-011 | Owner, Lease, Checkpoint | 18:54 |
| KATALOG | 8 | 0 | 0/0 | None | WK-KATALOG-001 | Owner, Lease, Checkpoint | 18:00 |
| DATENRETTUNG | 10 | 6 | 7/8 | WK-DATENRETTUNG-010 BACKUP_KANDIDATEN.md 772380bc | – (Rest BLOCKIERT_GO) | Owner, Lease, Checkpoint, nächster freigegebener Key (keiner OFFEN) | 18:56 |
| SYMPHONY | 12 | 6 | 7/7 | WK-SYMPHONY-007 STOP_GATES.md 1cb0c396 | WK-SYMPHONY-003 | Owner, Lease, Checkpoint | 18:56 |
| MAC_WAND | 10 | 8 | 8/8 | WK-MAC_WAND-010 LAUNCHD_ZUORDNUNG.md 1c588431 | – (Rest BLOCKIERT_GO) | Owner, Lease, Checkpoint, nächster freigegebener Key (keiner OFFEN) | 18:56 |
| WINDOWS_WAND | 10 | 8 | 8/8 | WK-WINDOWS_WAND-010 RC_0046_TESTPLAN.md 2c532793 | – (Rest BLOCKIERT_GO) | Owner, Lease, Checkpoint, nächster freigegebener Key (keiner OFFEN) | 18:56 |

BLOCKED-Gründe:
- PRUEFER: WK-PRUEFER-010: BLOCKIERT_GO (Push-GO von Dennis)
- DOKU: WK-DOKU-010: BLOCKIERT_GO (Push-GO von Dennis)
- PRODUKT: WK-PRODUKT-009: BLOCKIERT_GO (Push-GO von Dennis) ; WK-PRODUKT-010: BLOCKIERT_GO (GO + Login durch Dennis)
- UMSATZ: WK-UMSATZ-008: BLOCKIERT_GO (Entscheidung Dennis) ; WK-UMSATZ-009: BLOCKIERT_GO (GO Dennis) ; WK-UMSATZ-012: BLOCKIERT_GO (nach WK-UMSATZ-008) ; WK-UMSATZ-013: BLOCKIERT_GO (Recovery-Freigaben Dennis) ; WK-UMSATZ-014: BLOCKIERT_GO (Entscheidungsblatt Punkt 4)
- WEBSITE: WK-WEBSITE-007: BLOCKIERT_GO (Entscheidung Dennis) ; WK-WEBSITE-008: BLOCKIERT_GO (Dennis) ; WK-WEBSITE-009: BLOCKIERT_GO (Push-GO Dennis) ; WK-WEBSITE-010: BLOCKIERT_GO (wartet auf WK-007)
- INTEGRATOR: WK-INTEGRATOR-008: BLOCKIERT_GO (Push-GO Dennis) ; WK-INTEGRATOR-014: BLOCKIERT_GO (Kolibri gesperrt)
- INTEGRATION: WK-INTEGRATION-004: BLOCKIERT (Akzeptanz 'pytest passed' nicht erfüllt: Gate 13/13 + tests ; WK-INTEGRATION-005: BLOCKIERT (Akzeptanz 'kein gemeinsamer Diff' nicht erfüllt: 3 gemeinsa ; WK-INTEGRATION-007: BLOCKIERT_GO (GO Dennis) ; WK-INTEGRATION-008: BLOCKIE
- KATALOG: WK-KATALOG-008: BLOCKIERT_GO (GO Dennis)
- DATENRETTUNG: WK-DATENRETTUNG-002: BLOCKIERT (Mama-Briefe tabu, Mac offline) ; WK-DATENRETTUNG-003: BLOCKIERT (UNKNOWN, keine Quelle) ; WK-DATENRETTUNG-007: BLOCKIERT_GO (GO Aufräumen Dennis) ; WK-DATENRETTUNG-008: BLOCKIERT_GO (Eigenes GO Dennis)
- SYMPHONY: WK-SYMPHONY-008: BLOCKIERT_GO (Entscheidung Dennis) ; WK-SYMPHONY-012: BLOCKIERT_GO (Löschen nur mit Dennis' GO)
- MAC_WAND: WK-MAC_WAND-007: BLOCKIERT_GO (GO Dennis) ; WK-MAC_WAND-008: BLOCKIERT_GO (GO Dennis)
- WINDOWS_WAND: WK-WINDOWS_WAND-007: BLOCKIERT_GO (GO Dennis) ; WK-WINDOWS_WAND-008: BLOCKIERT_GO (GO Dennis)

Hash-Abweichungen (Datei nach Beleg geändert, Beleg muss neu): PRUEFER INTEGRATOR_0060.md, CP2_PRUEFUNG.md, CP5_PRUEFUNG.md · DOKU LAUFEND.md, GATE_0027.md, SELF_REPORTED_VERALTET.md · DATENRETTUNG BACKUP_KANDIDATEN.md
Dateirechte: alle Agentenfiles gehören User box, Rechte rw-r--r--, und alle Agenten laufen als box. Isolation und Single Writer gelten nur per Konvention (siehe LEASES.md). Lease-Dateien gab es vorher keine.
Agenten-Zugriff (eigenes File nach 18:00 selbst geändert): 11/12. Ausnahme ist KATALOG (seit 18:00 unverändert, HOLD).
Persistenz: 12/12 Agentenfiles sind vorhanden und lesbar. Den Test in einer frischen Shell habe ich exemplarisch an MAC_WAND WK-001 gemacht, siehe Abschlussbericht.
Secret-Scan (nur Namen, keine Werte): Treffer der Muster token/sk-/api_key in INTEGRATOR.md, ERGEBNISSE/INTEGRATOR/{RESOLVE_TOKEN.md, PYTEST_0060_a209b3fe.log, PYTEST_0060_9afe8706.log, INTEGRATIONSTEST.log}, ERGEBNISSE/INTEGRATION/{LUECKE_01.diff, raw_logs/patch_full.log, raw_logs/pr527_files.json, raw_logs/pr528_files.json}. Wahrscheinlich Test-Fixtures, nicht verifiziert. Für Sindbad ausgeschlossen. In den übrigen 11 Agentenfiles keine Treffer.

