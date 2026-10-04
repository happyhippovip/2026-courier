# User Acceptance V — Uhren / Zeit-Disziplin (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: Querschnitt (K-Frische, O-Zertifikat, S-Messung und RUN-Evidenz
brauchen alle vergleichbare Zeiten — V definiert, welche Uhr sie liefert).

## USER_PROBLEM

Als Nutzer sehe ich "vor 5 Minuten", "stale", "Abschluss 14:32" — aber nach
welcher Uhr? Was passiert, wenn mein Rechner schlief, die Uhr sprang oder
Server und Worker auf verschiedenen Rechnern laufen? Zeit-Anzeigen ohne
Uhren-Regel sind Deko.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Server-Zeit = reine `time.time()`-Epochs: `last_seen`-Stempel
  (`server/app.py:209,243,265`), stale-Vergleiche (`:296,423`),
  `/health`-Zeit (`:81`). Keine Timezone (Epochs brauchen keine — gut),
  kein `monotonic`, keine ISO-Zeit im State.
- Peripheral-Präzedenz (gut, aber nicht im Server-Pfad): UTC-ISO-Konvention
  in vielen `scripts/` (created_at/updated_at mit timezone.utc);
  `time.monotonic()` für Deadlines im Mac-Daemon
  (`mac_worker/daemon.py:368-376`), `runtime_state.py:115-116` und
  Github-Adapter (`github_worker_adapter.py:154-155`).
- Positiv: `last_seen` stempelt der SERVER bei Empfang — Worker-Uhren
  werden nie vertraut. Skew zwischen Worker- und Server-Uhr kann die
  Stale-Erkennung nicht verfälschen.
- ABER — Befund V-a (Schlaf-Szenario): Stale-Mathematik läuft über
  Wall-Clock. Laptop-Sleep/Wake, VM-Suspend oder NTP-Sprung auf dem
  SERVER-Rechner lassen `now - last_seen` springen: Nach dem Aufwachen
  sind alle Worker gleichzeitig > 300 s stale → Massen-Quarantäne
  (R-Pfad) ohne echten Ausfall. Für Pilot-Laptops das wahrscheinlichste
  Zeit-Szenario, nirgends adressiert.
- Befund V-b (kein Anzeige-Format): State kennt nur Epochs; Zertifikate
  (O1), Gesehen-Zeiten (M2), Messungen (S2) brauchen lesbare Zeiten —
  Format-Regel fehlt (UTC-ISO als Konvention vorhanden, aber nicht
  bindend, Server-emittiert nichts davon).
- Befund V-c (RUN-Evidenz ohne Uhren-Check): RUN_1/RUN_2-Command-Sheets
  fordern Port-frei/Branch/keine-stale-DB — keinen Uhren-Vergleich.
  Evidence-Merge (Server-Log + Worker-Log + Verifier-Log) setzt
  vergleichbare Uhren voraus, ohne es zu prüfen.

## ACCEPTANCE_REQUIREMENT

- V1: Intervall-Messung (stale, Frische, Timeouts) läuft über monotone
  Uhren, wo der Prozess sie besitzt (Server: monotonic-Delta pro Worker
  zusätzlich zum Epoch-Stempel); Epochs bleiben für absolute Zeitpunkte.
  V-a-Fix durch Runtime-Owner (Präzedenz: Mac-Daemon nutzt bereits
  monotonic).
- V2: Sleep/Wake ist ein bekanntes Ereignis: Erkennt der Server einen
  Zeit-Sprung (monotonic vs. wall driftet), wird er geloggt und die
  Stale-Anzeige sagt "Uhren-Sprung erkannt — Frische neu bewertet"
  statt still zu quarantänieren. Keine Massen-Quarantäne ohne diesen
  Hinweis.
- V3: Anzeige-Format-Regel: Alle Nutzer-Zeiten in ISO-8601 mit expliziter
  Zone (UTC-Default, lokale Zone nur mit Label). Epochs erreichen nie
  eine Anzeige (K1 zeigt "vor N s", O1 zeigt ISO-Zeitpunkt).
- V4: RUN-Evidenz bekommt einen Uhren-Precondition: Vor RUN_1/RUN_2 wird
  der Offset zwischen beteiligten Rechnern gemessen und ins Evidence-Pack
  geschrieben (V-c-Fix durch Run-Prep-Owner). Offset > Schwelle →
  Warnung im Pack, kein stiller Merge.
- V5: Jede Zeit-Anzeige nennt ihre Quelle: "Server-Uhr", "Mac-Runner-Uhr",
  "diese Anzeige". Zeiten ohne Quellen-Label sind ungültig.

## MISSING_SYSTEM_SUPPORT

- Kein monotonic im Server-Pfad, keine Sprung-Erkennung.
- Keine Format-Regel, keine Quellen-Labels, kein Uhren-Precondition.
- Keine Sleep/Wake-Betrachtung für Pilot-Laptops.

## PREPARABLE_NOW

- Dieses Dokument (V1–V5 + Befunde V-a bis V-c).
- V4-Precondition-Entwurf für Run-Prep-Owner (ein Messschritt vor RUN_1).
- V3-Format-Regel als sofort übernehmbarer Glossar-Eintrag (T).

## BLOCKED_UNTIL

- Echte Uhren-Beobachtung erst mit physischem RUN/Pilot (mehrere Rechner).
- Runtime-Owner implementiert monotonic + Sprung-Hinweis.

## NEXT

W (Mehr-Nutzer/Mehr-Geräte): was sehe ich auf Gerät B von der Arbeit auf
Gerät A — und wer darf was? (Single-User-Annahme heute; W formuliert sie
explizit, bevor Pilot sie bricht.)
