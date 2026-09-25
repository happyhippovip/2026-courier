import os
import sys
import keyring
import logging

def get_secret(name, required=False):
    val = None
    if os.environ.get('DISABLE_KEYRING') != '1':
        services = ['courier', 'courier_worker']
        for service in services:
            try:
                v = keyring.get_password(service, name)
                if v: 
                    val = v
                    break
            except Exception:
                pass
            try:
                v = keyring.get_password(service, name.upper())
                if v: 
                    val = v
                    break
            except Exception:
                pass
    if not val:
        val = os.environ.get(f'COURIER_{name.upper()}')
        
    if val:
        # reject known placeholders
        if val in ('dev-secret-key', 'test-api-key', 'placeholder', 'changeme'):
            # Allow test-api-key ONLY if in a test environment (e.g. pytest)
            if 'pytest' not in sys.modules and os.environ.get('PYTEST_CURRENT_TEST') is None:
                print(f"[FATAL] Default/placeholder secret detected for {name}. This violates permanent credential policy.")
                sys.exit(1)
                
    if required and not val:
        print(f"[FATAL] Missing required secure credential: {name}. Cannot start without it. Value must not be printed.")
        sys.exit(1)
        
    return val

class RedactingStream:
    def __init__(self, stream, secrets):
        self.stream = stream
        self.secrets = [s for s in secrets if s]

    def write(self, s):
        is_bytes = isinstance(s, bytes)
        for sec in self.secrets:
            if is_bytes:
                sec_bytes = sec.encode('utf-8')
                s = s.replace(sec_bytes, b'[REDACTED_SECRET]')
            else:
                s = s.replace(sec, '[REDACTED_SECRET]')
        self.stream.write(s)
        
    def flush(self):
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

class RedactingFormatter(logging.Formatter):
    def __init__(self, orig_formatter, secrets):
        self.orig_formatter = orig_formatter
        self.secrets = [s for s in secrets if s]
        
    def format(self, record):
        msg = self.orig_formatter.format(record) if self.orig_formatter else record.getMessage()
        for sec in self.secrets:
            msg = msg.replace(sec, '[REDACTED_SECRET]')
        return msg

def apply_redaction(secrets):
    sys.stdout = RedactingStream(sys.stdout, secrets)
    sys.stderr = RedactingStream(sys.stderr, secrets)
    
    for handler in logging.root.handlers:
        orig_formatter = handler.formatter
        handler.setFormatter(RedactingFormatter(orig_formatter, secrets))
