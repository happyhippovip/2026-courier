# R-127 · Doku `docs/EMAIL_SENDER_POLICY.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `4646043923aea777793f2a26500d78377999fb80cd0ec10d9ffab1c2f207f931`, 23 Zeilen, letzter Commit 2026-09-16.

| Aussage | Zeile | Urteil | Beleg |
|---|---|---|---|
| Betroffenes Konto = Absender, nie ersatzweise ein anderes; bei Unklarheit nicht senden | 3-13 | **gültig** | Deckt sich mit V7 „extern posten/senden VERBOTEN“ |
| Code-Abgleich | – | **kein Versandcode gefunden** | `git grep` nach `smtplib`/`sendmail`/`SMTP(` in `*.py` außerhalb von Tests: leer. `scripts/inbound_response_observer.py` und `scripts/invoice_generator.py` verarbeiten E-Mail-Felder, senden aber nicht. Das habe ich nicht vertieft (R-108/R-112) |
sha256: add9e1d3384df7301fc27588c8ef2083fe1733700de431abb17638bd099277c3
