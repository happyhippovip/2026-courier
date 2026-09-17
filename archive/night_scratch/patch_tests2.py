import sys
content = open("tests/test_courier_continue.py").read()

content = content.replace(
'''"ONBOARD_FIRST_PILOT_CUSTOMER - AUTHORIZED_MACHINE_ACTION"]''',
'''"ONBOARD_FIRST_PILOT_CUSTOMER - AUTHORIZED_MACHINE_ACTION", "ONBOARD_FIRST_PILOT_CUSTOMER - IRREVERSIBLE_HUMAN_ACTION"]''')

open("tests/test_courier_continue.py", "w").write(content)
