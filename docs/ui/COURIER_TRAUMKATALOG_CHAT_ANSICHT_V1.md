# Courier Symphony – Chat Prompt-Katalog, Bedienansicht V1

Stand: 2026-10-15 · Dokumentation einer ausdrücklich gewünschten Benutzeroberfläche. **Kein Ausführungsauftrag.**

## Exakt gewünschte Chat-Ansicht
Der Nutzer möchte **innerhalb der ChatGPT-Nachricht**, nicht über eine HTML-Datei, Markdown-Download, externen Link oder separaten Browser, durch einen Prompt-Katalog navigieren.

Layout (siehe vom Nutzer bestätigter iPhone-Screenshot):
- Überschrift `COURIER SYMPHONY · KATALOGANSICHT`, `Traumkatalog 3000`, Status `PLAN_ONLY`.
- Obere Zeile mit **Zurück ←** links, **N / 3000** mittig und **Weiter →** rechts; beide Pfeile führen zu echten Aktionen.
- Darunter ID `TRAUM-0001`, Fachthema und Phase; **Kopieren**-Schaltfläche rechts oben am Prompt.
- Der **vollständige** Prompttext erscheint in einer scrollbaren Fläche. `Kopieren` kopiert den **gesamten Text**, nicht nur die sichtbaren Zeilen.
- Wechsel zum nächsten/vorherigen Datensatz ohne Verlassen des Chats; mobile Touch-Bedienung.
- Die zuletzt bestätigte Chat-Ansicht hatte nur **3 geladene Datensätze**. Das ist eine technische Beschränkung der damaligen Implementierung, **keine** verifizierte interaktive 3000er-Volltextansicht. Eine Anzeige `N / 3000` allein beweist nicht, dass 3000 Datensätze geladen sind.

## Wiederherstellung in einem neuen Chat
Kopierbarer Nutzerprompt:

> Öffne mir den Courier-Symphony-Traumkatalog **direkt in dieser Chat-Nachricht** als interaktive Ansicht wie im Screenshot vom 15.10.2026: Zurück-Pfeil links, Nummer `N / 3000` in der Mitte, Weiter-Pfeil rechts, `Kopieren` rechts über dem vollständigen Prompt. Kein HTML-Link, kein Download als Hauptansicht, keine deaktivierten Deko-Pfeile. Verwende die vorhandenen Katalogdateien, wenn verfügbar, und zeige transparent, wie viele Original-Volltexte tatsächlich geladen sind. Gib mir eine Suche und ID-Sprung, wenn technisch möglich. Kein Agentenstart, keine Queue-Änderung.

## Daten- und Sicherheitsregeln
- `TRAUM-0001..3000` sind Katalog-IDs und **keine** freigegebenen Workkeys.
- `PLAN_ONLY`; `NEW_FULL_DRAFT_UNREVIEWED` bis zur Qualitätsprüfung.
- Originale, die in anderen Berichten als verifiziert gemeldet wurden, nicht durch synthetische Entwürfe ersetzen.
- Keine automatische Ausführung, API-Kosten, GitHub-Merges oder schreibende Datenbankoperationen.
- Die Katalogdateien müssen in einem neuen Chat erreichbar sein; **eine GitHub-UI-Spezifikation allein enthält nicht die 3000 Volltexte**. Falls Dateien fehlen, transparent anfordern statt Inhalte zu erfinden.

## Windows- und Mac-Desktop-Ablage (separater späterer Auftrag)
Ein lokaler Agent kann eine Kopie der UI-Spezifikation und einen kleinen Checkpoint in bereits vorhandenen Grok-Desktop-Ordnern ablegen **erst nach** belegtem Pfad, Owner, Schreibfreigabe, Backup und Ressourcenprüfung. Mac-Datenrettung/FREEZE beachten. Keine Pfade raten, keine Dateien überschreiben.

## Abnahme
1. Zwei funktionierende Pfeile, soweit Datensätze vorhanden; keine Attrappen.
2. Volltextkopie über `Kopieren`.
3. Korrekte ID und Zähler; tatsächlich geladene Anzahl sichtbar.
4. Darstellung direkt im Chat; keine externe Datei als Ersatz.
5. Wiedereinstieg über obigen Wiederherstellungsprompt.
6. Kein automatischer produktiver Auftrag.
