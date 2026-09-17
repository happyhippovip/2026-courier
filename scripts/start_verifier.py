import subprocess, sys, os
def launch(module, log_file):
    with open(os.path.join('scripts', log_file), 'a') as f:
        subprocess.Popen([sys.executable, '-u', '-m', module], stdout=f, stderr=f, creationflags=0x08000008)
launch('scripts.courier_verifier', 'verifier.log')
