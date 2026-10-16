"""Legal guard: checks every outward text BEFORE a human approves and sends it.

Courier gives no legal advice and never sends on its own. This guard only
blocks the mistakes that most often turn a helpful message into a problem:
misleading absolute claims, fear/urgency that reads like a scam, third-party
brands, secret values, unsolicited advertising, public disclosure of a secret,
and a sales pitch inside a first security notice. An empty result means "no
known problem found" - a human still decides.
"""
import re

ABSOLUTE_CLAIMS = [r"\bgr(ö|oe)(ß|ss)te[nrs]?\b", r"\bbeste[nrs]? der welt\b", r"\bbest in the world\b",
                   r"\b(world'?s|weltweit) (best|beste|größte|biggest|largest)\b", r"\b100\s?% (sicher|secure|safe)\b",
                   r"\bgarantiert\b", r"\bguarantee[ds]?\b", r"\bunhackbar\b", r"\bunhackable\b", r"\bnumber one\b",
                   r"\bnummer (1|eins)\b"]
FEAR = [r"\bsofort handeln\b", r"\bact now\b", r"\bletzte chance\b", r"\blast chance\b",
        r"\b(konto|wallet|funds?|gelder?) (ist |sind |are |is )?(in gefahr|at risk)\b", r"\bbevor es zu spät ist\b",
        r"\bbefore it'?s too late\b", r"\bdringend\b", r"\burgent\b"]
BRANDS = ["binance", "coinbase", "kraken", "metamask", "trust wallet", "bybit", "okx", "bitpanda", "trezor",
          "ledger live", "ledger nano"]
SECRETS = [r"\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}\b", r"\bAKIA[0-9A-Z]{16}\b", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
           r"\bsk-[A-Za-z0-9]{32,}\b", r"\b0x[0-9a-fA-F]{64}\b"]
PITCH = [r"€", r"\beur\b", r"\bpreis\b", r"\bprice\b", r"\bangebot\b", r"\boffer\b", r"\bkaufen\b", r"\bbuy\b"]
LEGAL_ADVICE = [r"\brechtsberatung\b", r"\blegal advice\b", r"\b(ihr seid|ihr habt|seid ihr|habt ihr)\b.{0,20}\b(haftbar|rechtlich)\b",
                r"\byou are (legally )?liable\b"]

# first contact is allowed only where the other side invited it
CHANNELS = {
    "security_contact": "their SECURITY.md / security.txt / private vulnerability report",
    "reply": "they wrote to us first",
    "existing_customer": "an existing customer relationship",
    "cold_email": "unsolicited e-mail/DM to someone without consent",
    "public_issue": "a public issue or comment",
}


def _hits(patterns, text):
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]


def check_outward(text, channel, finding_is_secret=False, human_approval=None):
    """Problems that block sending. [] = no known problem; a human still approves."""
    if channel not in CHANNELS:
        return [f"unknown channel {channel!r}; use one of {sorted(CHANNELS)}"]
    problems = []
    if _hits(ABSOLUTE_CLAIMS, text):
        problems.append("absolute claim (best/biggest/guaranteed/100% secure) - not provable, counts as misleading")
    if _hits(FEAR, text):
        problems.append("fear or urgency wording - reads like a scam message; state the fact calmly")
    brands = [b for b in BRANDS if b in text.lower()]
    if brands:
        problems.append(f"third-party brand named ({', '.join(brands)}) - never imply partnership or use their marks")
    if _hits(SECRETS, text):
        problems.append("secret-shaped value in the text - never quote a key, name only file and type")
    if _hits(LEGAL_ADVICE, text):
        problems.append("reads as legal advice - Courier does not give legal advice")
    if channel == "cold_email":
        problems.append("unsolicited advertising without consent - use their security contact or wait for a reply")
    if channel == "public_issue" and finding_is_secret:
        problems.append("a leaked secret must be reported privately, never in a public issue")
    if channel in ("security_contact", "public_issue") and _hits(PITCH, text):
        problems.append("a first security notice must not contain a sales offer - help first, offer only if they reply")
    if not human_approval:
        problems.append("needs a human approval id before sending")
    return problems
