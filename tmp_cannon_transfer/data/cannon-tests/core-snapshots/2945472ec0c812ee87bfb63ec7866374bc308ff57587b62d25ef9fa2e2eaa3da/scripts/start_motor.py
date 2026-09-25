import subprocess, sys, os

def launch(module, log_file):
    f = open(os.path.join('logs', log_file), 'a')
    subprocess.Popen([sys.executable, '-u', '-m', module], stdout=f, stderr=f, creationflags=0x08000008)

if not os.path.exists('logs'): os.makedirs('logs')
launch('server.app', 'courier_daemon.log')
launch('scripts.courier_github_dispatcher', 'courier_github_dispatcher.log')
launch('scripts.courier_watchdog', 'courier_watchdog.log')

