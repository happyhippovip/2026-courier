# Courier Capsule Registry V1 – Community-Erweiterungen über Work Capsules

Status: Entwurf (Draft). Baut auf `docs/orchestrator/COURIER_EINSTEIN_LAYER.md` und `courier_orchestrator/` (PR #542) auf.
Prinzip wie im Orchestrator: *viele Augen, ein Stift*. Wer eine Capsule hochlädt, darf sie weder selbst reviewen noch freigeben.

## 1. Was ist eine Work Capsule?

Eine Capsule ist ein wiederverwendbares Arbeitspaket ohne private Projektdaten:

| Feld | Inhalt |
|---|---|
| `capsule_id`, `version` | eindeutiger Schlüssel `id@version`, Versionen sind unveränderlich |
| `author`, `license` | Autor und SPDX-Lizenz (muss auf der Allowlist stehen) |
| `task_class`, `problem_class` | Task-Klasse (für Trust) und Beschreibung der Problemklasse |
| `inputs` | erwartete Inputs (Typen, keine echten Daten) |
| `planning_pattern` | Schritte des Planungsmusters |
| `worker_requirements` | Anforderungen an Worker (Modell-Tier, Tools) |
| `verification_pattern` | wie der unabhängige Verifier das Ergebnis prüft |
| `failure_modes` | bekannte Fehlerbilder |
| `cost_profile` | erwartete und maximale Kosten |
| `output_schema` | JSON-Schema des Outputs |
| `code` (optional) | kleine Python-Helfer, nur Stdlib-sichere Module |

Code: `courier_orchestrator/capsules/schema.py`.

## 2. Ablauf

```
Upload ─► Automatische Prüfung ─► Quarantäne ─► Unabhängiges Review ─► Human Gate ─► signiertes Update an alle
              │ fail                                   │ fail                                   │
              ▼                                        ▼                                        ▼
          rejected                                 bleibt / rejected                      Rückruf möglich (recalled)
```

### 2.1 Upload
Autor lädt Capsule als JSON hoch. Kanonische Serialisierung (sortierte Keys) → `sha256`. Eine Version, die schon existiert, kann nicht überschrieben werden.

### 2.2 Automatische Prüfung (alle Stufen müssen grün sein)
1. **Schema**: Pflichtfelder, Typen, `capsule_id`-Format, `schema_version = capsule/v1`. V1: `validate_capsule`; später zusätzlich `jsonschema` (MIT).
2. **Lizenz-Allowlist**: `Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, CC0-1.0`. Später: ScanCode Toolkit und REUSE für Lizenztexte in Anhängen.
3. **Secret-Scan**: V1 mit Regex (AWS-, GitHub-, Slack-, sk-Keys, Private Keys, `password=`-Muster). Produktion: gitleaks.
4. **Private-Daten-Scan**: E-Mail-Adressen und absolute Home-Pfade führen zur Ablehnung.
5. **Statische Sicherheitsanalyse**: AST-Prüfung auf verbotene Imports (`os, subprocess, socket, shutil, ctypes, importlib, pickle, marshal, requests, urllib, http, …`) und Aufrufe (`eval, exec, compile, __import__, open`). Produktion: zusätzlich Semgrep und Bandit; OSV-Scanner für Abhängigkeiten.
6. **Größenlimit**: 256 KiB pro Capsule.
7. **Tests in Sandbox** (V2): Capsule-Helfer laufen nur gegen synthetische Fixtures, ohne Netzwerk, in gVisor (`runsc`) oder nsjail mit CPU/RAM/Zeit-Limits.
8. **Signatur und Herkunft** (V2): Signatur der Capsule mit Sigstore (cosign/sigstore-python, keyless über OIDC), in-toto-Attestierung der Prüfkette, Zielniveau SLSA Build L2+.

Fällt eine Stufe durch, ist die Capsule `rejected` mit Fehlerliste. Sonst `quarantined`.

### 2.3 Quarantäne
Quarantänierte Capsules werden **nie** verteilt. Sie sind nur für Reviewer sichtbar.

### 2.4 Unabhängiges Review
Mindestens ein bestandenes Review von jemand anderem als dem Autor. Ein negatives Review blockiert die Freigabe. Selbst-Review wird technisch verweigert.

### 2.5 Human Gate (Freigabe)
Ein Mensch (zunächst Dennis) gibt explizit frei. Der Freigebende darf nicht der Autor sein. Vor Freigabe wird der `sha256` erneut geprüft. Kein automatischer Publish.

### 2.6 Signiertes Update an alle
Das Distributions-Manifest enthält nur `approved` Capsules mit passendem Hash (`id@version` + `sha256`) plus die Liste zurückgerufener Keys. Produktion: Manifest als TUF-Repository (python-tuf) mit signierten Metadaten (Schutz vor Rollback/Freeze), Capsules zusätzlich mit Sigstore signiert. Clients übernehmen nur Capsules, deren Hash und Signatur stimmen. Es fließen keine Nutzungs- oder Projektdaten zurück.

## 3. Trust pro Autor und pro Task-Klasse
- Trust ist ein Zähler `trust[author][task_class]`.
- Freigabe: +1. Rückruf: −3 (Fehler wiegen schwerer als Erfolge).
- Trust ist pro Task-Klasse getrennt: ein guter Autor für `extraction` bekommt keinen Vorschuss für `code_change`.
- V2: Trust steuert Review-Tiefe (z. B. 2 Reviews bei Trust ≤ 0), nie das Human Gate.

## 4. Rückruf
- `recall(key, reason)` setzt Status `recalled`, unabhängig vom vorherigen Status.
- Zurückgerufene Capsules verschwinden aus dem Manifest und stehen in `recalled_keys`; Clients deaktivieren sie beim nächsten Update.
- Rückrufe bleiben im Index dokumentiert (nichts wird gelöscht).

## 5. Keine privaten Daten
- Capsules beschreiben Muster, keine Instanzen: Inputs sind Typen, keine Inhalte.
- Automatische Ablehnung bei Secrets, E-Mail-Adressen, Home-Pfaden.
- Der Upload-Client baut Capsules aus Missionen nur über eine Allowlist von Feldern; Mission-Journale, Hub-Deltas und Kundendaten sind nie Teil einer Capsule.
- Reviewer prüfen zusätzlich manuell auf Projektbezug.

## 6. Code-Slice V1 (dieser PR)
- `courier_orchestrator/capsules/schema.py` – Dataclass `Capsule`, Status, Allowlist, Limits
- `courier_orchestrator/capsules/validate.py` – `validate_capsule`
- `courier_orchestrator/capsules/registry.py` – lokaler JSON-Index mit sha256, Quarantäne/Review/Freigabe/Rückruf, Trust, Manifest
- `tests/capsules/test_capsule_registry_v1.py`
Nur Stdlib, kein Netzwerk, keine Veröffentlichung.

## 7. Open-Source-Bausteine (übernehmen statt bauen)

Lizenzen geprüft am 13.10.2026 über die GitHub-API bzw. die LICENSE-Dateien.

| Baustein | URL | Lizenz | Zweck | Empfehlung |
|---|---|---|---|---|
| Sigstore cosign | https://github.com/sigstore/cosign | Apache-2.0 | Signieren/Verifizieren von Artefakten, keyless | übernehmen (CLI in CI) |
| sigstore-python | https://github.com/sigstore/sigstore-python | Apache-2.0 | Sigstore-Signatur direkt aus Python | übernehmen (Client-Verifikation) |
| in-toto | https://github.com/in-toto/in-toto | Apache-2.0 | Attestierung der Prüfkette | übernehmen (V2) |
| SLSA | https://github.com/slsa-framework/slsa | Community Specification License 1.0 | Spezifikation Herkunftsniveaus | als Zielrahmen nutzen |
| python-tuf (The Update Framework) | https://github.com/theupdateframework/python-tuf | Apache-2.0 (auch MIT) | sichere signierte Update-Verteilung, Rollback-Schutz | übernehmen für Distribution |
| gitleaks | https://github.com/gitleaks/gitleaks | MIT | Secret-Scan | übernehmen (ersetzt Regex-Scan) |
| Semgrep (Community Edition) | https://github.com/semgrep/semgrep | LGPL-2.1 | statische Analyse mit eigenen Regeln | als externes Tool nutzen |
| Bandit | https://github.com/PyCQA/bandit | Apache-2.0 | Python-Sicherheitslinter | übernehmen |
| OSV-Scanner | https://github.com/google/osv-scanner | Apache-2.0 | bekannte Schwachstellen in Abhängigkeiten | übernehmen |
| ScanCode Toolkit | https://github.com/aboutcode-org/scancode-toolkit | Apache-2.0 (Daten CC-BY-4.0) | Lizenzerkennung | übernehmen (V2) |
| REUSE tool | https://github.com/fsfe/reuse-tool | GPL-3.0-or-later | SPDX-Konformität prüfen | nur als externes CLI |
| gVisor | https://github.com/google/gvisor | Apache-2.0 | Sandbox-Kernel für Container | übernehmen für Sandbox-Tests |
| nsjail | https://github.com/google/nsjail | Apache-2.0 | leichte Prozess-Sandbox | Alternative zu gVisor |
| jsonschema | https://github.com/python-jsonschema/jsonschema | MIT | JSON-Schema-Validierung | übernehmen |
| pluggy | https://github.com/pytest-dev/pluggy | MIT | Plugin-/Hook-System | optional für Capsule-Hooks |
| YARA | https://github.com/VirusTotal/yara | BSD-3-Clause | Malware-Signaturen | optional |
| ClamAV | https://github.com/Cisco-Talos/clamav | GPL-2.0 | Virenscanner | optional, nur als externer Dienst |

GPL/LGPL-Tools werden nur als separate Prozesse aufgerufen, nicht in Courier eingebunden.

## 8. Nicht in V1
Sandbox-Ausführung, echte Signaturen, TUF-Repository, Upload-API, UI. Keine Änderungen an `server/app.py`, Ralph oder `.github/workflows`.
