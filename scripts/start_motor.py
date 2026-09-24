import os
import socket
import subprocess
import sys


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_python_exe():
    if os.environ.get("COURIER_PYTHON"):
        return os.environ["COURIER_PYTHON"]
    return sys.executable


def launch(module, log_file):
    log_path = os.path.join("logs", log_file)
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    f = open(log_path, "a")
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000008
    python_exe = get_python_exe()
    try:
        subprocess.Popen([python_exe, "-u", "-m", module], stdout=f, stderr=f, **kwargs)
    finally:
        f.close()


def main():
    if not os.path.exists("logs"):
        os.makedirs("logs", exist_ok=True)

    if is_port_in_use(8081) or is_port_in_use(8080):
        print(
            "Courier daemon appears to be running already (port 8081/8080 is in use). Refusing to start duplicate background jobs."
        )
    else:
        launch("server.app", "courier_daemon.log")
        launch("scripts.courier_github_dispatcher", "courier_github_dispatcher.log")
        launch("scripts.courier_watchdog", "courier_watchdog.log")


if __name__ == "__main__":
    main()
