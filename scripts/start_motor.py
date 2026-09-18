import subprocess, sys, os
import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def launch(module, log_file):
    f = open(os.path.join('logs', log_file), 'a')
    subprocess.Popen([sys.executable, '-u', '-m', module], stdout=f, stderr=f)

if not os.path.exists('logs'): os.makedirs('logs')

if is_port_in_use(8081) or is_port_in_use(8080):
    print("Courier daemon appears to be running already (port 8081/8080 is in use). Refusing to start duplicate background jobs.")
else:
    launch('server.app', 'courier_daemon.log')
    launch('scripts.courier_github_dispatcher', 'courier_github_dispatcher.log')
    launch('scripts.courier_watchdog', 'courier_watchdog.log')
