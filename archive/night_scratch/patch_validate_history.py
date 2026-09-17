import sys
content = open("scripts/agent_handoff_ledger.py").read()

new_logic = """
        # Enforce history boundaries and reject replayed/copied proofs
        historical_evidence = {}
        for h in bundle.get("history", []):
            for e in h.get("acceptance_guard", {}).get("evidence", []):
                historical_evidence[e["source_url"]] = e

        guard_changed = guard != bundle.get("acceptance_guard")
        if guard_changed:
            # Enforce independent producer/verifier boundary
            old_evidence_urls = {e["source_url"]: e for e in bundle.get("acceptance_guard", {}).get("evidence", [])}
            new_evidence = guard.get("evidence", [])
            for e in new_evidence:
                url = e.get("source_url")
                is_new_url = url not in old_evidence_urls
                
                if url in historical_evidence:
                    # It existed in history.
                    old_e = historical_evidence[url]
                    if old_e["evidence_sha"] != e["evidence_sha"]:
                        raise LedgerError(f"copied proof: URL {url} was historically bound to SHA {old_e['evidence_sha']} but is now claimed for {e['evidence_sha']}")
                    if old_e["runtime_binding"] != e["runtime_binding"]:
                        raise LedgerError(f"copied proof: URL {url} was historically bound to runtime {old_e['runtime_binding']} but is now claimed for {e['runtime_binding']}")
                        
                if is_new_url and e.get("source_type") == "MACHINE_ARTIFACT":
                    if updated_by == "Google-Antigravity" or updated_by == e.get("runtime_binding") or updated_by == e.get("producer_id") or updated_by == e.get("verifier_id"):
                        raise LedgerError("caller-created or self-certifying MACHINE_ARTIFACT evidence rejected")
                    if not e.get("producer_id") or not e.get("verifier_id"):
                        raise LedgerError("unverifiable producer or verifier in MACHINE_ARTIFACT evidence")
                    if e["producer_id"] == e["verifier_id"] or e["producer_id"] == "arbitrary" or e["verifier_id"] == "arbitrary":
                        raise LedgerError("evidence produced by the acceptance decision path itself or uses arbitrary strings")
"""

import re
content = re.sub(r'        # Enforce history boundaries and reject replayed/copied proofs.*?raise LedgerError\("evidence produced by the acceptance decision path itself.*?"\)', new_logic.strip(), content, flags=re.DOTALL)

open("scripts/agent_handoff_ledger.py", "w").write(content)
