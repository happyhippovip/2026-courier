# MASTERPLAN COURIER SYMPHONY
Stand: 23.09.2026 · Version 2 · Verantwortlich für Freigaben: Dennis

> Leitsatz: Vision groß, Umsetzung in Stufen. Eine Stufe ist erst fertig, wenn ihr Beleg vorliegt.
> Kein Beleg = kein PASS. Lob oder Selbstauskünfte eines Modells sind keine Belege.

---

## 1. Nordstern
**Ein Kunde drückt einen Knopf. Courier arbeitet ein Projekt ohne ein einziges "Proceed" bis "fertig" ab und belegt jeden Schritt.**

Messgröße (täglich): **belegte erledigte Aufgaben ohne menschlichen Eingriff** – plus Anzahl Doppel-Ausführungen (Ziel 0) und verlorene Ergebnisse (Ziel 0).

## 2. Der Durchbruch HEUTE (Definition)
Heute gilt als Durchbruch, wenn alle vier Punkte belegt sind:
1. Der Endlos-Lauf auf dem Mac (gestartet 23.09.2026 18:07) hat **mindestens 20 Aufgaben ohne Eingriff** erledigt – ohne Hänger, ohne /clear.
2. Jedes Ergebnis ist an genau einen Commit gebunden (result_id == voller Commit-Hash), DUPLICATE_EXECUTIONS = 0, LOST_RESULTS = 0.
3. Der 5er-Lauf der Cannon V1 ist grün.
4. Der Stand ist als **Cannon V1** gesichert (Tag + Bundle). Push auf GitHub: Entscheidung Dennis.

Alles andere ist heute zweitrangig.

## 3. Stopp-Liste (ab sofort NICHT mehr)
- 12–14 Fenster von Hand füttern → stattdessen arbeitet die Cannon.
- Muse mit `--yolo` oder Agenten mit abgeschalteter Sandbox → Cannon nutzt `--disable-approval` mit Sandbox (nie Proceed, trotzdem abgesichert).
- Neue Accounts, um Limits zu umgehen.
- Neue Features, bevor Cannon V1 eingefroren ist.
- Worker-Branches mergen, bevor Cannon V1 eingefroren ist.
- Stundenlange Werkzeug-Reparaturen (z.B. Antigravity) während der Kernarbeit → Notlösung reicht.
- AWS und bereits geprüfte Abos erneut durchgehen (nur bei neuer Frist/Kostenwarnung).

## 4. Rollen
| Wer | Aufgabe |
|---|---|
| **Cannon + Muse** | Die eigentliche Arbeit: Aufgabe für Aufgabe, belegt, ohne Proceed. |
| **Google-Worker** | Nur solange die Abos laufen: Audits, Gegenprüfungen, Vorarbeit. Kein Merge ohne Prüfung. |
| **Chief (ChatGPT)** | Jobcenter, Einstiegsgeld/LES, Businessplan, Förderpaket, Texte. |
| **Claude** | Belege prüfen, Master-Prompts schreiben, Freeze-/Merge-Entscheidungsvorlagen. |
| **Dennis** | Freigaben: Merge, Push, Geld, Accounts, Veröffentlichung. Sonst möglichst wenig tippen (Regel Nr. 1). |

## 5. Stufen bis zum Endstadium

### Stufe 1 – Cannon V1 fertig und einfrieren (JETZT)
- 1.1 pre-yolo-patch-Referenz klären. BELEGT: `pre-yolo-patch(-v2)` = 49150d3f, `yolo-patch-applied-v2` = e98ce2cc. Offen: welche ist offizielle Basis.
- 1.2 Live-Text-Fehler untersuchen (UNKNOWN: welcher genau).
- 1.3 Tests stabil grün auf Mac und Windows.
- 1.4 5er-Lauf + Auswertung Endlos-Lauf.
- 1.5 Einfrieren: Tag `courier-cannon-v1`, Bundle-Sicherung, GitHub-Push (Dennis).
- **Abnahme:** Mac und Windows je ein belegter Lauf mit result_id == Commit, 0 Duplikate, 0 verlorene Ergebnisse, Notaus unter 15 Sekunden.

### Stufe 2 – Ledger fertig
- Der Ledger ist die einzige Wahrheit: welche Aufgabe, welcher Worker, welches Ergebnis, welcher Beleg, welcher Verbrauch (Credits).
- Warum vor V2: Ohne fertigen Ledger kann Courier weder sinnvoll verteilen noch Credits messen.
- **Abnahme:** Jede Aufgabe eines Laufs ist im Ledger mit Worker, Ergebnis, Beleg und Verbrauch nachvollziehbar; Absturz- und Doppel-Tests grün.

### Stufe 3 – Cannon V2 „Dirigent"
- Courier startet und befüllt N Fenster/Worker automatisch mit Planer → Arbeiter → Prüfer (heute noch manuell per Prompt 1-2-3).
- Jede Aufgabe genau einmal reserviert (Prinzip im Zyklus bereits erprobt).
- Übersicht aller Fenster: wer macht gerade was.
- Kontingent-Wächter: erkennt "quota reached" und gibt die Aufgabe an einen anderen regulären Worker weiter.
- Stoppt von selbst, wenn das Projekt fertig ist.
- **Abnahme:** Ein Testprojekt wird von mindestens 3 Workern ohne Doppelarbeit bis "fertig" gebracht, alles im Ledger belegt.

### Stufe 4 – Kundenoberfläche
- Ein-Klick-Start ohne Terminal und ohne Localhost, Mac und Windows.
- Kunden sehen Fortschritt, Ergebnisse und gespeicherte, bereinigte Logs (Schlüssel/Tokens entfernt – Funktion existiert bereits im YOLO-Profil).
- Optional: per /clear geleerte Sitzungen speichern (End-Baustein).
- **Abnahme:** Ein Testkunde startet per Doppelklick und sieht nur Fortschritt, Logs, Ergebnisse.

### Stufe 5 – Community
- Login mit X/Facebook, gemütlicher Chat im Stil von ICQ damals, Vorführ-Ansicht mit Live-Logs.
- Vorher klären: Datenschutz (DSGVO), Regeln von X/Meta für Login-Apps, laufende Kosten. Entscheidung Dennis.
- **Abnahme:** Geschlossene Testgruppe loggt sich ein, chattet, sieht Live-Logs; Datenschutz-Check dokumentiert.

## 6. Endstadium (Definition "fertig")
Courier Symphony ist fertig, wenn ein fremder Kunde ohne Hilfe per Knopf ein Projekt startet, Courier es mit mehreren Workern ohne Proceed bis "fertig" bringt, jeder Schritt im Ledger belegt ist, der Kunde nur Fortschritt/Logs/Ergebnisse sieht und die Community-Oberfläche läuft.

## 7. Risiken und Gegenmaßnahmen
| Risiko | Gegenmaßnahme |
|---|---|
| Agenten ohne Sandbox im Original-Repo überschreiben Arbeit | Nur Cannon mit Sandbox; Worker nur in eigenen Kopien/Branches; Sicherungs-Bundles vorhanden |
| Viele Accounts zum Umgehen von Limits (Nutzungsbedingungen) | Keine neuen Accounts; Plan hängt nicht davon ab |
| Unsignierte Antigravity-Version 2.16 | Bewusste Entscheidung Dennis; nur Notlösung, nicht Produktbestandteil |
| Öffentliches GitHub-Repo | Keine Schlüssel, Zugangsdaten, Kunden- oder Förderdaten ins Repo |
| Tests beenden fremde Prozesse (Antigravity-Abstürze) | Prozess-Kill-Regel in jedem Prompt |
| Überlastung Dennis | Regel Nr. 1: ein Schritt, ein Befehl, große Master-Prompts, Cannon statt Handarbeit |

## 8. Rhythmus
- **Täglich:** eine Status-Zeile vom Mac/Windows an Claude, genau eine Entscheidung durch Dennis.
- **Pro Stufe:** Abnahme mit Beleg, dann Freeze, dann nächste Stufe.

## 9. Kontext-Block für neue Chats (zum Einfügen)
```
Projekt Courier Symphony. Regeln: Kein Beleg = kein PASS; jede Aussage BELEGT/BEHAUPTET/VERMUTET/UNKNOWN;
vor Code-Aussagen Branch+SHA nennen oder UNKNOWN. Geld, Veröffentlichung, Zugangsdaten, Merge/Push entscheidet nur Dennis.
Regel Nr. 1: Dennis will wenig tippen – ein nächster Schritt, Ausführender genannt, fertige Prompts/Befehle.
Aktuelle Stufe laut MASTERPLAN: Stufe 1 (Cannon V1 einfrieren). Reihenfolge: Cannon V1 -> Ledger -> Cannon V2 Dirigent -> Kundenoberfläche -> Community.
Mac: Cannon-Endlos-Lauf in ~/Downloads/courier_cannon_endlos (Ziel-Repo ~/Downloads/courier_cannon_ziel).
Windows: Cannon-Port in C:\Users\lol\2026-workspace\courier-cannon-win; Antigravity nur über Chrome/localhost.
AWS und Abos sind erledigt – nicht erneut prüfen.
```
