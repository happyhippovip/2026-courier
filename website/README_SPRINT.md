# Website-Vorschau

`website/src/` ist die Quelle. `./build_site.sh` schreibt `website/public/`.
Diese Datei gehört nicht ins Deploy-Artefakt.

Öffentlich ausliefern tut nur der manuelle Workflow
`Deploy Courier Website to GitHub Pages` (`workflow_dispatch`).
Ein Push auf den Vorschau-Zweig prüft den Build und lädt ihn als Artefakt hoch.
Er schaltet die Domain nicht.

## Was die alte Notiz falsch sagte

`website/` fehlt nicht mehr auf `integration/v1`.
Die Apex-Adressen `185.199.108.109/110/111` sind nicht die GitHub-Pages-Ziele.
Zum Vergleich, nicht zum blinden Setzen, nennt GitHub Pages diese IPv4-Adressen:
`185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.

Diese Datei ändert kein DNS und keine Mail-Records (MX, SPF, DKIM, DMARC).
`couriersymphony.de` zeigt weiter die reservierte STRATO-Seite. Das ist nicht live.

## Lokal ansehen

```sh
cd website && ./build_site.sh && python3 lounge_relay.py
```

Dann `http://127.0.0.1:8765/` . Die letzte Laterne lässt sich auch ohne Relay öffnen:
Name, eine von drei Figuren, dann der eine Raum. Ohne Relay ist niemand sonst da.
Das Relay hört nur auf `127.0.0.1` und ist kein öffentlicher Chat.
