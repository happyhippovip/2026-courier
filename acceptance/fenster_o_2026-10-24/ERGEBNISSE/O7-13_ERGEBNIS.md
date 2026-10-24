# O7-13 · G1 · WQ-1b_v2 ohne done_prs/open_pr_files · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a`; zusätzlich WQ-1b v2 `claude/v38-wq1b` = `a2a6dfabd` |
| Testdatei | `O7-13_test_feed_drops_pr_context.py` · sha256 `caac57b297bf1191a04bc5ded5ddb8487ccbc937d6ed7c06401ca1bf32a5e693` |
| Marker | 2 × `xfail(strict=True, raises=AssertionError)` + 1 Schutztest |
| Lauf auf Basis | `1 passed, 2 xfailed`, Exit 0. Auf WQ-1b v2 ebenso: `1 passed, 2 xfailed` |
| `--runxfail` | open PR: `claimed ['WK1'] == ['WK2']` schlägt fehl; done PR: `outcome 'idle', claimed []` |
| Kosten | 0 €, nur Dateien |

## Zeilenprüfung (Katalog-Angabe „queue_feed.py Z. 90/179/203“)
- Die Angaben stimmen für **WQ-1b v2** (`a2a6dfabd`): `:90` `list_ready(now=now)` in `has_open_work`, `:179` `list_ready(now=now)`, `:203` `claim(…, announce=True)`. Keine dieser Stellen übergibt `done_prs`/`open_pr_files`.
- Auf der **Basis** steht derselbe Defekt in anderen Zeilen: `courier_worker/queue_feed.py:77`, `:137`, `:139`. **WQ-1b v2 hat ihn nicht eingeführt, sondern übernommen.**

## Befund (VERIFIED)
- `courier_core/work_queue.py` berücksichtigt beides (`list_ready` `:71-89`, `claim` `:90-112`, `_deps_met` `:635-644`, `_blocked_by_scope` `:647-656`, CLI `--done-pr`/`--open-pr-file`). Schutztest: passed.
- Der automatische Feed hat **keinen Kanal** für diese Werte. Folgen:
  1. Ein Item, dessen Scope eine offene PR überlappt, wird trotzdem beansprucht (Scope-Kollision mit fremder Arbeit).
  2. Ein Item mit `depends_on` auf eine gemergte PR wird nie READY und deshalb nie gefüttert.

## Annahme für den Fix (Owner entscheidet)
Die Tests nehmen an, dass `work_queue_feed.json` die Felder `done_prs` und `open_pr_files` trägt und dass der Feed sie an `list_ready`/`claim`/`has_open_work` weitergibt. Bei einer anderen Schnittstelle (z. B. einem Probe-Callback) bleibt die Assertion gleich, nur das Setup ändert sich.
sha256: 9254ffb96406734d96421614e8b700571c5b2ef13eed80dd648681f26851b128
