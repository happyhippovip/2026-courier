import sys
content = open("scripts/courier_continue.py").read()
old = '''    capability_map = {
        "LEDGER/HANDOFF": ["git", "file_write"],
        "PR41 ACCEPTANCE": ["git_merge", "code_analysis", "reasoning"],
        "RELEASE": ["shell", "build_tools"],
        "PUBLIC DEPLOYMENT": ["github_actions", "api"],
        "PUBLICATION VERIFICATION": ["http_client"],
        "PILOT INTAKE": ["email_processing"],
        "SALES PACKAGE": ["markdown", "file_write", "reasoning"],
        "FIRST PILOT": ["intake_execution", "reasoning"],
        "PAYMENT ONLY WHEN ACTUALLY REQUIRED": ["payment_mechanism"],
        "POST-PILOT HARDENING": ["refactoring", "testing", "reasoning"]
    }'''

new = '''    capability_map = {
        "LEDGER/HANDOFF": ["git", "file_write"],
        "PR41 ACCEPTANCE": ["git_merge", "code_analysis", "reasoning"],
        "RELEASE - SAFE_AUTOMATABLE_PREPARATION": ["shell", "build_tools"],
        "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION": ["github_actions", "api"],
        "PUBLICATION VERIFICATION": ["http_client"],
        "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION": ["email_processing"],
        "SALES PACKAGE - SAFE_AUTOMATABLE_PREPARATION": ["markdown", "file_write", "reasoning"],
        "FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION": ["intake_execution", "reasoning"],
        "PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION": ["payment_mechanism"],
        "POST-PILOT HARDENING - SAFE_AUTOMATABLE_PREPARATION": ["refactoring", "testing", "reasoning"],
        "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION": ["social_api", "press_api"],
        "ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION": ["shell", "build_tools"]
    }'''
content = content.replace(old, new)
open("scripts/courier_continue.py", "w").write(content)
