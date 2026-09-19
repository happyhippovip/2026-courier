import sys
content = open("prep_real_worker_final.py").read()
content = content.replace('def http_post(', 'import os\n    for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]: os.environ.pop(k, None)\n    def http_post(')
open("prep_real_worker_final.py", "w").write(content)
