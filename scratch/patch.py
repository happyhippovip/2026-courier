with open("scripts/mac_continuous_controller.py", "r") as f:
    text = f.read()
text = text.replace('reg.register_worker("WINDOWS", "WINDOWS_NATIVE", "WINDOWS", AvailabilityClass.TEMPORARY_30_DAY, [r"C:\Dev\Windows-AI-OS"])', 'reg.register_worker("WINDOWS", "WINDOWS_NATIVE", "WINDOWS", availability_class=AvailabilityClass.TEMPORARY_30_DAY, mutable_scope=[r"C:\Dev\Windows-AI-OS"])')
with open("scripts/mac_continuous_controller.py", "w") as f:
    f.write(text)
