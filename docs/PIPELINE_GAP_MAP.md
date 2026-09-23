# Content Pipeline Gap-Map

Zielpfad: KANAL WÄHLEN -> STORY/ZIEL -> TEMPLATE -> RUN -> REVIEW -> READY_TO_PUBLISH -> HUMAN APPROVAL -> PUBLISH

Vorhandene Komponenten:
- `config/content_workflows.json`: Definiert Stages (IDEA -> SCRIPT -> ASSET_SELECTION -> VIDEO_BUILD -> REVIEW -> METADATA -> READY_TO_PUBLISH) und Review-Policies.
- `scripts/run_content_production_pipeline.py`: Führt die lokalen Stages dedupliziert und idempotent aus.
- `scripts/publish_youtube_package.py` / `providers/youtube_provider.py`: Übernimmt das fertige Package und veröffentlicht es sicher (idempotent, keine lokalen Secrets).

Fehlende Verbindungen (Gaps):
1. **KANAL WÄHLEN (Trigger)**: Die Courier-Engine (Cannon) nutzt aktuell `demo/goal_template.json` (mit Fake-Tasks wie `task-generate`). Es fehlt ein echtes `goal_template.json`, das Tasks erzeugt, die `run_content_production_pipeline.py` aufrufen.
2. **HUMAN APPROVAL (Gate)**: Die Config verlangt `REQUIRE_EXPLICIT_HUMAN_APPROVAL` vor dem Publish. Aktuell hält der Python-Runner am Ende von `READY_TO_PUBLISH` an, aber es gibt keine Courier-Integration (UI/CLI), die Dennis aktiv um Erlaubnis fragt und bei "Ja" den `publish_youtube_package.py` Task freigibt.
