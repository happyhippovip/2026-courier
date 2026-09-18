import sys
content = open("tests/test_agent_handoff_ledger.py").read()

content = content.replace(
'''            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            b2 = ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "worker1", 1.0, landed)''',
'''            landed["evidence"][0]["validity"] = "STALE"
            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            b2 = ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "worker1", 1.0, landed)''')

content = content.replace(
'''            landed2["binding"]["current_sha"] = "b"*40
            
            with self.assertRaisesRegex(ledger_module.LedgerError, "copied proof: URL https://github.com/example/project/actions/runs/99 was historically bound to SHA"):
                ledger_module.update(ledger, b2["revision"], {"CURRENT_SHA": "b"*40}, "worker2", 1.0, landed2)''',
'''            landed2["evidence"][0]["validity"] = "STALE"
            landed2["evidence"][1]["validity"] = "STALE"
            landed2["binding"]["current_sha"] = "b"*40
            
            with self.assertRaisesRegex(ledger_module.LedgerError, "copied proof: URL https://github.com/example/project/actions/runs/99 was historically bound to SHA"):
                ledger_module.update(ledger, b2["revision"], {"CURRENT_SHA": "b"*40}, "worker2", 1.0, landed2)''')

content = content.replace(
'''            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            # The updater is "caller", which matches producer_id -> Self-certification!
            with self.assertRaisesRegex(ledger_module.LedgerError, "caller-created or self-certifying MACHINE_ARTIFACT evidence rejected"):
                ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "caller", 1.0, landed)''',
'''            landed["evidence"][0]["validity"] = "STALE"
            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            # The updater is "caller", which matches producer_id -> Self-certification!
            with self.assertRaisesRegex(ledger_module.LedgerError, "caller-created or self-certifying MACHINE_ARTIFACT evidence rejected"):
                ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "caller", 1.0, landed)''')

content = content.replace(
'''            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            with self.assertRaisesRegex(ledger_module.LedgerError, "evidence produced by the acceptance decision path itself or uses arbitrary strings"):
                ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "worker", 1.0, landed)''',
'''            landed["evidence"][0]["validity"] = "STALE"
            landed["binding"]["current_sha"] = "a"*40
            landed["binding"]["runtime_identity"] = "runtime-a"
            with self.assertRaisesRegex(ledger_module.LedgerError, "evidence produced by the acceptance decision path itself or uses arbitrary strings"):
                ledger_module.update(ledger, bundle["revision"], {"CURRENT_SHA": "a"*40, "RUNTIME_IDENTITY": "runtime-a"}, "worker", 1.0, landed)''')

open("tests/test_agent_handoff_ledger.py", "w").write(content)
