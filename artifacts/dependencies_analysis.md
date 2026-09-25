# Courier Dependencies & Config Analysis

## 1. Paketierung & Abhängigkeiten
- Die Abhängigkeiten sind minimalistisch und konsistent. `pyproject.toml` und `requirements.txt` weisen exakt denselben Dependency-Baum auf (`Flask>=2.0.0`, `requests>=2.25.0`, `psutil>=5.8.0`, `keyring>=23.0.0`).
- Das Build-Backend (`setuptools.build_meta`) ist modern und PEP-517 konform.
- Python-Voraussetzung ist `>=3.9`, was einen breiten Einsatz auf macOS und Windows (beides Zielplattformen) sicherstellt.

## 2. Laufzeitumgebung
- Ein lokales `venv/` ist aktiv und eingerichtet.
- Lokale Test-Keys und Umgebungsvariablen liegen korrekt in der `.env.local` (`COURIER_API_KEY`, `COURIER_VERIFIER_API_KEY`).

## 3. Konfiguration (`config/`)
Das `config/`-Verzeichnis enthält sauber getrennte JSON-Definitionen (z.B. `hardware_profiles.json`, `entitlements.json`, `teamwork_policy.json`). Diese trennen die logische Architektur klar von fest verdrahteten Magic Strings im Code.

## 4. Test-Konfiguration
`pytest.ini` ist minimal, bindet den `PYTHONPATH` aber explizit auf den Root-Pfad (`.`) und adressiert `tests/`. Es gibt keine kollidierenden Konfigurationen in der `pyproject.toml`.

## Fazit
Die Basis-Konfiguration des Projekts ist exzellent strukturiert, minimalistisch und konsistent. Es gibt keine unaufgeräumten Dependencies oder konkurrierenden Paketmanager (z.B. Poetry vs Pip).
