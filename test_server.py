import sys
sys.path.insert(0, 'app')
import server
try:
    server.main()
except Exception as e:
    print("EXCEPTION:", e)
