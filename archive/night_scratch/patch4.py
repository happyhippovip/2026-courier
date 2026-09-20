import sys

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'assert launchd_wid is not None, "Launchd worker not registered in Central"',
    '''import time
    for _ in range(15):
        if launchd_wid is not None: break
        time.sleep(1)
        workers = http_get("/workers")
        for wid, winfo in workers.items():
            if wid.startswith("MAC-") and wid != "MAC-CLI-1":
                launchd_wid = wid
                break
    assert launchd_wid is not None, "Launchd worker not registered in Central"'''
)

open("tests/test_tomato_two_torture.py", "w").write(content)
