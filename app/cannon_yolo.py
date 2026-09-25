import os
import re

def has_secret(text: str) -> bool:
    """
    Prüft, ob der Text potenziell sensitive Daten wie API-Keys, Passwörter 
    oder bekannte Environment-Variablen enthält.
    """
    if not isinstance(text, str):
        return False
        
    for key, val in os.environ.items():
        if any(kw in key.upper() for kw in ["KEY", "TOKEN", "SECRET", "PASS", "CREDENTIAL"]):
            if val and len(val) > 4 and val in text:
                return True
            
    # Heuristik für Token-Muster (z.B. ghp_ für GitHub, sk- für OpenAI, AWS, Bearer, PEM, .env)
    patterns = [
        r"ghp_[a-zA-Z0-9]{36}",
        r"sk-[a-zA-Z0-9]{48}",
        r"AIza[0-9A-Za-z-_]{35}",
        r"AKIA[0-9A-Z]{16}",
        r"Bearer\s+[A-Za-z0-9\-\._~+/]+=*",
        r"-----BEGIN [\w\s]+-----[\s\S]*?-----END [\w\s]+-----",
        r"(?i)(?:password|secret|token|key|api|cred)\s*[:=]\s*(?:[\"']?)([a-zA-Z0-9\-\._\+\/]{8,})(?:[\"']?)"
    ]
    for p in patterns:
        if re.search(p, text):
            return True
            
    return False


def redact(text: str) -> str:
    """
    Maskiert Passwörter, API-Keys und andere Secrets im Text.
    """
    if not isinstance(text, str):
        return text
        
    redacted_text = text
    
    for key, val in os.environ.items():
        if any(kw in key.upper() for kw in ["KEY", "TOKEN", "SECRET", "PASS", "CREDENTIAL"]):
            if val and len(val) > 4:
                redacted_text = redacted_text.replace(val, "***REDACTED***")
            
    # Heuristik Patterns maskieren
    patterns = [
        r"ghp_[a-zA-Z0-9]{36}",
        r"sk-[a-zA-Z0-9]{48}",
        r"AIza[0-9A-Za-z-_]{35}",
        r"AKIA[0-9A-Z]{16}",
        r"Bearer\s+[A-Za-z0-9\-\._~+/]+=*",
        r"-----BEGIN [\w\s]+-----[\s\S]*?-----END [\w\s]+-----",
        r"(?i)(password|secret|token|key|api|cred)\s*([:=])\s*(?:[\"']?)([a-zA-Z0-9\-\._\+\/]{8,})(?:[\"']?)"
    ]
    for p in patterns:
        if "password|" in p: # Special handling for assignments to keep the variable name
            redacted_text = re.sub(p, r"\1 \2 ***REDACTED***", redacted_text)
        else:
            redacted_text = re.sub(p, "***REDACTED***", redacted_text)
        
    return redacted_text
