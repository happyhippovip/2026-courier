import sys

content = open("scripts/courier_continue.py").read()

new_logic = """
            scope = "dependent"
            
            # Any automatable preparation or machine action is independent unless strictly gated
            if "independent" in edge.lower():
                scope = "independent"
            elif any(k in edge for k in ["PUBLIC DEPLOYMENT", "PUBLICATION VERIFICATION", "PILOT INTAKE", "SALES PACKAGE", "POST-PILOT HARDENING", "ONBOARD_FIRST_PILOT_CUSTOMER", "EXTERNAL_PUBLICATION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED", "FIRST PILOT"]):
                # Make preparation and authorized machine actions independent so they can execute concurrently
                # Only the HUMAN_ACTION should block its own downstream steps, but maybe not unrelated ones!
                if "SAFE_AUTOMATABLE_PREPARATION" in edge or "AUTHORIZED_MACHINE_ACTION" in edge:
                    scope = "independent"
                else:
                    scope = "independent"
            
            # For RELEASE, we treat preparation and machine action as independent if we want them to run.
            # But wait, RELEASE - AUTHORIZED_MACHINE_ACTION depends on SAFE_AUTOMATABLE_PREPARATION.
            # And RELEASE - IRREVERSIBLE_HUMAN_ACTION depends on AUTHORIZED_MACHINE_ACTION.
            # If we make them all 'independent', the DAG order handles it?
            # No, if they are independent, they execute concurrently!
            # We want them to execute sequentially if dependent, but NOT blocked by unrelated things.
"""

content = content.replace("""            if "independent" in edge.lower() or edge in ["PUBLIC DEPLOYMENT", "PUBLICATION VERIFICATION", "PILOT INTAKE", "SALES PACKAGE", "POST-PILOT HARDENING"]:
                scope = "independent\"""", """            if "independent" in edge.lower() or any(k in edge for k in ["PUBLIC DEPLOYMENT", "PUBLICATION VERIFICATION", "PILOT INTAKE", "SALES PACKAGE", "POST-PILOT HARDENING", "FIRST PILOT", "PAYMENT", "ONBOARD"]):
                scope = "independent\"""")

open("scripts/courier_continue.py", "w").write(content)
