# O7-14 · G2 · rejected ohne Status wird endlos erneuert (queue_feed) · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a`; zusätzlich WQ-1b v2 `a2a6dfabd` |
| Testdatei | `O7-14_test_feed_renews_rejected_forever.py` · sha256 `d1d03b1c67339924e9cc74f5dacbf94e3f85ab3ec87c7b234d694893279c8290` |
| Marker | `xfail(strict=True, raises=AssertionError)` |
| Lauf | Basis: `1 xfailed`, Exit 0; WQ-1b v2: `1 xfailed`. Mit `--runxfail`: `{'WK1': 'CLAIMED', 'WK2': 'READY'}, 2 RENEW` |
| Kosten | 0 €, echter Feed und echte Bridge, ablehnender Fake-Controller |

## Zeilenprüfung (Katalog „queue_feed.py Z. 157–176“)
- Stimmt für **WQ-1b v2** (`a2a6dfabd`): Die Renew-Schleife steht in `:150-176`. `park` gibt es dort **nur** für `status in ("ERROR", "BLOCKED")` (`:162-168`).
- Auf der **Basis**: `courier_worker/queue_feed.py:123-134`. Dort gibt es kein `park`; jeder nicht-FINAL_DONE-Workkey wird erneuert (`:133`).

## Befund (VERIFIED)
Lehnt der Controller ab (400), behält die Mission `posted=False` und bekommt **keinen** Status (`scripts/ledger_v1_bridge.py:366-369`, siehe O7-15). Weder FINAL_DONE noch ERROR/BLOCKED greifen, deshalb erneuert der Feed die Lease bei jedem Durchlauf. WK1 bleibt dauerhaft `CLAIMED`, WK2 wird nie gefüttert. Das betrifft beide Stände; das `park` aus WQ-1b v2 allein behebt es nicht.

## Fix-Abhängigkeit
Erst der R1-Fix in der Bridge (BLOCKED-Stempel bei 4xx außer 409, O7-15) macht das `park` von WQ-1b v2 wirksam. Dann wird dieser Test auf WQ-1b v2 XPASS, und das xfail ist zu entfernen (C1-17). Auf der Basis braucht es zusätzlich das `park` aus WQ-1b v2.
sha256: a9394e3e5d93cd9f002563a844724c4e82354a5f199f120baccc3786f4c65e8d
