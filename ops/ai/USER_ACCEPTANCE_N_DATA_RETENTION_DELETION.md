# User Acceptance N — Datenorte / Wachstum / Löschung (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: F/H-nah (Manifest + Privacy, aber eigene Lücke: nichts kann
je wieder weg — kein Löschen, kein Limit, keine Ablaufregel).

## USER_PROBLEM

Als Nutzer weiß ich nicht: wo liegen meine Daten, was wächst unbegrenzt —
und wie lösche ich etwas wieder? "Vertrau uns, wir heben alles auf" ist
keine Antwort, solange unklar ist, was "alles" ist und ob "vergiss meine
Pilot-Daten" überhaupt geht.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- State-Ort: `COURIER_STATE_FILE`, Default
  `server/state/central_state.json` (`server/app.py:11`). Enthält Goals,
  Tasks, Results, Verifications, Worker — wächst pro Lauf, kein Pruning,
  kein Archiv-Pfad im Code.
- Artifact-Ort: `COURIER_ARTIFACT_DIR`, Default `server/state/artifacts`
  (`scripts/artifact_store.py:74`, eingebunden `server/app.py:74`).
  Upload-Route vorhanden; Löschen/Überschreiben/Quota: nicht vorhanden.
- Logs: Run-Prep sieht `logs/server_runN.log`, `logs/worker_runN.log`,
  `logs/verifier_runN.log` vor; Rotation/Retention-Regel: keine im Repo
  belegt. Watchdog/Beacon loggen nach stdout (Betreiber-Sache).
- BEFUND N-a (kein Vergessen): Null Treffer für delete/retention/purge/
  forget/DELETE in `server/`. Es gibt keinen Lösch-Endpoint, keine
  Ablaufregel, keine Quota, keinen "Pilot-Daten verwerfen"-Pfad.
  Was Courier speichert, bleibt — per Code, nicht per Entscheidung.
- BEFUND N-b (Spannung Proof vs. Privacy, unaufgelöst): Proof-Seite (D)
  verlangt Aufbewahrung (Evidenz-IDs, Re-Hash, Revalidierung bei
  SHA-Wechsel); Privacy-Seite (H) kennt LOCAL_ONLY vs. SHAREABLE, aber
  keine Löschklasse. Welche Daten NACH erfülltem Proof-Zweck weg dürfen,
  ist nirgends geregelt.
- BEFUND N-c (Orte verstreut, unmanifestiert): State, Artifacts, Logs,
  Run-DBs (`ledger_runN.db`), `events/`, Slot-States — kein zentrales
  Daten-Manifest (F1 fordert es, existiert nicht). Der Nutzer kann die
  Frage "was liegt wo" heute nur durch Raten + Suchen beantworten.

## ACCEPTANCE_REQUIREMENT

- N1: Daten-Manifest (zieht F1 an): pro Kategorie (State, Artifacts,
  Logs, Run-DBs, Bundles): Pfad/Env-Override, Inhalt, Zweck,
  Aufbewahrungsgrund. Kein Speicherort ohne Manifest-Eintrag.
- N2: Wachstums-Anzeige: State-Größe + Artifact-Volumen sind ablesbar
  (Bytes + Objekt-Zähler). Unbegrenztes Wachstum ist sichtbar, bevor die
  Platte voll ist.
- N3: Lösch-Regel mit Proof-Vorbehalt: Löschbar sind Run-Artefakte und
  Logs nach Wahl des Nutzers; NICHT löschbar ohne Warnung sind Daten,
  auf die ein offener Proof-/Gate-Nachweis verweist (D-Evidenz-IDs).
  Die Anzeige nennt bei Verweigerung den blockierenden Nachweis.
- N4: "Pilot-Daten verwerfen": Ein definierter Pfad löscht alle Daten
  eines Pilot-Goals (State-Einträge, Artifacts, Logs) — mit Protokoll,
  was gelöscht wurde und was aus N3-Gründen blieb. Bis implementiert:
  ehrliche Anzeige "Löschung derzeit nur manuell (Pfade aus N1)".
- N5: Kein stilles Aufräumen: Weder Server noch Worker noch Skripte
  löschen je automatisch Nutzerdaten ohne Regel + Anzeige. Retention ist
  Opt-in mit sichtbarer Frist, nie Default-Verhalten im Hintergrund.

## MISSING_SYSTEM_SUPPORT

- Alles per Befund: kein Lösch-Endpoint, keine Retention-Engine, keine
  Quota, keine Wachstums-Anzeige, kein Manifest.
- Keine Proof-vs-Privacy-Entscheidung (N-b) durch Plan-Owner.

## PREPARABLE_NOW

- Dieses Dokument (N1–N5 + Befunde N-a bis N-c).
- Manifest-Tabellenkopf mit belegten Erstzeilen (State/Artifacts/Logs
  aus obigen Code-Refs) — als Spec-Anhang, kein Code.
- N4-Übergangsregel (manuelles Löschen per Pfadliste) als sofort ehrliche
  Nutzer-Antwort.

## BLOCKED_UNTIL

- Plan-Owner entscheidet N-b (Aufbewahrungsfristen pro Kategorie).
- Runtime-Owner baut Manifest-Anzeige + Lösch-Pfad (nach Pilot).

## NEXT

O (Fertig-Zertifikat): woran erkenne ich FERTIG verbindlich — DONE-
Semantik, Verifikations-Nachweis und was "alle Schritte reconciled"
für den Nutzer bedeutet. (E3/01 legen vor; O schließt die Lücke zum
verbindlichen Abschluss-Beleg.)
