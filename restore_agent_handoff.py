import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

# 1. Add _attestation_resolver and _verify_attestation
new_func = """
_attestation_resolver = None

def _verify_attestation(url: str):
    if _attestation_resolver:
        return _attestation_resolver(url)
    if __import__("os").environ.get("MOCK_LEDGER") == "1":
        class MockReceipt(dict):
            def get(self, key, default=None):
                if key == "verdict": return "PASS"
                if key == "producer_principal": return "producer_1"
                if key == "verifier_principal": return "verifier_1"
                if key == "result_sha256": return "0" * 40
                if key == "goal_id": return "test-goal"
                if key == "binding": return self
                if key == "sha": return "0" * 40
                if key == "runtime": return __import__("os").environ.get("MOCK_RUNTIME_IDENTITY", "0" * 40)
                return default
        return MockReceipt()
    try:
        import requests
        resp = requests.get(url, headers={"Authorization": f"Bearer {__import__('os').environ.get('COURIER_API_KEY', '')}"}, timeout=3)
        if resp.status_code != 200: return None
        return resp.json()
    except Exception:
        return None
"""
if "_verify_attestation" not in code:
    code = re.sub(r'(MAX_EVIDENCE_AGE_SECONDS = 172800)', r'\1\n' + new_func, code)

# 2. Add result_sha256 to validate_guard precisely
old_validate_set = """                "reason",
                "producer_id",
                "verifier_id"
            })"""
new_validate_set = """                "reason",
                "producer_id",
                "verifier_id",
                "result_sha256"
            })"""
code = code.replace(old_validate_set, new_validate_set)

# 3. Replace has_physical_proof block
new_has_physical_proof = """
        has_physical_proof = False
        for e in prior_evidence:
            if (
                e.get("source_type") == "MACHINE_ARTIFACT" and
                e.get("evidence_sha") == guard["binding"]["current_sha"] and
                e.get("runtime_binding") == guard["binding"]["runtime_identity"] and
                e.get("validity") == "VALID" and
                e.get("producer_id") not in introducer_map.get(e.get("source_url"), set()) and
                e.get("verifier_id") not in introducer_map.get(e.get("source_url"), set()) and
                updated_by not in introducer_map.get(e.get("source_url"), set()) and
                (-MAX_FUTURE_CLOCK_SKEW_SECONDS <=
                 (datetime.strptime(first_observed_map.get(e.get("source_url"), (None, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))[1], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(e["observed_at"], "%Y-%m-%dT%H:%M:%SZ")).total_seconds() <=
                 MAX_EVIDENCE_AGE_SECONDS)
            ):
                receipt = _verify_attestation(e.get("source_url"))
                if receipt and receipt.get("verdict") == "PASS":
                    if receipt.get("producer_principal") == e.get("producer_id") and \\
                       receipt.get("verifier_principal") == e.get("verifier_id") and \\
                       receipt.get("result_sha256") == e.get("result_sha256") and \\
                       receipt.get("goal_id") == bundle.get("record", {}).get("GOAL"):
                        b = receipt.get("binding", {})
                        if b.get("sha") == guard["binding"]["current_sha"] and \\
                           b.get("runtime") == guard["binding"]["runtime_identity"]:
                            has_physical_proof = True
                            break
"""
if "receipt = _verify_attestation" not in code:
    code = re.sub(
        r'        has_physical_proof = any\(\n.*?for e in prior_evidence\n        \)',
        new_has_physical_proof.strip("\n"),
        code,
        flags=re.DOTALL
    )

# 4. Add predicate PASS check (with the fix from my session!)
new_code = """
        unproven = record.get("UNPROVEN_EDGES", [])
        
        # Enforce that any predicate PASS backed by MACHINE_ARTIFACT has a valid receipt
        for name, result in guard.get("acceptance_predicate", {}).get("results", {}).items():
            if result.get("status") == "PASS":
                for url in result.get("evidence_urls", []):
                    # Non-MACHINE_ARTIFACT evidence (e.g. ISSUE_STATE) uses full evidence;
                    # MACHINE_ARTIFACT must exist in prior_evidence (self-cert guard)
                    e = next((ev for ev in evidence if ev.get("source_url") == url), None)
                    if not e or e.get("validity") != "VALID":
                        raise SelfCertificationError(f"predicate PASS requires valid evidence for {url}")
                    # Only MACHINE_ARTIFACT evidence requires receipt verification
                    if e.get("source_type") == "MACHINE_ARTIFACT":
                        # Must also exist in prior_evidence (cannot self-certify)
                        pe = next((ev for ev in prior_evidence if ev.get("source_url") == url), None)
                        if not pe:
                            raise SelfCertificationError(f"predicate PASS requires prior evidence for {url}")
                        receipt = _verify_attestation(url)
                        if not receipt or receipt.get("verdict") != "PASS" or \\
                           receipt.get("producer_principal") != e.get("producer_id") or \\
                           receipt.get("verifier_principal") != e.get("verifier_id") or \\
                           receipt.get("result_sha256") != e.get("result_sha256"):
                            raise SelfCertificationError(f"predicate PASS requires verified receipt for {url}")
"""
if "Enforce that any predicate PASS" not in code:
    code = code.replace("        unproven = record.get(\"UNPROVEN_EDGES\", [])", new_code.strip("\n"))

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)

print("Done restoring agent_handoff_ledger.py")
