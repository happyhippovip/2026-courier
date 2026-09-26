# Muse Long-Run Compatibility Entry Point

This path is kept because existing Muse sessions already reference it.

Use the universal mission in:

ops/ai/UNIVERSAL_WALL_LONGRUN_PROMPT.md

Apply these defaults:

PROVIDER=MUSE
HOST=AUTO
ROUND_HOURS=4
TASK_SIZE=LARGE
MODE=READ_ONLY_REPORT

Important corrections versus older wall drafts:

- logical wall size is configurable 1..37
- logical slots are not heavy-process counts
- current resource policy keeps MAX_HEAVY_JOBS=1 unless later proven policy explicitly changes it
- Windows Antigravity remains the only final-candidate source writer
- Muse is READ_ONLY/REPORT_ONLY unless durable coordination explicitly assigns an unowned writer scope
- candidate-b-1 @ 4c1e24ccc522042af826bc4c2b595daf85d097f9 remains the accepted repair base
- candidate-b-2 is rejected
- no account rotation, no busywork, no fake physical proof
- use Ledger/result evidence to avoid duplicate work
- continue after one task only while useful safe authorized work remains

Read the complete universal prompt and execute it.

CONTINUE_BY_DEFAULT=YES
DO_NOT_WAIT_FOR_HUMAN=YES
NO_EVIDENCE_NO_PASS=YES
