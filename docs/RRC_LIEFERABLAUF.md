# Repo Reality Check – Lieferablauf

Stand: 2026-10-14. Bestellweg: Mail an founder@couriersymphony.de. Kein Checkout auf der Website.

## Pakete (nur, was `scripts/repo_reality_check.py` liefert)
| Paket | Preis | Lieferung |
|---|---|---|
| Free | 0 € | Anzahl der Funde nach Schwere (hoch/mittel/niedrig) + Top 3 Funde im Mailtext |
| Basis | 1,99 € | `report.md` als Anhang |
| Plus | 2,99 € | `report.md` + `report.pdf` + `report.json` + 2–4 Sätze Einordnung |
| Großes Paket | 4,99 €/Monat (Einführungspreis) | wie Plus, monatlicher Re-Scan, kündbar zum Monatsende; regulärer Preis später höher |

## Ablauf
1. **Eingang**: Mail mit Paket, Zahlungsart (PayPal / Überweisung / Karte-Stripe) und öffentlicher Repo-URL. Fehlt etwas: kurz nachfragen.
2. **Prüfen**: Repo ist öffentlich auf github.com erreichbar, keine ZIPs, keine Zugangsdaten annehmen. Widerrufs-Zustimmung steht in der Mail.
3. **Bestätigen**: Antwort-Mail mit Bestätigung und Zahlungsdetails nur für die gewählte Zahlungsart (PayPal.me-Link, IBAN oder Stripe-Link). Zahlungsdetails niemals auf der Website. Free: direkt weiter mit Schritt 5.
4. **Zahlungseingang** abwarten und im Ledger notieren.
5. **Scan** (read-only):
   ```
   git clone --depth 1 https://github.com/OWNER/REPO /tmp/rrc/REPO
   python3 scripts/repo_reality_check.py /tmp/rrc/REPO /tmp/rrc/out/REPO
   ```
   Ausgabe: `report.json`, `report.md`, `report.pdf`; stdout zeigt die Zählung nach Schwere. Exit 3 = Leak-Check hat angeschlagen → nicht ausliefern, manuell prüfen.
6. **Kontrolle**: Report kurz lesen; keine Secret-Werte, keine fremden Pfade.
7. **Ausliefern** innerhalb von 48 h nach Zahlungseingang mit Vorlage `docs/templates/RRC_REPORT_MAIL_DE.md`.
8. **Aufräumen**: `/tmp/rrc/REPO` löschen; Report-Dateien nur so lange behalten, wie für Rückfragen nötig.
9. **Abo (Großes Paket)**: monatlich Schritt 5–8 wiederholen; Kündigung per Mail wirkt zum Monatsende.

## Grenzen (nicht versprechen)
Kein Reality-Score, keine Gesamtnote, keine Test-/TODO-Zählung, kein Sicherheitsaudit, keine Zertifizierung.

## Offen (nur Dennis)
PayPal.me-Link, IBAN, echter Stripe-Link; Steuerstatus (§ 19 UStG-Hinweis ist derzeit aus); Prüfung der Abo-Kündigungs-/Widerrufstexte.
