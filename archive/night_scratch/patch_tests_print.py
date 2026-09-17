import sys
content = open("tests/test_agent_handoff_ledger.py").read()
content = content.replace(
'''            landed2["binding"]["current_sha"] = "b"*40
    
            with self.assertRaisesRegex''',
'''            landed2["binding"]["current_sha"] = "b"*40
            landed2["binding"]["runtime_identity"] = "runtime-a"
            print([e["source_url"] for e in landed2["evidence"]])
            
            with self.assertRaisesRegex''')
open("tests/test_agent_handoff_ledger.py", "w").write(content)
