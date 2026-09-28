with open("scripts/q14_proof.py", "r") as f:
    content = f.read()

# Replace top-level server thread execution
content = content.replace("""import threading
from server.app import app
def run_server():
    app.run(host="0.0.0.0", port=8080, use_reloader=False)

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)
""", "")

content = content.replace("def main():", """def main():
    import threading
    from server.app import app
    def run_server():
        app.run(host="0.0.0.0", port=8080, use_reloader=False)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)
""")

with open("scripts/q14_proof.py", "w") as f:
    f.write(content)
