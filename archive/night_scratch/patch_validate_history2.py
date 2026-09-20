import sys

content = open("scripts/agent_handoff_ledger.py").read()

bad = """                    if url in historical_evidence:
                        # Replayed or copied proof
                        old_e = historical_evidence[url]
                        if old_e["evidence_sha"] != e["evidence_sha"]:
                            raise LedgerError(f"copied proof: URL {url} was historically bound to SHA {old_e['evidence_sha']} but is now claimed for {e['evidence_sha']}")
                        if old_e["runtime_binding"] != e["runtime_binding"]:
                            raise LedgerError(f"copied proof: URL {url} was historically bound to runtime {old_e['runtime_binding']} but is now claimed for {e['runtime_binding']}")
                        if old_e["validity"] != e["validity"]:
                            raise LedgerError(f"replayed proof validity tampering: URL {url}")"""

good = """                    if url in historical_evidence:
                        # Replayed or copied proof
                        old_e = historical_evidence[url]
                        if old_e["evidence_sha"] != e["evidence_sha"]:
                            raise LedgerError(f"copied proof: URL {url} was historically bound to SHA {old_e['evidence_sha']} but is now claimed for {e['evidence_sha']}")
                        if old_e["runtime_binding"] != e["runtime_binding"]:
                            raise LedgerError(f"copied proof: URL {url} was historically bound to runtime {old_e['runtime_binding']} but is now claimed for {e['runtime_binding']}")"""

content = content.replace(bad, good)
open("scripts/agent_handoff_ledger.py", "w").write(content)
