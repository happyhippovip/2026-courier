import sys
with open('scripts/mac_windows_dispatcher.py', 'r') as f:
    code = f.read()

code = code.replace("result_json.get('EXIT_CODE')", "result_json.get('ExitCode', result_json.get('EXIT_CODE'))")
code = code.replace("result_json.get('STATUS')", "result_json.get('Status', result_json.get('STATUS'))")
code = code.replace("result_json.get('OUTPUT')", "result_json.get('Output', result_json.get('OUTPUT'))")

with open('scripts/mac_windows_dispatcher.py', 'w') as f:
    f.write(code)
