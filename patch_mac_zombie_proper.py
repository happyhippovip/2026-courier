import re

with open("scripts/mac_worker/daemon.py", "r") as f:
    code = f.read()

code = code.replace("""        except subprocess.TimeoutExpired:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(1)
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    process.terminate()
                    time.sleep(1)
                    process.kill()
            except Exception:
                pass""", """        except subprocess.TimeoutExpired:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(1)
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    process.terminate()
                    time.sleep(1)
                    process.kill()
            except Exception:
                pass
            process.wait()""")

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(code)
