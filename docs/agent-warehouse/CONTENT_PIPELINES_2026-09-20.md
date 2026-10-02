# Content Pipelines — YouTube / TikTok

Date: 2026-09-20  
Status: code-backed inventory + product handoff

## Repository evidence

Die bestehende Codebasis enthält `scripts/run_content_production_pipeline.py` mit expliziten Produktionsstufen.

Dort sind u. a. diese Pfade beschrieben:

### FruitKI / YouTube

```
IDEA
-> SCRIPT
-> ASSET_SELECTION
-> VIDEO_BUILD
-> REVIEW
-> METADATA
-> READY_TO_PUBLISH
```

### 3D-KI / TikTok

```
IDEA
-> HOOK
-> SCRIPT
-> 3D_ASSET_OR_SCENE
-> VERTICAL_VIDEO_BUILD
-> REVIEW
-> CAPTION_HASHTAGS
-> READY_TO_PUBLISH
```

Das Repository enthält außerdem ein Production Artifact Manifest Schema für YouTube/TikTok-Artefakte.

## Wichtige Trennung

**READY_TO_PUBLISH ist nicht dasselbe wie veröffentlicht.**

Das bestehende Dashboard benennt öffentliche Social-Uploads als gesperrten/freigabepflichtigen Bereich. Diese Trennung sollte erhalten bleiben:

- lokale/automatisierte Produktion: möglich;
- Review: erforderlich;
- öffentliches Publishing: nur mit explizitem passenden Gate.

## Productization

Die Pipeline kann später als Courier-Fähigkeit angeboten werden:

"Erzeuge aus diesem Ziel eine Content-Serie."

Courier kann:
- Themen planen;
- Skripte vorbereiten;
- Assets/Scenes erzeugen oder auswählen;
- Videos bauen;
- Metadaten/Caption/Hashtags erzeugen;
- Review-Pakete erstellen;
- Publish-ready Artefakte archivieren.

## Agent Warehouse

Für jede Produktion sollten persistent abgelegt werden:

- project_id
- goal_id
- content_item_id
- platform
- stage
- input references
- generated artifacts
- hashes
- review result
- rights/source metadata
- publish approval state
- final publish URL (falls später freigegeben)
- timestamps
- cost metadata

## Rechte / Anti-Copy

Die allgemeine Idee einer Content-Pipeline ist nicht exklusiv monopolisierbar. Schützbar bzw. kontrollierbar sind jedoch insbesondere die konkrete eigene Software, Dokumentation, Datenbank, Workflows, Assets, Texte, Marken, vertrauliches Know-how und ggf. weitere Rechte.

Deshalb keine internen Produktionsdetails, Credentials, Accounttokens oder nicht öffentliche Wettbewerbsvorteile in öffentliche Marketingtexte übernehmen.
