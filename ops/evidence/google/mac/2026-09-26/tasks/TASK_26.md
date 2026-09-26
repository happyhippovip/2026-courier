# TASK_26: Confirm Worker-Reported SHA Alone Cannot Produce PASS

STATUS=DONE
NEW_EVIDENCE=scripts/courier_verifier.py:65: verifier recomputes sha = hashlib.sha256(open(art_path, 'rb').read()).hexdigest(). Worker's posted hash is ignored by verifier.
PROVEN=Independent verifier re-reads disk bytes; spoofed worker hash in result payload cannot cause false PASS.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_27
