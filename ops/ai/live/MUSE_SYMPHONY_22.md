# Family 22 — cost admission (READ_ONLY_C2)

FAMILY=22
STATUS=FAMILY_COMPLETE
SUBCASES_DONE=5 (22.1 cheaper worker active; 22.2 cheaper worker silent crash stall; 22.3 cheaper worker unqualified mismatch; 22.4 cheaper worker busy skip; 22.6 default target routing)

CONFIRMED_SOURCE_DEFECTS=1 (22.2 Cost Admission Head-of-Line Stall)
EVIDENCE_GAPS=0
DISPROVEN=0
NO_ISSUE=22.1 (Wenn ein günstiger Worker da ist, wird der teure korrekt abgelehnt und der Task bleibt QUEUED); 22.3 (Wenn der günstige Worker nicht die nötigen `capabilities` hat, blockiert er den teuren nicht); 22.4 (Wenn der günstige Worker busy `available=False` ist, blockiert er den teuren nicht); 22.6 (Fehlender `target_agent` fällt sicher auf `linux` zurück).

## Fix Packets

**FIX_PACKET 22.2 (Cost Admission Head-of-Line Stall):**
FILES=server/app.py (claim_task)
BUG=Wenn ein günstigerer Worker registriert, qualifiziert und `available=True` ist, aber lautlos crasht (oder extrem langsam pollt), blockiert er alle teureren Worker für volle 5 Minuten, da das Timeout `now - other_w.get("last_seen", 0) > 300` beträgt. Während dieser 5 Minuten stagniert die gesamte Pipeline, da niemand den Task claimt.
MIN_FIX=Das Timeout für die Cost-Admission-Blockade (den `last_seen` Check in Zeile 325) aggressiv reduzieren, z.B. auf `30` Sekunden anstatt `300` Sekunden. Alternativ: Eine echte Worker-Queue / Preemption einbauen.
MIN_TEST=Teuren Worker und günstigen Worker starten. Günstigen Worker stoppen (ohne unregister). Assert: Nach 31 Sekunden kann der teure Worker den Task erfolgreich claimen.
OWNER=WINDOWS_CENTRAL_WRITER
LATER (Blockiert nicht direkt die Sicherheit des RUN_1 oder RUN_2 Idempotenz-Beweises, aber erzeugt im Langzeitbetrieb heftige Latenz-Spikes).
