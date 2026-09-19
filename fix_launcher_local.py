with open("app/cannon/mac_launcher.py", "r") as f:
    s = f.read()
s = s.replace('        cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,\n        , start_new_session=True,\n', '        cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,\n        start_new_session=True,\n')
with open("app/cannon/mac_launcher.py", "w") as f:
    f.write(s)
