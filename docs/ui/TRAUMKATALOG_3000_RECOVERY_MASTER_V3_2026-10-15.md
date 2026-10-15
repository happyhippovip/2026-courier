# COURIER SYMPHONY – TRAUMKATALOG 3000 / RECOVERY MASTER V3
Stand: 2026-10-15 | Owner: Nutzer | Status: DOKUMENTATIONS-CHECKPOINT | SINGLE_WRITER / PLAN_ONLY

## Warum diese Datei existiert
Der Nutzer hat mehrere Stunden mit der Wiederherstellung der Prompt-Katalog-Bedienung verbracht. Diese konkrete UX ist eine persönliche und geschäftliche Kernanforderung. Ein Agent darf sie nicht durch statische Textlisten, 200er-Seiten, eine externe HTML-Seite oder eine Attrappe mit deaktivierten Pfeilen ersetzen.

## Kanonischer GitHub-Nachweis
Öffentliches Repo: happyhippovip/2026-courier
Branch: docs/chat-katalog-funktioniert-2026-10-15
Bestätigte funktionierende 17er-Referenz: docs/ui/CHAT_KATALOG_FUNKTIONSREFERENZ_2026-10-15.md (Commit 88f3d6e4d790b8352c2ae153a5cb66b48e826d36)
1–3000-Bedienvertrag: docs/ui/TRAUMKATALOG_3000_CHAT_NAVIGATION_V2_2026-10-15.md (Commit c807b8af726e83930860232db01002ad798f4688)
Diese V3-Datei ergänzt, ersetzt nicht die V1/V2-Referenzen.

## Verbindliches UX-Verhalten
1. **Direkt innerhalb einer ChatGPT-Nachricht** eine interaktive Karte mit Titel „Courier Symphony · Traumkatalog 3000“.
2. **Zurück ←**, Zähler **N / 3000**, **Weiter →** in einer Reihe. Der Wechsel muss ohne neue Chat-Nachricht erfolgen.
3. Start bei **TRAUM-0021**, wenn kein neuer Fortschrittsstand gemeldet wird. Nur bei 1/3000 dürfen die entsprechenden Pfeile deaktiviert sein.
4. Nummernsprung auf jede ganze Zahl von 1 bis 3000 und Auswahl einer der 15 Produktlinien.
5. **Kopieren** oben rechts am jeweiligen Prompt; kopiert den kompletten aktuell gewählten Volltext, bestätigt „Kopiert“.
6. Prompttext ist in einer gut lesbaren, scrollbaren Fläche; für iPhone und Desktop geeignet.
7. Status: 3.000 systematisch generierte **Entwürfe**, nicht 3.000 unabhängig verifizierte Originale; keine automatischen produktiven Workkeys.
8. **Kein Link oder HTML-Download als Ersatz** für die In-Chat-Bedienung.

## Daten- und Wiederherstellungsarchitektur
- Quellkatalog wurde im ChatGPT-Arbeitsverzeichnis als Courier_Symphony_Traumkatalog_3000.csv und .md erzeugt; zusätzlich Kopieransicht .html und MANIFEST.json.
- Diese Dateien wurden in diesem Chat am 15.10.2026 im Arbeitsverzeichnis vorgefunden; die CSV hat rund 4,6 MB, Markdown rund 4,8 MB.
- Der aktuelle GitHub-Dokumentationsstand ist **keine** verifizierte vollständige Kopie dieser Dateien. Ohne tatsächliche Datenquelle darf ein Agent nicht behaupten, 3.000 Originalvolltexte bytegenau wiederhergestellt zu haben.
- In einem neuen Chat: GitHub-Dokumentation lesen, Datenquelle beschaffen, Datensatzanzahl/IDs/Hashes validieren, interaktive Chat-Karte aufbauen und zuerst Kopieren/Navigieren testen.
- Für echte Langzeitarchivierung zusätzlich eine geprüfte, versionierte Datenkopie (CSV/Markdown/Manifest), GitHub-Commit oder freigegebener Archivspeicher, und eine zweite unabhängige lokale Kopie. Erst nach SHA256-Prüfung „gesichert“ melden.
- Keine eigenmächtige Änderung von main, kein Merge, keine Ausführung der 3000 Entwürfe.

## GrokBot / Agentenverteilung
- GrokBot kann dieses Dokument und die V1/V2-Dateien **lesen** und ein kleines Übergabepaket mit SHA256, Index, Status und Wiederherstellungsprompt vorbereiten.
- Eine einzelne kanonische Quelle und ein SINGLE_WRITER; andere Chats/Agenten lesen nur, statt parallel konkurrierende Kataloge anzulegen.
- Windows- und Mac-Grok-Desktop-Ordner: tatsächliche Pfade zunächst ermitteln und melden. Keine Pfade raten. Datenrettung, MAC_RESOURCE_PAUSED, Owner/Lease, Platz und Schreibrechte prüfen.
- Ohne separate Freigabe **keine** lokalen Dateien anlegen/überschreiben, keine Datenbankbereinigung, keine Queue-Änderungen, keine API-Kosten.
- GrokBot darf erst nach der Bestätigung aller Voraussetzungen einen kleinen, versionierten, nicht überschreibenden Export als eigenen Auftrag erhalten.

## Abnahmekriterien
A1: Karte im Chat, kein externer Browser als Ersatz.
A2: Wechsel 20→21→22 und 2999→3000 funktioniert ohne neuen Chat-Turn.
A3: 3000→2999 und 21→20 funktionieren.
A4: Direkt zu 1500 und 3000 springen.
A5: Kopieren liefert exakt den gesamten aktuell angezeigten Prompt.
A6: Quellenstatus und tatsächliche Volltextzahl sind ehrlich angegeben.
A7: Nach Neustart/Wiederherstellung gleiche ID/Prompt-Paarung und dieselben UI-Bedienelemente.
A8: Keine Ausführung, keine Datenveränderung, keine Kosten.

## Sofort kopierbarer Wiederherstellungsprompt
„Öffne meinen Courier-Symphony-Traumkatalog direkt **hier im Chat** in der 1–3000-Karussellansicht vom 15.10.2026. Lies im öffentlichen GitHub-Repo happyhippovip/2026-courier auf Branch docs/chat-katalog-funktioniert-2026-10-15 die Datei docs/ui/TRAUMKATALOG_3000_RECOVERY_MASTER_V3_2026-10-15.md und die darin genannten V1/V2-Referenzen. Starte bei Nummer 21 oder meinem zuletzt genannten Fortschritt. Echte Zurück-/Weiter-Pfeile, Nummernsprung 1–3000, Produktlinienwahl und Kopieren rechts oben über dem vollständigen Prompt, alles in derselben Chat-Nachricht. Keine HTML-Seite, keine Links statt der Ansicht, keine 20er-Grenze. Wenn Daten fehlen, sag genau welche und behaupte keine bytegenaue Wiederherstellung. Kein automatischer Agentenstart.“

## Status dieser Lieferung
Dokumentation/Bedienvertrag: GitHub-gesichert auf separatem Branch.
Original-CSV/Markdown: im Chat-Arbeitsverzeichnis vorhanden; GitHub-Upload noch nicht belegt.
Windows-Desktop: NICHT KOPIERT. Mac-Desktop: NICHT KOPIERT.
Persistenz des UI-Zustands über neue Chat-Sitzungen: NICHT garantiert.
