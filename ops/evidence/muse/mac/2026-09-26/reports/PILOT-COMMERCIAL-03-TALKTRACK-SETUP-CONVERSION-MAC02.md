# PILOT-COMMERCIAL-03 — talk-track + day-0 setup + demo-to-pilot conversion

WORKER=MAC-02 (MUSE) · HOST=MAC · MODE=NON_CODE_PREP · 2026-09-26
Complements: SIGNUP flow (MAC-21, the 3 steps — this file is the WORDS for
those steps, not a second flow), RV11 (machine prep), RV18 (acceptance test),
landing HONEST LIMITS (my WALL-P2-LANDING-STRUCTURE), demo storyboard (my
WALL-P2-DEMO-STORYBOARD). No new process invented.

## ONBOARDING_SCRIPT (operator talk-track, ~10 min call; [S1/2/3] = SIGNUP steps)
Open: "Ich zeige Ihnen in zehn Minuten, was das System heute kann und was
nicht. Danach entscheiden Sie, ob wir einen abgegrenzten Versuch starten.
[S1] Welche Aufgabe frisst morgens am meisten Zeit?" → run B1–B6 (file 01),
write answers down where the customer sees them.
"Das ist die These, die wir prüfen: dass Sie morgens weniger als [B2] Minuten
brauchen. Wenn das nicht eintritt, ist der Pilot gescheitert — und das ist
dann das ehrliche Ergebnis." [S2] "Jetzt lasse ich den Test vor Ihren Augen
laufen. Dauert zwei Minuten. Wenn irgendwo FEHLER steht, hören wir auf, und
der Fehlerbericht gehört Ihnen." → run RV18 witnessed. On PASS: [S3] "Der
Test ist bestanden. Das heißt nur: DIESE Aufgabenform funktioniert. Jetzt
grenzen wir Ihren Versuch ab: welcher Ordner, welche Aufgaben, was darf nie
passieren, wer kann Stopp sagen." → fill agreement inputs (file 02).
Close: "Sie bekommen zu jeder Aufgabe eine Prüfkarte. Leere Versprechen gibt
es nicht — nur gezählte Karten." Forbidden sentences on this call: "voll
autonom", "KI versteht Ihre Arbeit", "das skaliert dann", any timeframe
beyond the 2-week window.

## SETUP_CHECKLIST (day 0, operator-owned, ~30 min with customer watching)
1. Machine matches RV11 prep realities (Python 3.9+, git present; state/log
locations shown to customer; keychain-free config path confirmed — never
assume, always check).
2. Two API keys set (env), verifier key ≠ worker key (PRIVACY-DATAFLOW
method); server refuses insecure defaults — show the refusal once, it builds
more trust than any claim.
3. Scope handshake written (agreement inputs, file 02) BEFORE first run.
4. RV18 witnessed → PASS printed → witnessed proof card delivered (first
free artifact). On FAIL: RV13 incident card, stop, no invoice.
5. First scoped task runs; proof card #1 delivered same day. Customer knows
where cards land and how to read HUMAN_INTERVENTIONS.

## DEMO_TO_PILOT_CONVERSION_FLOW (after the 60s demo or live MM7 beats)
1. LAND: demo ends on the relay counter (HUMAN_RELAYS=0, counted) + the
hash-caveat overlay (storyboard 00:23–00:32). Never end on hype.
2. QUALIFY (one question): "Gibt es bei Ihnen eine Aufgabe wie diese —
wiederkehrend, mit prüfbarem Ergebnis?" NO → give the honest-limits block,
part friendly. YES → continue.
3. WITNESS: run RV18 live (not the recording). Recording convinces; only the
witnessed run converts.
4. BASELINE: B1–B6 on the spot (15 min). No baseline → no pilot (unmeasurable
promise is not offered).
5. AGREE: one-page agreement inputs, signed. 6. RUN day-0 setup above.
Conversion metric (MAC10 experiment feeds): record at which step each prospect
stops — the step with most drop-offs is the product gap, not a sales problem.

STATUS=PACK COMPLETE (01+02+03) · all 15 mission items now covered across
MAC-02 + sibling reports · no capability claimed beyond GM5/E-probes/RV18-shape
