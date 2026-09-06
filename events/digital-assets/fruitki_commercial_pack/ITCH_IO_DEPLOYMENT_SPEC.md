# Itch.io Zero-Spend Commercial Deployment Specification
**Product:** FruitKI 3D Animated Character Commercial Pack  
**Archive:** `events/digital-assets/dist/FruitKI_3D_Commercial_Pack_v1.0.0.zip` (SHA-256: `ff71c4e7469fbe32ac7e71bc6f331e9f11ba1bca0915f749b91eb6d6b96cf801`)  
**Pricing:** $19 (Royalty-Free Commercial License)  

---

## 1. Butler CLI Automated Deployment (Zero Human GUI Friction)
When Butler CLI or Itch API key is authenticated:
```bash
# Push release build directly to itch.io channel
butler push events/digital-assets/dist/FruitKI_3D_Commercial_Pack_v1.0.0.zip happyhippovip/fruitki-3d-commercial-pack:godot-release
```

---

## 2. Direct Web Store Listing Metadata
- **Cover Image:** `events/opportunity-queue/work-fruitki-catalog-enrichment.json`
- **Engine Tags:** Godot 4.x, GL Compatibility, OpenGL 3
- **File Contents:** 12 3D Character Rigs, 30 Animations, PBR Textures, License Agreement
