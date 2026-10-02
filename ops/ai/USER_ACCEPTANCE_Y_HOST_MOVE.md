# User Acceptance Y — Host-/Plattform-Wechsel / Umzug (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: F/G/N/V/X-nah — N1-Orte + X-Version + V-Uhren + G-Rollback
treffen auf den Gerätewechsel: Was zieht mit um, was bricht?

## USER_PROBLEM

Als Nutzer wechsle ich das Gerät oder Verzeichnis (Windows → Mac, neuer
Rechner, neues WLAN) und frage: ziehen meine Goals mit um? Muss ich etwas
exportieren? Und wenn ich es falsch mache — warnt mich jemand, bevor
Courier mit leerem State startet und so tut, als gäbe es nichts?

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- State-Pfade sind CWD-relativ per Default: `server/state/
  central_state.json` (`server/app.py:11`), `server/state/artifacts`
  (`scripts/artifact_store.py:74`). Kein absoluter Anker, keine
  Host-Bindung, keine "State gehört zu <Host>"-Prüfung.
- BEFUND Y-a (stiller Leer-Start): Startet der Server in einem anderen
  Verzeichnis (oder nach Umzug ohne State-Kopie), lädt `load_state`
  still einen LEEREN State (`:55-63`: Datei fehlt → leere Dicts).
  Der Nutzer sieht "keine Goals" — nicht "State nicht gefunden, gesucht
  in <Pfad>". Verloren vs. nie-da ist ununterscheidbar.
- BEFUND Y-b (Worker-Identitäts-Kollision): `register` überschreibt pro
  worker_id vollständig (`:205-213`) und meldet immer REGISTERED —
  keine Host-Namensraum-Prüfung. Zwei Rechner mit gleicher WORKER_ID
  (aus kopierter config.json / gleichem Env-Namen) überschreiben sich
  gegenseitig: last_seen-Flapping, Task-Diebstahl
  (current_task gehört mal A, mal B), ohne jede Warnung.
- BEFUND Y-c (fest verdrahtete LAN-IP): Windows-Daemon
  `DEFAULT_SERVER = "http://192.168.178.162:8080"`
  (`windows_worker/daemon.py:10`). Netzwerk-/Rechner-Wechsel bricht die
  Worker→Server-Bindung still (Env/config gewinnen, aber Default-Nutzer
  zeigen ins Leere). Mac-Seite: config + Keychain + Env (kein
  IP-Default) — asymmetrisch, nirgends dokumentiert.
- BEFUND Y-d (kein Umzugs-Verfahren): Kein Export/Import, keine
  Umzugs-Checkliste. Zusammengehöriges (State + Artifacts + Version +
  Uhren + Keys) muss der Nutzer selbst zusammentragen (N1/X1/V4/F4).
- Positiv: Server bindet `0.0.0.0:8080` (`app.py:562`) — LAN-Erreichbarkeit
  gegeben; Mac-Keychain-Pfad für Credentials existiert (kein Key-Kopieren
  nötig, F4-konform).

## ACCEPTANCE_REQUIREMENT

- Y1: Kein stiller Leer-Start: Fehlt die State-Datei am erwarteten Pfad,
  sagt der Server beim Start: "Kein State in <Pfad> — neu anfangen oder
  State bereitstellen?" (Y-a-Fix.) "Keine Goals" gibt es nur noch bei
  explizit leerem, gefundenem State.
- Y2: Worker-Identitäten sind host-eindeutig: WORKER_ID enthält Host-Anteil
  (Regel + Generierungs-Vorschrift) oder `register` warnt bei
  ID-Wiederverwendung von anderer Plattform/gleichzeitigem Doppel-
  Heartbeat ("ID-Kollision möglich — IDs prüfen"). (Y-b-Fix.)
- Y3: Server-Bindung ist prüfbar: Worker-Start zeigt "Server: <URL>,
  erreichbar: ja/nein (Probe <Zeit>)" — kein stilles Zeigen auf tote
  LAN-IPs (Y-c-Fix: Default dokumentieren oder auf localhost + explizite
  LAN-Config umstellen; Entscheidung Runtime-Owner).
- Y4: Umzugs-Checkliste (Prep-Doku, sofort nutzbar): 1) State + Artifacts
  kopieren (Pfade aus N1), 2) Version prüfen (X1), 3) Keys pro Umgebung
  neu provisionieren, nie kopieren (F4), 4) WORKER_ID neu/host-eindeutig
  (Y2), 5) Server-URL prüfen (Y3), 6) Uhren-Offset notieren (V4),
  7) Probe-Goal (S1) vor echter Arbeit. Sieben Punkte, abhakbar.
- Y5: Parallel-Betrieb zweier Hosts am selben State ist verboten, bis ein
  Lock/Lease existiert: "Ein State, ein Server." Zwei Server auf einer
  State-Datei = Korruptions-Risiko (atomares Schreiben schützt vor
  Halb-Ständen, nicht vor gegenseitigen Überschreibungen).

## MISSING_SYSTEM_SUPPORT

- Keine Pfad-/Host-Prüfung, kein Leer-Start-Hinweis, keine
  ID-Kollisions-Warnung, keine Bindungs-Probe, kein Umzugs-Assistent.
- Kein State-Lock gegen Doppel-Server (Y5).

## PREPARABLE_NOW

- Dieses Dokument (Y1–Y5 + Befunde Y-a bis Y-d).
- Y4-Checkliste als sofort verwendbare Umzugs-Anleitung (Doku reicht).
- Y-b/Y-c-Notizen an Runtime-Owner (ID-Regel, Server-Default).

## BLOCKED_UNTIL

- Echter Host-Wechsel erst mit Mac-Canary/Pilot (Windows ↔ Mac real).
- Runtime-Owner implementiert Y1–Y3 + Y5.

## NEXT

Z (Serien-Abschluss/Übergabe-Protokoll): Status dieser Reihe (A–Y),
offene Owner-Entscheidungen, Mess-Lücken bis Pilot — ein Blatt für den
nächsten Operator. (Danach: zurück zu A mit Pilot-Daten.)
