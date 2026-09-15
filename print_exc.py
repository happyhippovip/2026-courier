import sys
path = "scripts/courier_safety_dispatcher.py"
data = open(path).read()
data = data.replace('self.last_result_status = "FAIL"', 'print("FAIL AT LINE"); self.last_result_status = "FAIL"')
open(path, "w").write(data)
