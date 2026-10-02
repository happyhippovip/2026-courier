# User Acceptance X — State-Version / Migration / Update-Ehrlichkeit (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: G-nah (Update/Rollback/LKG) — G definiert den Rückweg; X
definiert den Hinweg: was passiert mit MEINEN Goals beim Update.

## USER_PROBLEM

Als Nutzer steht ein Update an und ich frage: was passiert mit meinen
laufenden Goals? Werden sie migriert, bleiben sie liegen, gehen sie
verloren — und wer sagt mir vorher, ob mein State zur neuen Version
passt? "Einfach updaten" ohne State-Antwort ist kein Angebot.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- `load_state` (`server/app.py:55-63`): liest JSON, setzt drei Keys per
  `setdefault` (goals/tasks/workers) — keine Schema-Prüfung, keine
  Version, keine Migration, kein Backup. Jede Vergangenheit lädt still;
  jede Zukunft (State neuer als Code, z. B. nach Rollback) lädt still;
  korruptes JSON crasht unbehandelt (`json.load` ohne Guard).
- BEFUND X-a (Version ohne Leser): `server/state/demo_state.json` trägt
  `"schema_version": 2` — aber `server/app.py` referenziert
  `schema_version` nirgends. Die einzige Versions-Nummer im State-Umfeld
  ist Dekoration. (Die vielen `"2.0"`-Checks in `scripts/` gelten
  Chief-/Bridge-Nachrichten, nicht dem zentralen State.)
- BEFUND X-b (kein Migrations-Pfad): Kein Migrations-Skript, kein
  Backup-vor-erstem-Schreiben, kein "State zu neu"-Guard, keine
  Kompatibilitäts-Matrix. Update = Code tauschen + hoffen; Rollback =
  alten Code auf neuen State loslassen + hoffen. G3 (Rollback belegt
  LKG-Fingerprint) hat auf State-Ebene kein Gegenstück.
- BEFUND X-c (korrupter State = Crash statt Satz): `json.load`-Fehler
  propagiert als unbehandelte Exception — der Nutzer bekommt 500/Traceback
  statt U1-Satz (Klasse + Next). Überlapp mit U2 (Korrelations-ID),
  hier als State-Spezialfall notiert.
- Positiv: Atomares Schreiben (tmp + fsync + os.replace, `:65-72`) —
  Halb-Schreibstände sind ausgeschlossen. Die Speicher-Schicht ist
  solide; nur die Versions-Schicht fehlt.

## ACCEPTANCE_REQUIREMENT

- X1: Jeder State trägt eine gelesene Version: `schema_version` wird beim
  Laden geprüft (X-a-Fix). Unbekannte/fehlende Version → expliziter
  Zustand UNKNOWN_SCHEMA mit Next (migrieren/sichern/neu anfangen),
  nie stilles Laden.
- X2: Vor jedem Update sieht der Nutzer die State-Antwort (ergänzt G2):
  State-Version alt → neu, Migrations-Schritte (was wird umgeschrieben),
  Nicht-Migrierbares (was bleibt liegen / wird archiviert), Backup-Ref
  (automatische State-Kopie VOR dem ersten Schreiben der neuen Version).
  Kein Update ohne diese vier.
- X3: Forward-Guard: Code lehnt State neuer als er selbst mit klarer
  Meldung ab ("State v3, Code versteht v2 — kein Start ohne Migration"),
  statt ihn still zu laden und zu verstümmeln. Rollback-Sicherheit auf
  State-Ebene (G3-Gegenstück).
- X4: Korrupter State ist ein Diagnose-Fall, kein Crash: stabile Meldung
  + Korrelations-ID + Backup-Verweis + Support-Bundle-Pfad (H1/U2).
  (X-c-Fix.)
- X5: Solange X1–X4 fehlen, gilt die ehrliche Anzeige (G5-Schwester):
  "Updates migrieren deinen State derzeit NICHT automatisch. Sichere
  <State-Pfad> + <Artifact-Pfad> (N1) vor jedem Update manuell."

## MISSING_SYSTEM_SUPPORT

- Keine State-Versionierung im Live-Pfad, keine Migration, kein
  Backup-vor-Upgrade, kein Forward-Guard, kein Korrupt-Handler.

## PREPARABLE_NOW

- Dieses Dokument (X1–X5 + Befunde X-a bis X-c).
- X5-Wording als sofortige ehrliche Update-Regel (neben G5).
- Versions-Schema-Entwurf (Felder: schema_version, code_min_version,
  migrated_at, migrated_from, backup_ref) — Schema, kein Code.

## BLOCKED_UNTIL

- Gate-7-Freigabe (wie G) + Runtime-Owner baut Version/Migration/Guards.
- Erste echte Migration erst mit erstem Schema-Wechsel nach Pilot.

## NEXT

Y (Plattform-/Host-Wechsel): was passiert mit meinen Goals, wenn ich von
Windows auf Mac wechsle — mitnehmen, neu anfangen, oder beides parallel?
(N1-Orte + X-Version + V-Uhren treffen auf den Gerätewechsel.)
