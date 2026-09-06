with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

content = content.replace(
    '        except Exception as e:\n            self.last_result_status = "FAIL"\n            return "FAIL_CLOSED"',
    '        except Exception as e:\n            print("VERIFY EXCEPTION:", e)\n            self.last_result_status = "FAIL"\n            return "FAIL_CLOSED"'
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
