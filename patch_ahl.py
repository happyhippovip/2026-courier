with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    '''has_physical_proof = True
                            break''',
    '''has_physical_proof = True
                            logger.error(f"DEBUG: SET has_physical_proof=True for {e.get('source_url')}")
                            break
                        else:
                            logger.error(f"DEBUG: binding mismatch: {b} != {guard['binding']}")
                    else:
                        logger.error(f"DEBUG: field mismatch. receipt={receipt}, e={e}, goal={bundle.get('record', {}).get('GOAL')}")
                else:
                    logger.error(f"DEBUG: missing/failed receipt: {receipt}")
            else:
                logger.error(f"DEBUG: loop condition failed for {e.get('source_url')}: type={e.get('source_type')} val={e.get('validity')}")
'''
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
