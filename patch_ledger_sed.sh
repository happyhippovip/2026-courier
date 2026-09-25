sed -i '' '810i\
                        print("COND1", receipt.get("producer_principal"), e.get("producer_id"))\
                        print("COND2", receipt.get("verifier_principal"), e.get("verifier_id"))\
                        print("COND3", receipt.get("result_sha256"), e.get("result_sha256"))\
                        print("COND4", receipt.get("goal_id"), bundle.get("record", {}).get("GOAL"))\
                        b = receipt.get("binding", {})\
                        print("COND5", b.get("sha"), guard["binding"]["current_sha"])\
                        print("COND6", b.get("runtime"), guard["binding"]["runtime_identity"])
' scripts/agent_handoff_ledger.py
