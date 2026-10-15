# Courier Symphony – Traumkatalog 3000 / Chat-Navigation V2

Datum: 2026-10-15. Vom Nutzer ausdrücklich zur Sicherung freigegeben. Der Nutzer möchte die bereits geöffnete Katalogansicht behalten und ungestört arbeiten.

## Bestätigte Anforderungen und Bedienung
- Direkt in der ChatGPT-Nachricht, kein HTML-Link als Ersatz.
- 1 bis 3000 innerhalb derselben interaktiven Karte; Start bei Nummer 21, weil 1–20 bearbeitet wurden.
- Zurück und Weiter wechseln jeweils genau einen Datensatz; Grenzen ausschließlich 1 und 3000, nicht 20.
- Direkter Nummernsprung 1–3000 mit Eingabefeld und Öffnen.
- Produktlinien-Auswahl: 15 Produktlinien zu je 200 Einträgen.
- Kopieren rechts über dem Prompt: GenUI.copy(full) kopiert den vollständigen aktuellen Prompt; danach Anzeige Kopiert.
- Prompt in scrollbarem Bereich mit ID, Produktlinie, Fachthema, Phase; mobile Touch-Bedienung.
- Status PLAN_ONLY / maschinell erzeugter Entwurf; kein produktiver Workkey, kein automatischer Agentenstart.
- Keine weiteren Nachrichten für Navigation, keine deaktivierten Attrappen.

## Index-Algorithmus der tatsächlich zuletzt gerenderten Chat-Karte
idx ist DIL.useState(21). target ist DIL.useState('21'). copied ist DIL.useState(false).
lineIndex = Math.floor((idx-1)/200)
topicIndex = Math.floor(((idx-1)%200)/10)
phaseIndex = (idx-1)%10
id = 'TRAUM-' + String(idx).padStart(4,'0')
line = groups[lineIndex][0]
topic = groups[lineIndex][1].split('|')[topicIndex]
phase = phases[phaseIndex]
Der Prompttext full wird aus ID, Linie, Thema, Phase, phasenspezifischer Anweisung, Lieferung, Pflichtfeldern und Grenzen zusammengesetzt.
Zurück: disabled bei idx===1, sonst setIdx(v=>Math.max(1,v-1)).
Weiter: disabled bei idx===3000, sonst setIdx(v=>Math.min(3000,v+1)).
Nummernsprung: nur Integer 1–3000; setIdx(Number(target)).
Produktlinienauswahl: setIdx(Number(v)*200+1).
Kopieren: GenUI.copy(full); setCopied(true).

## 15 Produktlinien / Nummernbereiche
1 Agenten-Orchestrierung 1–200
2 Verified Handoff 201–400
3 Independent Acceptance 401–600
4 Kolibri Dashboard 601–800
5 Host-Monitoring 801–1000
6 Queue-Workkey 1001–1200
7 Projektgedächtnis 1201–1400
8 Account Continuity 1401–1600
9 Datenimport-Sync 1601–1800
10 Recovery-Wiederaufnahme 1801–2000
11 Modellrouting 2001–2200
12 Kosten-Ressourcen 2201–2400
13 Security-Audit 2401–2600
14 Developer CLI 2601–2800
15 Windows EXE Pilot 2801–3000

## Zehn Phasen
Quelleninventur; Risikoanalyse; Vertragsspezifikation; Zustandsmodell; Sicherheitsprüfung; Prüfplan; UI- und Bedienkonzept; Integrationsentwurf; Kosten- und Betriebsplan; Abnahme- und Übergabepaket.

## Wiederherstellungsprompt
Öffne den Courier-Symphony-Traumkatalog direkt in dieser Chat-Nachricht in der funktionierenden 1–3000-Ansicht vom 15.10.2026. Referenz: happyhippovip/2026-courier, Branch docs/chat-katalog-funktioniert-2026-10-15, Datei docs/ui/TRAUMKATALOG_3000_CHAT_NAVIGATION_V2_2026-10-15.md. Starte bei Nummer 21 oder meiner zuletzt genannten Nummer. Echte Zurück-/Weiter-Pfeile ohne Grenze bei 20, Nummernsprung 1–3000, Produktlinienauswahl und Kopieren rechts oben über dem vollständigen Prompt. Kein Link oder HTML statt der Chat-Ansicht. Lade die Katalogdaten aus der bestehenden Quelle, statt Originaltexte zu erfinden. Keine produktiven Aktionen.

## Wahrheitsgrenze
Dies ist die exakte Bedien- und Navigationsspezifikation der zuletzt gezeigten 1–3000-Karte, aber KEINE bytegenaue Sicherung sämtlicher 3000 Volltexte oder des gesamten Chat-UI-Zustands. Die 3000 Prompt-Entwürfe wurden aus 15 Linien, 20 Themen und 10 Phasen systematisch generiert; Original- und Entwurfsstatus unterscheiden. GitHub kann den laufenden Chat nicht offenhalten; die vorhandene Chat-Nachricht bleibt für den Nutzer bedienbar, solange sie in der Oberfläche verfügbar ist.

## Schutz
Kein Merge nach main, keine Desktop-Schreibaktionen, keine Queue-Änderung, keine Tests oder Agentenstarts. Diese Sicherung ist ein Dokumentationscommit auf dem bestehenden separaten Branch.