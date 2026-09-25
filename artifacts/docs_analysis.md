# Courier Documentation & API Analysis

## 1. Verfügbare Dokumentation
Das Projekt ist exzellent (fast schon exzessiv) dokumentiert.
- `COURIER_START_HERE.md` liefert eine extrem präzise "Bootstrap"-Anleitung für neue Agenten und Entwickler, welche die Architektur (Motor, Ledger, Worker Contract) punktgenau erklärt.
- Der Ordner `docs/` enthält 50 `.md` Dateien, darunter tiefgreifende Strategiepapiere (`MULTI_AGENT_CONVERGENCE_POLICY.md`, `OPUS_MASTERPLAN_HANDOFF_2026-09-24.md`).
- Das Root-Verzeichnis enthält weitere ~30 Markdown-Dateien mit Checkpoints und historischen Plänen.

## 2. Unklare Schnittstellen & Lücken
- **API-Dokumentation fehlt**: Obwohl die REST-API in `server/app.py` über 70KB groß ist, existiert kein OpenAPI/Swagger-File oder eine dedizierte API-Referenz in den `docs/`. Clients (Worker) müssen den Code lesen, um Endpunkte zu verstehen.
- **Veraltete Dokumente**: Viele Pläne im `docs/` Verzeichnis (z.B. alte `WF-CHIEF-*` Execution Strategies) repräsentieren den Zustand vor Wochen oder Monaten. Es ist oft unklar, ob eine Policy noch aktiv ist oder durch neuere "Masterplans" (wie den OPUS_MASTERPLAN) überschrieben wurde.
- **Inline-Code-Doku**: Zwar gibt es in den Kern-Skripten wie `work_queue.py` funktionale Logik, aber echte Docstrings (`"""..."""`) an Funktionen oder Klassen sind rar. Das Projekt verlässt sich auf die High-Level-Markdowns, statt den Code selbst zu dokumentieren.

## 3. Handlungsempfehlungen
1. **API-Doku**: Generierung einer `openapi.yaml` für `server/app.py`.
2. **Doc-Rot bekämpfen**: Verschieben historischer Pläne nach `docs/archive/`. Nur gültige Invariants und Policies im aktiven `docs/`-Root belassen.
3. **Docstrings**: Den Python-Code in `scripts/` mit Typ-Hinweisen und Docstrings versehen, um die Lesbarkeit für Tools und Entwickler zu erhöhen.
