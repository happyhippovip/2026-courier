# Handover-Status (öffentlich, ohne Geheimnisse)
Stand: 2026-09-21

## Arbeitsweise
- Muse ist Haupt-Worker. ChatGPT ist Manager und legt genau einen nächsten Schritt fest. Claude ist Code-Chef für Notfälle und komplexe Arbeit (vor allem Cannon).
- Ein Schritt zur Zeit, keine parallelen Live-Änderungen.
- AWS-Konsolenänderungen macht der Nutzer selbst am MacBook, weil Muse den offenen Browser-Tab nicht übernehmen kann.
- Bei Unsicherheit FAIL CLOSED. Keine Bestätigung ohne sichtbaren Beleg.
- UNKNOWN-Regel: Ist unklar, ob ein Task abgeschickt wurde: STOP, keine Wiederholung, erst Reconciliation.

## Cloud-Stand (AWS, Region Frankfurt)
- Zugang zur Linux-Instanz über EC2 Instance Connect: getestet, funktioniert (2026-09-21).
- Zugang über SSM Session Manager: Sitzung im Browser geöffnet (2026-09-21). Eine IAM-Rolle mit der AWS-verwalteten SSM-Richtlinie ist an die Instanz angehängt.
- SSH ist nur von einer festen Adresse und von der AWS-EIC-Prefix-List erlaubt, nichts ist für die ganze Welt offen.
- Ziel: SSM ist der normale Admin-Zugang, EIC nur Fallback. Keine langlebigen AWS-Access-Keys auf den Rechnern.
- Offen: Systemupdates und Neustart der Instanz, als eigener Schritt.

## Nächste Schritte (Reihenfolge)
1. Lokale Cannon-Queue (Dauerlauf) fertigstellen. Bestehende Datei nicht verändern oder zerstören.
2. Mac testen, 3. Windows testen
4. Machine A (kleiner Dauer-Controller), 5. Machine B (größerer Worker, nur bei Bedarf)
6. Recovery Package, 7. Run Lineage, 8. Workflow Versioning, 9. Context Packs
10. Cost Guard, 11. Observability, 12. API/Policy
13. Website, 14. Funding Evidence, 15. skalieren

## Rettungspunkte (nicht überschreiben)
- Tag courier-1-10-working-2026-09-19
- Branch known-good/1-10-working-2026-09-19
- Commit 6ca172ac

## Nicht ins Repo
Account-IDs, IPs, Keys, Tokens, Passwörter, private Infrastrukturdetails, interne Kostenmodelle, vertrauliche Partnergespräche. Nicht behaupten, AWS- oder Amazon-Partner zu sein, solange kein formeller Status vorliegt.
