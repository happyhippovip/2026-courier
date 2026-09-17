import sys, os
content = open("server/app.py").read()
content = content.replace('app.run(host="0.0.0.0", port=8080)', 'app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8080)))')
open("server/app.py", "w").write(content)
