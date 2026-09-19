"""Resolve evidence ONLY through the operator-configured HTTPS Courier authority.

Environment/configuration and the OS TLS trust store belong to the operator,
not TaskPacket/evidence writers. Never follow evidence-selected hosts/redirects.
"""
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from scripts.attestation_contract import MAX_AGE


def authenticated_evidence(evidence, record):
    origin = os.environ.get('COURIER_ATTESTATION_ORIGIN', '').rstrip('/')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        return False
    url = evidence.get('source_url', '')
    if not re.fullmatch(re.escape(origin) + r'/attestations/[0-9a-f]{32}', url):
        return False
    key = os.environ.get('COURIER_API_KEY')
    if not key:
        return False
    try:
        # No environment proxy/netrc substitution or redirect credential forwarding.
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(url, headers={'Authorization': 'Bearer ' + key},
                                   timeout=(3, 5), allow_redirects=False)
            if response.status_code != 200:
                return False
            receipt = response.json()
        observed = datetime.fromtimestamp(receipt['verified_at'], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        now = time.time()
        return bool(
            receipt['attestation_id'] == url.rsplit('/', 1)[1]
            and receipt['goal_id'] == record['GOAL']
            and receipt['binding']['sha'] == evidence['evidence_sha'] == record['CURRENT_SHA']
            and receipt['binding']['runtime'] == evidence['runtime_binding'] == record['RUNTIME_IDENTITY']
            and re.fullmatch(r'courier-server:[0-9a-f]{32}', receipt['binding']['runtime'])
            and receipt['result_sha256'] == evidence.get('result_sha256')
            and receipt['producer_principal'] == evidence.get('producer_id')
            and receipt['verifier_principal'] == evidence.get('verifier_id')
            and receipt['producer_principal'] != receipt['verifier_principal']
            and receipt['verdict'] == 'PASS' and bool(receipt['artifacts'])
            and evidence['observed_at'] == observed
            and 0 <= now - receipt['received_at'] <= MAX_AGE
            and receipt['received_at'] <= receipt['verified_at'] <= now
        )
    except (requests.RequestException, ValueError, KeyError, TypeError, OverflowError):
        return False
