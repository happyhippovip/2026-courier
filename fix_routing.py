import re
import subprocess

subprocess.run(["git", "checkout", "scripts/routing_proof.py"])

with open("scripts/routing_proof.py", "r") as f:
    content = f.read()

content = content.replace("server_proc = subprocess.Popen([sys.executable, \"-m\", \"server.app\"], env=os.environ)\ntime.sleep(2)", "")
content = content.replace("print(\"Registering Windows worker...\")", """def main():
    server_proc = subprocess.Popen([sys.executable, "-m", "server.app"], env=os.environ)
    time.sleep(2)
    print("Registering Windows worker...")""")

new_lines = []
in_main = False
for line in content.split("\n"):
    if line.startswith("def main():"):
        in_main = True
        new_lines.append(line)
        continue
    
    if in_main:
        if line.strip() == "":
            new_lines.append("")
        else:
            new_lines.append("    " + line)
    else:
        new_lines.append(line)

new_content = "\n".join(new_lines) + "\n\nif __name__ == '__main__':\n    main()\n"
with open("scripts/routing_proof.py", "w") as f:
    f.write(new_content)
