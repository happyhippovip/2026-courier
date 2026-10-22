# Courier in 60 Sekunden – lokale Vorschau (Workkey PRODUKTPFAD-60S-V1)

Start: `./start_vorschau.sh` (Linux/Mac) oder `start_vorschau.cmd` (Windows), dann http://127.0.0.1:8766 öffnen.

Pfad: Start → Mission → lokales Ergebnis → Nachweis → Pilotkontakt (5 Schritte, ca. 6 Klicks).

Wahrheitsregeln:
- REPLAY = echter Lauf von `python -m courier_hub.mission_chip --json` auf integration/v1 d5b19f1df, aufgezeichnet in `mission_replay.json` (Metadaten und SHA-256 in `replay_meta.json`). Die Seite spielt ihn nur ab.
- LIVE = POST /hub/api/mission-chip, funktioniert nur, wenn die Seite vom laufenden Hub kommt; sonst UNKNOWN.
- Grün nur, wenn verifier_result.accepted, resolution=verified, overall_status=COMPLETE und ein Journal-Ereignis RESULT_ACCEPTED (seq>0) vorliegen.
- Die Prüfschritte nutzen das Feld `passed`, nicht `status` (der Server setzt `status` in Schritt 1–2 fest auf "PASS").
- „Selbst nachrechnen“ berechnet SHA-256 im Browser (WebCrypto) – das prüft nur den Fingerabdruck des Inhalts, nicht den Lauf.
- Kein Preis, keine Bestellung: Kontakt nur per mailto founder@couriersymphony.de, nichts wird automatisch gesendet.

Keine Repo-Datei geändert, kein Kolibri-Kern, keine CSV-Cleaner-Logik.
