with open("/Users/user/Desktop/Muse New 2026 Mac/app/cannon/mac_launcher.py", "r") as f:
    s = f.read()

s = s.replace(
    '        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,\n        , start_new_session=True)',
    '        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,\n        start_new_session=True)'
)

with open("/Users/user/Desktop/Muse New 2026 Mac/app/cannon/mac_launcher.py", "w") as f:
    f.write(s)
