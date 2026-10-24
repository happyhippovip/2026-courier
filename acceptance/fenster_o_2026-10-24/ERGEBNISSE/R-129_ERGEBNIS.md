# R-129 · Doku `docs/FREEZE_GITHUB_EVIDENCE.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `49bb6dc90b7c9a33f10b410c053c6b9ca849927d71e33b971d0aacba1646dc01`, 12 Zeilen, letzter Commit 2026-10-04.

| Aussage | Zeile | Urteil | Beleg |
|---|---|---|---|
| Freeze verifiziert auf `7004d817` | 4 | **historisch gültig** | `7004d817` ist Vorfahre von `81bbf224` |
| Dateien `courier_worker.yml`, `github_worker_adapter.py`, `integration_contract.py` | 8-10 | **vorhanden, aber nicht mehr eingefroren** | Seit `7004d817` gibt es 11 Commits auf diesen Dateien (7 allein auf `github_worker_adapter.py`, zuletzt #826). Der Freeze-Beleg gilt also nicht für den Trunk-Stand |
| Hosted-Run `35092958584` | 12 | **nicht neu geprüft** | Ein externer Lauf; ich habe ihn nicht erneut ausgeführt (0 €, kein CI-Dispatch) |
sha256: abc2347459f8708b454db325376db72414eae0ca488ffab70b1abc99018d897a
