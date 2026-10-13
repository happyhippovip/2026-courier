# G0 — Daten schützen

Definition of Done für das Gate „Daten schützen“. Owner: Courier Grok. `BUILD_IF_AUTHORIZED = JA`.

Der Gate-Status ist nur `NOT TESTED` oder `TEST PASSED`. Ein anderer Wortlaut, einschließlich eines unabhängigen Abnahmesiegels, ist kein G0-Status. `gate_status(True)` liefert `TEST PASSED`. Jeder andere Eingabewert bleibt `NOT TESTED`.

## Backup-Manifest

`build_manifest(root, paths)` schreibt für jede lesbare Datei unter `root`:

- `path` — relativer Pfad, ohne `..` und ohne absoluten Pfad
- `size` — Bytezahl
- `sha256` — SHA-256, 64 kleine Hex-Zeichen

Schema: `courier.g0.backup_manifest/v1`. Eine fehlende oder nicht lesbare Quelle bekommt `size: null` und `sha256: null` und gilt damit nicht als gesichert.

## Hash-Prüfung

`check_manifest(root, manifest)` vergleicht jede Manifestzeile mit der Datei:

| Lage | Ergebnis |
|---|---|
| Größe und SHA-256 stimmen | Beitrag zu `PASS` |
| Größe oder SHA-256 weicht ab | `FAIL` |
| Datei fehlt | `FAIL` |
| Pfad unsicher, kein regulärer File, Hash oder Größe unbrauchbar, leeres Manifest | `UNKNOWN` |

`PASS` gibt es nur, wenn jede Zeile stimmt. `UNKNOWN` wird nicht zu `PASS`. Ein `FAIL` in derselben Prüfung bleibt `FAIL`.

## Löschen

`deletion_plan(root, candidates, approvals)` löscht nichts. Jeder Kandidat hat `action: DRY_RUN`. `approved` ist nur wahr, wenn genau dieser relative Pfad in `approvals` steht und unter `root` bleibt. Eine Freigabe für `a.txt` gilt nicht für `a.txt.bak`. `*` ist keine Freigabe. `deleted` bleibt leer.

## Nachweis

```
python3 -m pytest -q tests/test_g0_protect.py
```

Modul: `courier_core/g0_protect.py`. Solange dieser Lauf nicht ausgeführt ist, bleibt der Status `NOT TESTED`.
