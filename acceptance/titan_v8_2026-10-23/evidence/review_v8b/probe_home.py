import sys, os, shutil
sys.path.insert(0, ".")
from adapters import local_shell as ls
P=sys.argv[1]
os.environ["HTTPS_PROXY"]="http://u:p@proxy:3128"; os.environ["SSL_CERT_FILE"]="/x/ca.pem"; os.environ["GIT_AUTHOR_NAME"]="Bob"
w=P+"/wd_git"; shutil.rmtree(w, ignore_errors=True)
r=ls.run({"command":["sh","-c","git init -q . && echo a>f && git add -A && git commit -qm init && git log --stat > out.txt"],"timeout_s":30}, w)
print("git commit:", r.outcome, r.reason[:200])
w2=P+"/wd_env"; shutil.rmtree(w2, ignore_errors=True)
r=ls.run({"command":["sh","-c","env | sort > out.txt; pip config list >/dev/null 2>&1; git config --global --list >>out.txt 2>&1; true"],"timeout_s":30}, w2)
print(open(w2+"/out.txt").read())
