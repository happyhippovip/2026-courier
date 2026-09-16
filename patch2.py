with open("scripts/github_worker_adapter.py", "r") as f:
    c = f.read()

c = c.replace("""                    if art_path.exists():
                        import shutil
                        shutil.copy(art_path, ".")""", """                    if art_path.exists():
                        shutil.copy(art_path, ".")""")

with open("scripts/github_worker_adapter.py", "w") as f:
    f.write(c)
